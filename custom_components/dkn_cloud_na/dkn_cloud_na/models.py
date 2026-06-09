"""Data models and sanitisation, ported from the app's Vue source.

``sanitize_device`` mirrors ``decompiled/src-app/src/models/devices.model.js``:
the backend sends loosely-typed JSON; we coerce known fields to Python types
and apply the same clamping the app applies. ``Device`` then exposes
climate-friendly helpers (current/target temperature, fan, mode) and control
methods that emit ``create-machine-event`` through a bound sender callback.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from .const import (
    MODE_AUTO,
    MODE_COOL,
    MODE_HEAT,
    RANGE_PROPS_BY_MODE,
    SETPOINT_PROP_BY_MODE,
    SETPOINT_PROP_BY_MODE_WATER,
    SLATS_AUTO,
    SLATS_SWING,
    UNIT_FAHRENHEIT,
)

# Third-party short names (app.config.js DEVICES_SHORT), reverse of link_t.manufacturer.
_DEVICES_SHORT = {"hw": "honeywell", "ecob": "ecobee", "nest": "nest"}
_TEMP_SENSOR = {0: "IU", 1: "T", 2: "M"}

# Field classification taken from sanitizeDevice() in devices.model.js.
_BOOL_FIELDS = frozenset({
    "acs_available", "aqpresent", "aqready",
    "aqionstatus0", "aqionstatus1", "aqionstatus2", "aqionstatus3",
    "aqionstatus4", "aqionstatus5", "aqionstatus6", "aqionstatus7",
    "block_on", "block_off", "block_mode", "block_setpoint",
    "device_master_slave", "isConnected", "leds_off", "machineready",
    "master", "power", "power_acs", "power_hot_water", "setpoint_step",
    "slats_autoud", "slats_autolr", "slats_swingud", "slats_swinglr",
    "tai_th", "tsensor_error", "emerheatpresent", "emerheatstatus", "t1t2on",
})
_NUMBER_FIELDS = frozenset({
    "acs_temp", "aqmode", "aqpm1_0", "aqpm2_5", "aqpm10",
    "consumption_ue", "error_value", "ext_temp", "local_temp", "mode",
    "pspeed", "exch_heat_temp_iu", "gas_pipe_temp_iu", "exch_heat_temp_ue",
    "disch_comp_temp_ue", "exp_valv_ue", "exp_valv_ui", "pe_ue", "pc_ue",
    "real_mode", "speed_state", "stat_channel", "stat_rssi", "units",
    "water_input_temp", "water_output_temp", "work_temp",
    "range_sp_acs_max", "range_sp_acs_min",
    "range_sp_auto_air_max", "range_sp_auto_air_min",
    "range_sp_auto_water_max", "range_sp_auto_water_min",
    "range_sp_cool_air_max", "range_sp_cool_air_min",
    "range_sp_cool_water_max", "range_sp_cool_water_min",
    "range_sp_hot_air_max", "range_sp_hot_air_min",
    "range_sp_hot_water_max", "range_sp_hot_water_min",
    "range_sp_vent_max", "range_sp_vent_min",
    "range_sp_dry_max", "range_sp_dry_min",
})
_STRING_FIELDS = frozenset({
    "error_ascii1", "error_ascii2", "icon", "name",
    "stat_ssid", "timezoneId", "version",
})
_ARRAY_FIELDS = frozenset({"mode_available", "speed_available"})

# Setpoints are clamped to their mode's range; map setpoint -> (min, max) prop.
_SETPOINT_RANGE = {
    "setpoint_acs": ("range_sp_acs_min", "range_sp_acs_max"),
    "setpoint_air_auto": ("range_sp_auto_air_min", "range_sp_auto_air_max"),
    "setpoint_air_cool": ("range_sp_cool_air_min", "range_sp_cool_air_max"),
    "setpoint_air_heat": ("range_sp_hot_air_min", "range_sp_hot_air_max"),
    "setpoint_air_vent": ("range_sp_vent_min", "range_sp_vent_max"),
    "setpoint_air_dry": ("range_sp_dry_min", "range_sp_dry_max"),
    "setpoint_water_auto": ("range_sp_auto_water_min", "range_sp_auto_water_max"),
    "setpoint_water_cool": ("range_sp_cool_water_min", "range_sp_cool_water_max"),
    "setpoint_water_heat": ("range_sp_hot_water_min", "range_sp_hot_water_max"),
}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def _to_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return int(num) if num.is_integer() else num


def _clamp(value: Optional[float], lo: Optional[float], hi: Optional[float]) -> Optional[float]:
    if value is None:
        return value
    if lo is not None and value < lo:
        return lo
    if hi is not None and value > hi:
        return hi
    return value


def sanitize_device(raw: dict) -> dict:
    """Coerce a raw backend device dict to typed values (partial dicts allowed)."""
    out: dict[str, Any] = {}

    for key, value in raw.items():
        if key in _BOOL_FIELDS:
            out[key] = _to_bool(value)
        elif key in _NUMBER_FIELDS:
            out[key] = _to_number(value)
        elif key in _STRING_FIELDS:
            out[key] = "" if value is None else str(value)
        elif key in _ARRAY_FIELDS:
            out[key] = list(value) if isinstance(value, (list, tuple)) else None
        elif key.startswith("slats_") and key not in ("slats_autoud", "slats_autolr",
                                                       "slats_swingud", "slats_swinglr"):
            out[key] = _to_number(value)

    # Special-cased fields (see devices.model.js).
    if "aidooit" in raw:
        out["pro"] = _to_bool(raw["aidooit"])
    if "fallback" in raw:
        out["link_fallback"] = _to_bool(raw["fallback"])

    manufacturer = raw.get("manufacturer")
    if isinstance(manufacturer, dict):
        if "_id" in manufacturer:
            mid = _to_number(manufacturer["_id"])
            out["manufacturerID"] = mid
            out["isS21"] = mid == 16
        if manufacturer.get("text") is not None:
            out["manufacturer"] = str(manufacturer["text"])

    link = raw.get("link_t")
    if isinstance(link, dict):
        if "manufacturer" in link:
            out["link_manufacturer"] = _DEVICES_SHORT.get(str(link["manufacturer"]))
        if "_id" in link:
            out["link_deviceID"] = str(link["_id"])
        if "isConnected" in link:
            out["link_isConnected"] = _to_bool(link["isConnected"])
        if "name" in link:
            out["link_name_thermostat"] = str(link["name"])

    if "work_temp_selec_sensor" in raw:
        out["work_temp_selec_sensor"] = _TEMP_SENSOR.get(_to_number(raw["work_temp_selec_sensor"]))

    # Clamp setpoints to their mode range, like parseBetween() in the app.
    for sp, (lo_key, hi_key) in _SETPOINT_RANGE.items():
        if sp in raw:
            out[sp] = _clamp(_to_number(raw[sp]), out.get(lo_key), out.get(hi_key))

    return out


class Device:
    """A single controllable unit (one ES.DKNWSERVER zone)."""

    def __init__(self, mac: str, installation_id: str, data: dict,
                 sender: Optional[Callable[[str, str, Any], Any]] = None):
        self.mac = mac
        self.installation_id = installation_id
        self.data: dict[str, Any] = sanitize_device(data)
        #: callable(mac, property, value) injected by the socket layer.
        self._sender = sender

    # -- merge / accessors --------------------------------------------------
    def update(self, partial_raw: dict) -> None:
        """Merge a partial ``device-data`` payload into this device."""
        self.data.update(sanitize_device(partial_raw))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def name(self) -> Optional[str]:
        return self.data.get("name")

    @property
    def available(self) -> bool:
        return bool(self.data.get("isConnected"))

    @property
    def is_on(self) -> bool:
        return bool(self.data.get("power"))

    @property
    def mode(self) -> Optional[int]:
        return self.data.get("mode")

    @property
    def modes_available(self) -> list[int]:
        return self.data.get("mode_available") or []

    @property
    def fahrenheit(self) -> bool:
        return self.data.get("units") == UNIT_FAHRENHEIT

    @property
    def is_water(self) -> bool:
        # Altherma DHW unit running in water mode (Unit.mixin.js isWater()).
        return bool(self.data.get("acs_available")) and self.data.get("tai_th") is False

    @property
    def current_temperature(self) -> Optional[float]:
        return self.data.get("work_temp") or self.data.get("local_temp")

    @property
    def fan_speeds_available(self) -> list[int]:
        return self.data.get("speed_available") or []

    @property
    def fan_speed(self) -> Optional[int]:
        return self.data.get("speed_state")

    @property
    def swing_available(self) -> bool:
        # Vertical louvre swing capability (slats_swingud in the model).
        return bool(self.data.get("slats_swingud"))

    @property
    def swinging(self) -> bool:
        return self.data.get("slats_vertical_1") == SLATS_SWING

    def setpoint_prop(self) -> Optional[str]:
        """Return the setpoint property name for the current mode/unit-type."""
        table = SETPOINT_PROP_BY_MODE_WATER if self.is_water else SETPOINT_PROP_BY_MODE
        return table.get(self.mode)

    @property
    def target_temperature(self) -> Optional[float]:
        prop = self.setpoint_prop()
        return self.data.get(prop) if prop else None

    def target_range(self) -> tuple[Optional[float], Optional[float]]:
        """(min, max) setpoint for the current mode."""
        keys = RANGE_PROPS_BY_MODE.get(self.mode)
        if not keys:
            return (None, None)
        return (self.data.get(keys[0]), self.data.get(keys[1]))

    @property
    def locked(self) -> bool:
        return any(self.data.get(k) for k in ("block_on", "block_off", "block_mode", "block_setpoint"))

    # -- control ------------------------------------------------------------
    def _send(self, prop: str, value: Any):
        if self._sender is None:
            raise RuntimeError("Device is not bound to a socket; cannot send control events.")
        return self._sender(self.mac, prop, value)

    def set_power(self, on: bool):
        return self._send("power", bool(on))

    def set_mode(self, mode: int):
        return self._send("mode", int(mode))

    def set_fan_speed(self, speed: int):
        return self._send("speed_state", int(speed))

    def set_setpoint(self, temperature: float):
        prop = self.setpoint_prop()
        if prop is None:
            raise ValueError(f"No setpoint property for mode {self.mode!r}")
        lo, hi = self.target_range()
        return self._send(prop, _clamp(temperature, lo, hi))

    def set_swing(self, on: bool):
        # Vertical louvre: SLATS_SWING toggles oscillation, SLATS_AUTO parks it.
        return self._send("slats_vertical_1", SLATS_SWING if on else SLATS_AUTO)

    def __repr__(self) -> str:
        return f"<Device {self.mac} {self.name!r} mode={self.mode} on={self.is_on}>"


class Installation:
    """A site/installation owning a set of devices."""

    def __init__(self, raw: dict, sender: Optional[Callable[[str, str, Any], Any]] = None):
        self.id: str = str(raw.get("_id") or raw.get("id") or raw.get("installationId") or "")
        self.name: Optional[str] = raw.get("name")
        self.timezone: Optional[str] = raw.get("timezoneId")
        self.raw = raw
        self.devices: dict[str, Device] = {}
        for dev in raw.get("devices") or []:
            mac = dev.get("mac")
            if mac:
                self.devices[mac] = Device(mac, self.id, dev, sender=sender)

    def bind_sender(self, sender: Callable[[str, str, Any], Any]) -> None:
        for dev in self.devices.values():
            dev._sender = sender

    def __repr__(self) -> str:
        return f"<Installation {self.id} {self.name!r} devices={len(self.devices)}>"


def parse_installations(payload: Any, sender=None) -> list[Installation]:
    """Parse the ``installations/dknUsa`` response into Installation objects.

    The endpoint may return a list, or an object whose values are installations
    (the app iterates ``for id in installations``); accept both.
    """
    items: Iterable[dict]
    if isinstance(payload, dict):
        items = [v for v in payload.values() if isinstance(v, dict)] or [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    return [Installation(item, sender=sender) for item in items]
