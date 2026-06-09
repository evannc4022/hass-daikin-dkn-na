"""Diagnostic / measurement sensors for DKN Cloud NA devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DknCoordinator
from .dkn_cloud_na import Device


@dataclass(frozen=True, kw_only=True)
class DknSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Device], float | None]
    exists_fn: Callable[[Device], bool]
    is_temperature: bool = False


def _present(key: str) -> Callable[[Device], bool]:
    return lambda d: d.get(key) is not None


SENSORS: tuple[DknSensorDescription, ...] = (
    DknSensorDescription(
        key="ext_temp",
        name="Outdoor temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        is_temperature=True,
        value_fn=lambda d: d.get("ext_temp"),
        exists_fn=_present("ext_temp"),
    ),
    DknSensorDescription(
        key="stat_rssi",
        name="Wi-Fi signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("stat_rssi"),
        exists_fn=_present("stat_rssi"),
    ),
    DknSensorDescription(
        key="consumption_ue",
        name="Outdoor unit current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Reported as amps x10.
        value_fn=lambda d: (d.get("consumption_ue") / 10 if d.get("consumption_ue") is not None else None),
        exists_fn=_present("consumption_ue"),
    ),
    DknSensorDescription(
        key="aqpm2_5",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("aqpm2_5"),
        exists_fn=lambda d: d.get("aqpresent") and d.get("aqpm2_5") is not None,
    ),
    DknSensorDescription(
        key="aqpm10",
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("aqpm10"),
        exists_fn=lambda d: d.get("aqpresent") and d.get("aqpm10") is not None,
    ),
    DknSensorDescription(
        key="aqpm1_0",
        name="PM1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("aqpm1_0"),
        exists_fn=lambda d: d.get("aqpresent") and d.get("aqpm1_0") is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DknCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[DknSensor] = []
    for mac, device in coordinator.devices.items():
        for desc in SENSORS:
            if desc.exists_fn(device):
                entities.append(DknSensor(coordinator, mac, desc))
    async_add_entities(entities)


class DknSensor(CoordinatorEntity[DknCoordinator], SensorEntity):
    """A single value read from a device's live data."""

    _attr_has_entity_name = True
    entity_description: DknSensorDescription

    def __init__(self, coordinator: DknCoordinator, mac: str, description: DknSensorDescription):
        super().__init__(coordinator)
        self._mac = mac
        self.entity_description = description
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, mac)})

    @property
    def _device(self) -> Device:
        return self.coordinator.devices[self._mac]

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._device.available

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self._device)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.is_temperature:
            return (
                UnitOfTemperature.FAHRENHEIT
                if self._device.fahrenheit
                else UnitOfTemperature.CELSIUS
            )
        return self.entity_description.native_unit_of_measurement
