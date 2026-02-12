"""Test the ista VDM integration initialization."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ista_vdm.const import DOMAIN


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "password",
        },
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)
    
    with patch(
        "custom_components.ista_vdm.IstaVdmAPI",
        autospec=True,
    ) as mock_api:
        api_instance = AsyncMock()
        api_instance.authenticate = AsyncMock(return_value=True)
        api_instance.get_consumption_data = AsyncMock(return_value=[])
        api_instance.get_flat_info = AsyncMock(return_value={})
        mock_api.return_value = api_instance
        
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        
        assert entry.state == ConfigEntryState.LOADED


async def test_setup_entry_auth_failure(hass: HomeAssistant) -> None:
    """Test setup fails on authentication error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "wrong_password",
        },
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)
    
    with patch(
        "custom_components.ista_vdm.IstaVdmAPI.authenticate",
        side_effect=Exception("Auth failed"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        
        assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "password",
        },
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)
    
    with patch(
        "custom_components.ista_vdm.IstaVdmAPI",
        autospec=True,
    ) as mock_api:
        api_instance = AsyncMock()
        api_instance.authenticate = AsyncMock(return_value=True)
        api_instance.get_consumption_data = AsyncMock(return_value=[])
        api_instance.get_flat_info = AsyncMock(return_value={})
        mock_api.return_value = api_instance
        
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        
        assert entry.state == ConfigEntryState.LOADED
        
        # Unload the entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        
        assert entry.state == ConfigEntryState.NOT_LOADED


async def test_reload_entry(hass: HomeAssistant) -> None:
    """Test reloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "password",
        },
        unique_id="test@example.com",
    )
    entry.add_to_hass(hass)
    
    with patch(
        "custom_components.ista_vdm.IstaVdmAPI",
        autospec=True,
    ) as mock_api:
        api_instance = AsyncMock()
        api_instance.authenticate = AsyncMock(return_value=True)
        api_instance.get_consumption_data = AsyncMock(return_value=[])
        api_instance.get_flat_info = AsyncMock(return_value={})
        mock_api.return_value = api_instance
        
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        
        assert entry.state == ConfigEntryState.LOADED
        
        # Reload the entry
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        
        assert entry.state == ConfigEntryState.LOADED
