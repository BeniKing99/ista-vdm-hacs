"""The Ista VDM integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from ista_vdm_api import IstaVdmAPI, IstaVdmAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


type IstaVdmConfigEntry = ConfigEntry[IstaVdmAPI]


async def async_setup_entry(hass: HomeAssistant, entry: IstaVdmConfigEntry) -> bool:
    """Set up ista VDM from a config entry."""
    api = IstaVdmAPI(entry.data["email"], entry.data["password"])
    
    # Test the connection during setup
    try:
        await api.authenticate()
    except IstaVdmAuthError as err:
        # If auth fails, trigger re-authentication flow
        _LOGGER.error(
            "Authentication failed for %s: %s. Triggering re-authentication.",
            entry.title,
            err
        )
        entry.async_start_reauth(hass)
        return False
    except Exception as err:
        # For other errors, log and still try to set up
        _LOGGER.error(
            "Unexpected error during authentication for %s: %s",
            entry.title,
            err
        )
        entry.async_start_reauth(hass)
        return False
    
    entry.runtime_data = api
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IstaVdmConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: IstaVdmConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)