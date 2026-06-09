"""The DKN Cloud NA integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .dkn_cloud_na import DknApiError, DknAuthError, DknConnectionError

from .const import DOMAIN
from .coordinator import DknCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DKN Cloud NA from a config entry."""
    coordinator = DknCoordinator(hass, entry)
    try:
        await coordinator.async_setup()
    except (DknAuthError,) as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except (DknApiError, DknConnectionError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: DknCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unloaded
