"""Native Engine.IO v3 / Socket.IO v2 long-polling client.

The dkncloudna.com backend is a Socket.IO **v2** server (Engine.IO **v3**),
confirmed live: the handshake returns length-prefixed framing
``97:0{...}2:40`` regardless of the requested EIO version. ``python-socketio``
v5 only speaks EIO4 (fails here with "OPEN packet not returned"), and pinning
the old v4 client conflicts with Home Assistant's bundled version. So we
implement just the slice of the protocol the app uses — **polling transport
only**, mirroring ``socket.service.js`` (``transports:['polling']``).

Protocol summary (Engine.IO v3 XHR-polling, string payloads):
  * payload framing: ``<charLen>:<packet>`` repeated.
  * engine.io packet types: 0 open, 1 close, 2 ping, 3 pong, 4 message, 6 noop.
  * socket.io packet (inside a ``4`` message): 0 CONNECT, 1 DISCONNECT, 2 EVENT,
    3 ACK, 4 ERROR, optionally prefixed with ``/namespace,``.
  * namespace connect  -> send ``40/{id}::dknUsa,``
  * inbound event      -> ``42/{id}::dknUsa,["device-data",{mac,data}]``
  * outbound control   -> ``42/{id}::dknUsa,["create-machine-event",{...}]``
  * client sends engine.io ping ``2`` every ``pingInterval`` (15 s), expects ``3``.
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import json
import logging
import time
from typing import Any, Awaitable, Callable, Optional, Union

import aiohttp

from .const import (
    EVENT_CREATE_MACHINE,
    EVENT_DEVICE_DATA,
    SCOPE,
    SOCKET_PATH,
    SOCKET_URL,
)
from .exceptions import DknAuthError, DknConnectionError

_LOGGER = logging.getLogger(__name__)

DeviceDataCb = Callable[[str, dict], Union[None, Awaitable[None]]]
EventCb = Callable[[str, list], Union[None, Awaitable[None]]]
TokenRefresh = Callable[[], Awaitable[str]]

# engine.io packet type codes
_EIO_OPEN, _EIO_CLOSE, _EIO_PING, _EIO_PONG, _EIO_MESSAGE, _EIO_UPGRADE, _EIO_NOOP = "0123456"
# socket.io packet type codes
_SIO_CONNECT, _SIO_DISCONNECT, _SIO_EVENT, _SIO_ACK, _SIO_ERROR = range(5)

_counter = itertools.count()


def _cache_buster() -> str:
    # socket.io-client uses a unique 't' query param per request.
    return f"{int(time.time() * 1000):x}-{next(_counter)}"


def decode_payload(data: str) -> list[str]:
    """Split an Engine.IO v3 string payload into individual packets."""
    packets: list[str] = []
    i, n = 0, len(data)
    while i < n:
        colon = data.find(":", i)
        if colon == -1:
            break
        length = int(data[i:colon])
        start = colon + 1
        packets.append(data[start:start + length])
        i = start + length
    return packets


def encode_payload(packet: str) -> str:
    """Frame a single packet for an Engine.IO v3 string POST body."""
    return f"{len(packet)}:{packet}"


def parse_sio(packet: str) -> tuple[int, str, Optional[Any]]:
    """Parse a socket.io packet body (the part after the engine.io '4')."""
    sio_type = int(packet[0])
    rest = packet[1:]
    namespace = "/"
    if rest.startswith("/"):
        comma = rest.find(",")
        if comma == -1:
            return sio_type, rest, None
        namespace, rest = rest[:comma], rest[comma + 1:]
    # An optional numeric ack id may precede the JSON; try parsing the body
    # as-is first, then again with any leading ack-id digits stripped.
    k = 0
    while k < len(rest) and rest[k].isdigit():
        k += 1
    data: Optional[Any] = None
    for candidate in (rest, rest[k:]):
        if not candidate:
            data = None
            break
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    return sio_type, namespace, data


class DknSocket:
    """A Socket.IO v2 polling connection to a single installation namespace."""

    def __init__(
        self,
        installation_id: str,
        token: str,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        base_url: str = SOCKET_URL,
        on_device_data: Optional[DeviceDataCb] = None,
        on_event: Optional[EventCb] = None,
        token_refresh: Optional[TokenRefresh] = None,
    ):
        self.installation_id = installation_id
        self.namespace = f"/{installation_id}::{SCOPE}"
        self._token = token
        self._url = base_url.rstrip("/") + SOCKET_PATH  # .../socket.io/
        self._on_device_data = on_device_data
        self._on_event = on_event
        self._token_refresh = token_refresh

        self._session = session
        self._own_session = session is None

        self._sid: Optional[str] = None
        self._ping_interval = 15.0
        self._ping_timeout = 30.0
        self._closing = False
        self._ns_connected = asyncio.Event()
        self._poll_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    # -- public API ---------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._ns_connected.is_set() and not self._closing

    def update_token(self, token: str) -> None:
        self._token = token

    async def connect(self, *, connect_timeout: float = 20.0) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        self._closing = False
        await self._handshake()
        # Connect to our namespace, then start the background loops.
        await self._send_packet(f"{_EIO_MESSAGE}{_SIO_CONNECT}{self.namespace},")
        self._poll_task = asyncio.create_task(self._poll_loop(), name=f"dkn-poll-{self.installation_id}")
        self._ping_task = asyncio.create_task(self._ping_loop(), name=f"dkn-ping-{self.installation_id}")
        try:
            await asyncio.wait_for(self._ns_connected.wait(), timeout=connect_timeout)
        except asyncio.TimeoutError as err:
            await self.disconnect()
            raise DknConnectionError("Timed out connecting to socket namespace") from err

    async def send_event(self, mac: str, prop: str, value: Any) -> None:
        """Emit ``create-machine-event`` (the control channel)."""
        payload = json.dumps(
            [EVENT_CREATE_MACHINE, {"mac": mac, "property": prop, "value": value}],
            separators=(",", ":"),
        )
        _LOGGER.debug("emit %s %s=%s", mac, prop, value)
        await self._send_packet(f"{_EIO_MESSAGE}{_SIO_EVENT}{self.namespace},{payload}")

    async def disconnect(self) -> None:
        self._closing = True
        for task in (self._poll_task, self._ping_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
        self._poll_task = self._ping_task = None
        self._ns_connected.clear()
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    # -- transport ----------------------------------------------------------
    def _params(self, *, with_sid: bool = True) -> dict[str, str]:
        params = {"EIO": "3", "transport": "polling", "t": _cache_buster()}
        if with_sid and self._sid:
            params["sid"] = self._sid
        return params

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _handshake(self) -> None:
        assert self._session is not None
        try:
            async with self._session.get(
                self._url,
                params=self._params(with_sid=False),
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status == 401:
                    await self._try_refresh()
                    return await self._handshake()
                if resp.status >= 400:
                    raise DknConnectionError(f"Handshake HTTP {resp.status}")
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise DknConnectionError(f"Handshake failed: {err}") from err

        for packet in decode_payload(text):
            if packet and packet[0] == _EIO_OPEN:
                info = json.loads(packet[1:])
                self._sid = info["sid"]
                self._ping_interval = info.get("pingInterval", 15000) / 1000
                self._ping_timeout = info.get("pingTimeout", 30000) / 1000
                _LOGGER.debug("handshake sid=%s ping=%ss", self._sid, self._ping_interval)
        if not self._sid:
            raise DknConnectionError("Handshake did not return a sid")

    async def _get(self) -> str:
        assert self._session is not None
        total = self._ping_interval + self._ping_timeout + 10
        async with self._session.get(
            self._url,
            params=self._params(),
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=total),
        ) as resp:
            if resp.status == 401:
                await self._try_refresh()
                raise _Reconnect()
            if resp.status >= 400:
                raise DknConnectionError(f"Poll HTTP {resp.status}")
            return await resp.text()

    async def _send_packet(self, packet: str) -> None:
        assert self._session is not None
        body = encode_payload(packet)
        _LOGGER.debug("POST -> %r", body)
        async with self._session.post(
            self._url,
            params=self._params(),
            headers={**self._headers(), "Content-Type": "text/plain;charset=UTF-8"},
            data=body.encode("utf-8"),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status == 401:
                await self._try_refresh()
                raise _Reconnect()
            if resp.status >= 400:
                raise DknConnectionError(f"Send HTTP {resp.status}")
            await resp.read()

    async def _try_refresh(self) -> None:
        if not self._token_refresh:
            raise DknAuthError("Socket auth expired and no token_refresh provided")
        self._token = await self._token_refresh()

    # -- loops --------------------------------------------------------------
    async def _ping_loop(self) -> None:
        try:
            while not self._closing:
                await asyncio.sleep(self._ping_interval)
                if self._closing:
                    return
                try:
                    await self._send_packet(_EIO_PING)
                except _Reconnect:
                    return  # poll loop owns reconnection
                except DknConnectionError as err:
                    _LOGGER.debug("ping failed: %s", err)
        except asyncio.CancelledError:
            raise

    async def _poll_loop(self) -> None:
        backoff = 1.0
        try:
            while not self._closing:
                try:
                    text = await self._get()
                    _LOGGER.debug("GET <- %r", text)
                    backoff = 1.0
                    for packet in decode_payload(text):
                        await self._handle_packet(packet)
                except _Reconnect:
                    if self._closing:
                        return
                    await self._reconnect()
                except (DknConnectionError, aiohttp.ClientError, asyncio.TimeoutError) as err:
                    if self._closing:
                        return
                    _LOGGER.warning("socket poll error (%s); reconnecting in %ss", err, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    await self._reconnect()
        except asyncio.CancelledError:
            raise

    async def _reconnect(self) -> None:
        self._ns_connected.clear()
        self._sid = None
        try:
            await self._handshake()
            await self._send_packet(f"{_EIO_MESSAGE}{_SIO_CONNECT}{self.namespace},")
        except (_Reconnect, DknConnectionError) as err:
            _LOGGER.debug("reconnect attempt failed: %s", err)

    # -- packet handling ----------------------------------------------------
    async def _handle_packet(self, packet: str) -> None:
        if not packet:
            return
        etype = packet[0]
        if etype == _EIO_PING:          # server-initiated ping -> pong
            await self._send_packet(_EIO_PONG)
        elif etype == _EIO_PONG:        # reply to our ping
            return
        elif etype == _EIO_CLOSE:
            _LOGGER.debug("server closed engine.io")
        elif etype == _EIO_MESSAGE:
            await self._handle_message(packet[1:])

    async def _handle_message(self, body: str) -> None:
        if not body:
            return
        sio_type, namespace, data = parse_sio(body)
        if namespace != self.namespace and namespace != "/":
            return
        if sio_type == _SIO_CONNECT and namespace == self.namespace:
            _LOGGER.info("installation %s namespace connected", self.installation_id)
            self._ns_connected.set()
        elif sio_type == _SIO_ERROR:
            _LOGGER.error("socket namespace error: %s", data)
            self._ns_connected.clear()
        elif sio_type == _SIO_EVENT and isinstance(data, list) and data:
            await self._dispatch_event(data)

    async def _dispatch_event(self, data: list) -> None:
        name = data[0]
        args = data[1:]
        if name == EVENT_DEVICE_DATA and args and self._on_device_data:
            payload = args[0] or {}
            mac = payload.get("mac")
            dev_data = payload.get("data", {}) or {}
            if mac:
                await _maybe_await(self._on_device_data(mac, dev_data))
        if self._on_event:
            await _maybe_await(self._on_event(name, args))


class _Reconnect(Exception):
    """Internal signal: token refreshed / transport reset, restart the session."""


async def _maybe_await(result: Any) -> None:
    if inspect.isawaitable(result):
        await result
