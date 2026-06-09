"""Climate platform for DKN Cloud NA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .dkn_cloud_na import (
    MODE_AUTO,
    MODE_COOL,
    MODE_DRY,
    MODE_FAN,
    MODE_HEAT,
    Device,
)
from .dkn_cloud_na.const import SLATS_AUTO, SLATS_SWING

from .const import DOMAIN
from .coordinator import DknCoordinator

MODE_TO_HVAC: dict[int, HVACMode] = {
    MODE_AUTO: HVACMode.HEAT_COOL,
    MODE_COOL: HVACMode.COOL,
    MODE_HEAT: HVACMode.HEAT,
    MODE_FAN: HVACMode.FAN_ONLY,
    MODE_DRY: HVACMode.DRY,
}
HVAC_TO_MODE: dict[HVACMode, int] = {v: k for k, v in MODE_TO_HVAC.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create a climate entity per device."""
    coordinator: DknCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DknClimate(coordinator, mac) for mac in coordinator.devices
    )


class DknClimate(CoordinatorEntity[DknCoordinator], ClimateEntity):
    """A single DKN/Airzone zone as a climate entity."""

    _attr_has_entity_name = True
    _attr_name = None  # use the device name
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: DknCoordinator, mac: str):
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = mac

    # -- helpers ------------------------------------------------------------
    @property
    def _device(self) -> Device:
        return self.coordinator.devices[self._mac]

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._device
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=dev.name,
            manufacturer="Daikin / Airzone",
            model=dev.get("manufacturer") or "DKN ES.DKNWSERVER",
            sw_version=dev.get("version"),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._device.available

    # -- temperature --------------------------------------------------------
    @property
    def temperature_unit(self) -> str:
        return (
            UnitOfTemperature.FAHRENHEIT
            if self._device.fahrenheit
            else UnitOfTemperature.CELSIUS
        )

    @property
    def current_temperature(self) -> float | None:
        return self._device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self._device.target_temperature

    @property
    def target_temperature_step(self) -> float:
        return 0.5 if self._device.get("setpoint_step") else 1.0

    @property
    def min_temp(self) -> float:
        lo, _ = self._device.target_range()
        return lo if lo is not None else super().min_temp

    @property
    def max_temp(self) -> float:
        _, hi = self._device.target_range()
        return hi if hi is not None else super().max_temp

    # -- hvac mode ----------------------------------------------------------
    @property
    def hvac_mode(self) -> HVACMode:
        dev = self._device
        if not dev.is_on:
            return HVACMode.OFF
        return MODE_TO_HVAC.get(dev.mode, HVACMode.AUTO)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [MODE_TO_HVAC[m] for m in self._device.modes_available if m in MODE_TO_HVAC]
        return [HVACMode.OFF, *modes]

    # -- fan ----------------------------------------------------------------
    @property
    def fan_modes(self) -> list[str] | None:
        speeds = self._device.fan_speeds_available
        return [str(s) for s in speeds] if speeds else None

    @property
    def fan_mode(self) -> str | None:
        speed = self._device.fan_speed
        return str(speed) if speed is not None else None

    # -- swing (vertical and/or horizontal, per capability) -----------------
    @property
    def _swing_supported(self) -> bool:
        d = self._device
        return d.vertical_swing_available or d.horizontal_swing_available

    @property
    def swing_modes(self) -> list[str] | None:
        d = self._device
        if not self._swing_supported:
            return None
        modes = [SWING_OFF]
        if d.vertical_swing_available:
            modes.append(SWING_VERTICAL)
        if d.horizontal_swing_available:
            modes.append(SWING_HORIZONTAL)
        if d.vertical_swing_available and d.horizontal_swing_available:
            modes.append(SWING_BOTH)
        return modes

    @property
    def swing_mode(self) -> str | None:
        if not self._swing_supported:
            return None
        d = self._device
        v, h = d.vertical_swinging, d.horizontal_swinging
        if v and h:
            return SWING_BOTH
        if v:
            return SWING_VERTICAL
        if h:
            return SWING_HORIZONTAL
        return SWING_OFF

    # -- features -----------------------------------------------------------
    @property
    def supported_features(self) -> ClimateEntityFeature:
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self._device.fan_speeds_available:
            features |= ClimateEntityFeature.FAN_MODE
        if self._swing_supported:
            features |= ClimateEntityFeature.SWING_MODE
        return features

    # -- commands (optimistic; the device-data echo reconciles) -------------
    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        dev = self._device
        await dev.set_setpoint(temperature)
        prop = dev.setpoint_prop()
        if prop:
            dev.data[prop] = temperature
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        dev = self._device
        if hvac_mode == HVACMode.OFF:
            await dev.set_power(False)
            dev.data["power"] = False
        else:
            if not dev.is_on:
                await dev.set_power(True)
                dev.data["power"] = True
            mode = HVAC_TO_MODE.get(hvac_mode)
            if mode is not None:
                await dev.set_mode(mode)
                dev.data["mode"] = mode
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await self._device.set_power(True)
        self._device.data["power"] = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        await self._device.set_power(False)
        self._device.data["power"] = False
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        dev = self._device
        await dev.set_fan_speed(int(fan_mode))
        dev.data["speed_state"] = int(fan_mode)
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        dev = self._device
        want_v = swing_mode in (SWING_VERTICAL, SWING_BOTH)
        want_h = swing_mode in (SWING_HORIZONTAL, SWING_BOTH)
        if dev.vertical_swing_available:
            await dev.set_vertical_swing(want_v)
            dev.data["slats_vertical_1"] = SLATS_SWING if want_v else SLATS_AUTO
        if dev.horizontal_swing_available:
            await dev.set_horizontal_swing(want_h)
            dev.data["slats_horizontal_1"] = SLATS_SWING if want_h else SLATS_AUTO
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        # The coordinator updates Device objects in place; just re-render.
        self.async_write_ha_state()
