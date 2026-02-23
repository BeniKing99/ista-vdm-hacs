"""Test the ista VDM button platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ista_vdm.button import IstaVdmRefreshButton
from custom_components.ista_vdm.const import DOMAIN


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_refresh = AsyncMock()
    coordinator.async_refresh_with_reauth = AsyncMock()
    coordinator.hass = MagicMock()
    return coordinator


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.title = "Ista VDM"
    entry.async_start_reauth = MagicMock()
    return entry


@pytest.fixture
def mock_device_info():
    """Create mock device info."""
    return MagicMock()


async def test_refresh_button(hass: HomeAssistant, mock_coordinator, mock_entry, mock_device_info) -> None:
    """Test refresh button."""
    button = IstaVdmRefreshButton(mock_coordinator, mock_entry, mock_device_info)
    
    assert button.name == "Refresh Data"
    assert button.icon == "mdi:refresh"
    
    await button.async_press()
    
    mock_coordinator.async_refresh_with_reauth.assert_called_once()


async def test_refresh_button_triggers_reauth_on_auth_failure(hass: HomeAssistant, mock_entry, mock_device_info) -> None:
    """Test refresh button triggers re-auth on ConfigEntryAuthFailed."""
    from homeassistant.exceptions import ConfigEntryAuthFailed
    
    coordinator = MagicMock()
    coordinator.async_refresh_with_reauth = AsyncMock(side_effect=ConfigEntryAuthFailed("Auth failed"))
    coordinator.hass = hass
    
    button = IstaVdmRefreshButton(coordinator, mock_entry, mock_device_info)
    
    with pytest.raises(ConfigEntryAuthFailed):
        await button.async_press()
    
    mock_entry.async_start_reauth.assert_called_once_with(hass)


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the button platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "password",
        },
    )
    entry.add_to_hass(hass)
    
    with patch(
        "custom_components.ista_vdm.button.IstaVdmDataUpdateCoordinator",
        autospec=True,
    ) as mock_coordinator_class:
        mock_coordinator = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator
        
        from homeassistant.helpers.entity_registry import EntityRegistry
        
        # Set up the sensor platform first to create the coordinator
        with patch(
            "custom_components.ista_vdm.sensor.IstaVdmAPI",
            autospec=True,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            
            # Now set up the button platform
            from custom_components.ista_vdm import async_setup_entry
            # Button is set up as part of the main setup
