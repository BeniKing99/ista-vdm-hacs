"""Test the ista VDM sensor platform."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ista_vdm.api import ConsumptionData
from custom_components.ista_vdm.const import DOMAIN
from custom_components.ista_vdm.sensor import (
    IstaVdmFlatCitySensor,
    IstaVdmHeatingSensor,
    IstaVdmHotWaterSensor,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = [
        ConsumptionData(
            period_start=date(2025, 12, 1),
            period_end=date(2025, 12, 31),
            heating_consumption=392.1,
            heating_cost=None,
            hot_water_consumption=0.26,
            hot_water_cost=None,
        ),
        ConsumptionData(
            period_start=date(2025, 11, 1),
            period_end=date(2025, 11, 30),
            heating_consumption=327.8,
            heating_cost=None,
            hot_water_consumption=0.29,
            hot_water_cost=None,
        ),
    ]
    coordinator.flat_info = {
        "city": "Vienna",
        "street": "Test Street",
        "housenumber": "123",
        "door": "4",
        "squaremeter": 56.9,
        "postalcode": "1010",
    }
    return coordinator


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        "email": "test@example.com",
        "password": "password",
    }
    return entry


@pytest.fixture
def mock_device_info():
    """Create mock device info."""
    return MagicMock()


async def test_heating_sensor(hass: HomeAssistant, mock_coordinator, mock_entry, mock_device_info) -> None:
    """Test heating sensor."""
    sensor = IstaVdmHeatingSensor(mock_coordinator, mock_entry, mock_device_info)
    
    assert sensor.name == "Heating Consumption"
    assert sensor.device_class == "energy"
    assert sensor.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
    assert sensor.state_class == "total"
    
    # Test native_value returns latest
    assert sensor.native_value == 392.1
    
    # Test attributes
    attrs = sensor.extra_state_attributes
    assert attrs["total_months"] == 2
    assert len(attrs["history"]) == 2
    assert attrs["period_start"] == "2025-12-01"


async def test_hot_water_sensor(hass: HomeAssistant, mock_coordinator, mock_entry, mock_device_info) -> None:
    """Test hot water sensor."""
    sensor = IstaVdmHotWaterSensor(mock_coordinator, mock_entry, mock_device_info)
    
    assert sensor.name == "Hot Water Consumption"
    assert sensor.device_class == "water"
    assert sensor.native_unit_of_measurement == UnitOfVolume.CUBIC_METERS
    assert sensor.state_class == "total"
    
    # Test native_value returns latest
    assert sensor.native_value == 0.26
    
    # Test attributes
    attrs = sensor.extra_state_attributes
    assert attrs["total_months"] == 2
    assert len(attrs["history"]) == 2


async def test_flat_city_sensor(hass: HomeAssistant, mock_coordinator, mock_entry, mock_device_info) -> None:
    """Test flat city sensor."""
    sensor = IstaVdmFlatCitySensor(mock_coordinator, mock_entry, mock_device_info)
    
    assert sensor.name == "City"
    assert sensor.native_value == "Vienna"


async def test_sensor_no_data(hass: HomeAssistant, mock_entry, mock_device_info) -> None:
    """Test sensors handle no data gracefully."""
    coordinator = MagicMock()
    coordinator.data = None
    
    sensor = IstaVdmHeatingSensor(coordinator, mock_entry, mock_device_info)
    assert sensor.native_value is None


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the sensor platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test@example.com",
            "password": "password",
        },
    )
    entry.add_to_hass(hass)
    
    with patch(
        "custom_components.ista_vdm.sensor.IstaVdmAPI",
        autospec=True,
    ) as mock_api:
        api_instance = AsyncMock()
        api_instance.authenticate = AsyncMock(return_value=True)
        api_instance.get_consumption_data = AsyncMock(return_value=[
            ConsumptionData(
                period_start=date(2025, 12, 1),
                period_end=date(2025, 12, 31),
                heating_consumption=392.1,
                heating_cost=None,
                hot_water_consumption=0.26,
                hot_water_cost=None,
            ),
        ])
        api_instance.get_flat_info = AsyncMock(return_value={
            "city": "Vienna",
            "street": "Test Street",
        })
        mock_api.return_value = api_instance
        
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        
        # Check sensors were created
        entity_registry = EntityRegistry.async_get(hass)
        entities = [
            entity for entity in entity_registry.entities.values()
            if entity.config_entry_id == entry.entry_id
        ]
        
        # Should have 9 entities (2 consumption + 6 flat info + 1 last updated)
        assert len(entities) == 9
