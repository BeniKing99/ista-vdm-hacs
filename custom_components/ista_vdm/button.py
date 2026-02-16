"""Platform for ista VDM button integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IstaVdmConfigEntry
from .const import DOMAIN
from .sensor import IstaVdmDataUpdateCoordinator

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IstaVdmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ista VDM button based on a config entry."""
    coordinator: IstaVdmDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Ista VDM",
        manufacturer="ista",
        model="VDM",
    )
    
    async_add_entities([
        IstaVdmRefreshButton(coordinator, entry, device_info),
    ])


class IstaVdmRefreshButton(ButtonEntity):
    """Button to manually refresh ista VDM data."""

    entity_description = ButtonEntityDescription(
        key="refresh",
        name="Refresh Data",
        icon="mdi:refresh",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the button."""
        self._entry = entry
        self._coordinator = coordinator
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_refresh"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Manual refresh triggered for %s", self._entry.entry_id)
        await self._coordinator.async_refresh()
