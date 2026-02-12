"""Diagnostics support for ista VDM."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import IstaVdmConfigEntry

TO_REDACT = {"password", "email"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IstaVdmConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    api = entry.runtime_data
    
    # Get flat info if available
    flat_info = {}
    if hasattr(api, "_flat_info") and api._flat_info:
        flat_info = api._flat_info
    
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "api_status": {
            "authenticated": api.is_authenticated if hasattr(api, "is_authenticated") else False,
            "flat_id": getattr(api, "_flat_id", None),
        },
        "flat_info": flat_info,
    }