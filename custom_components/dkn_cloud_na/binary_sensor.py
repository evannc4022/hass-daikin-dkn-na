"""Connectivity / problem binary sensors for DKN Cloud NA devices."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DknCoordinator
from .dkn_cloud_na import Device


@dataclass(frozen=True, kw_only=True)
class DknBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[Device], bool]
    exists_fn: Callable[[Device], bool]
    # Connectivity must stay available even when the unit is offline.
    follow_availability: bool = True


BINARY_SENSORS: tuple[DknBinaryDescription, ...] = (
    DknBinaryDescription(
        key="connectivity",
        name="Connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.get("isConnected")),
        exists_fn=lambda d: "isConnected" in d.data,
        follow_availability=False,
    ),
    DknBinaryDescription(
        key="problem",
        name="Problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.get("error_value")),
        exists_fn=lambda d: d.get("error_value") is not None,
    ),
    DknBinaryDescription(
        key="tsensor_error",
        name="Temperature sensor problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.get("tsensor_error")),
        exists_fn=lambda d: d.get("tsensor_error") is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: DknCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[DknBinarySensor] = []
    for mac, device in coordinator.devices.items():
        for desc in BINARY_SENSORS:
            if desc.exists_fn(device):
                entities.append(DknBinarySensor(coordinator, mac, desc))
    async_add_entities(entities)


class DknBinarySensor(CoordinatorEntity[DknCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    entity_description: DknBinaryDescription

    def __init__(self, coordinator: DknCoordinator, mac: str, description: DknBinaryDescription):
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
        if not self.coordinator.last_update_success:
            return False
        if self.entity_description.follow_availability:
            return self._device.available
        return True

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self._device)
