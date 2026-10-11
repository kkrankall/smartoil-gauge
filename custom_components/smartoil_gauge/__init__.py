"""The Smart Oil Gauge integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store

from .api import SmartOilClient
from .const import DOMAIN
from .coordinator import SmartOilConfigEntry, SmartOilCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SmartOilConfigEntry) -> bool:
    """Set up Smart Oil Gauge from a config entry."""
    # A session of its own, so the login cookie stays out of HA's shared one.
    # HA detaches it when the entry unloads.
    session = async_create_clientsession(hass)
    client = SmartOilClient(session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = SmartOilCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartOilConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: SmartOilConfigEntry) -> None:
    """Delete the saved login cookie when the integration is removed."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
