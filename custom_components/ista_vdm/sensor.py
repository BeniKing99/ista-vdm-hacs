"""Platform for ista VDM sensor integration."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from ista_vdm_api import ConsumptionData, IstaVdmAPI, IstaVdmAuthError, IstaVdmError

from . import IstaVdmConfigEntry
from .const import DOMAIN, PLATFORMS, UPDATE_INTERVAL

# Parallel updates - set to 0 to allow parallel updates
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)


class IstaVdmDataUpdateCoordinator(DataUpdateCoordinator[list[ConsumptionData]]):
    """Data update coordinator for ista VDM."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: IstaVdmAPI,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.api = api
        self.entry = entry
        self.flat_info: dict[str, Any] | None = None
        self.last_update_success_time: datetime | None = None

    async def _async_update_data(self) -> list[ConsumptionData]:
        """Fetch data from ista VDM API."""
        _LOGGER.debug("Starting data update for %s", self.entry.title)
        try:
            async with self.api:
                if not self.api.is_authenticated:
                    _LOGGER.debug("API not authenticated, authenticating...")
                    await self.api.authenticate()
                
                # Get flat info for static sensors (only once)
                if self.flat_info is None:
                    _LOGGER.debug("Fetching flat info...")
                    self.flat_info = await self.api.get_flat_info()
                    _LOGGER.debug("Flat info retrieved: %s", self.flat_info)
                
                # Get all consumption data
                _LOGGER.debug("Fetching consumption data...")
                data = await self.api.get_consumption_data()
                _LOGGER.debug("Retrieved %d consumption records", len(data))
                
                # Log the latest data for debugging
                if data:
                    latest = max(data, key=lambda x: x.period_end)
                    _LOGGER.debug(
                        "Latest data: period=%s to %s, heating=%s kWh, hot_water=%s m³",
                        latest.period_start,
                        latest.period_end,
                        latest.heating_consumption,
                        latest.hot_water_consumption
                    )
                
                # Update last success time
                self.last_update_success_time = dt_util.utcnow()
                
                return data
                
        except IstaVdmAuthError as err:
            _LOGGER.error(
                "Authentication failed for %s: %s. Triggering re-authentication.",
                self.entry.title,
                err
            )
            raise ConfigEntryAuthFailed from err
        except IstaVdmError as err:
            _LOGGER.error("Ista VDM error for %s: %s", self.entry.title, err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error updating data for %s: %s", self.entry.title, err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def async_refresh_with_reauth(self) -> None:
        """Force a refresh with full re-authentication."""
        _LOGGER.info("Forcing full re-authentication for %s", self.entry.title)
        # Force the API to re-authenticate by clearing tokens
        self.api._access_token = None
        self.api._refresh_token = None
        self.api._token_expires = None
        # Now trigger a normal refresh which will re-authenticate
        await self.async_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IstaVdmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ista VDM sensor based on a config entry."""
    api = entry.runtime_data
    
    coordinator = IstaVdmDataUpdateCoordinator(hass, api, entry)
    
    # Store coordinator in hass.data for access by other platforms
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Create device info from flat info
    device_info = _create_device_info(coordinator.flat_info, entry)
    
    # Create sensors
    entities: list[IstaVdmBaseSensor] = [
        IstaVdmHeatingSensor(coordinator, entry, device_info),
        IstaVdmHotWaterSensor(coordinator, entry, device_info),
        IstaVdmLastUpdatedSensor(coordinator, entry, device_info),
    ]
    
    # Add flat detail sensors (static info)
    if coordinator.flat_info:
        entities.extend([
            IstaVdmFlatCitySensor(coordinator, entry, device_info),
            IstaVdmFlatStreetSensor(coordinator, entry, device_info),
            IstaVdmFlatHouseNumberSensor(coordinator, entry, device_info),
            IstaVdmFlatDoorSensor(coordinator, entry, device_info),
            IstaVdmFlatSquareMeterSensor(coordinator, entry, device_info),
            IstaVdmFlatPostalCodeSensor(coordinator, entry, device_info),
        ])
    
    async_add_entities(entities)


def _create_device_info(
    flat_info: dict[str, Any] | None,
    entry: ConfigEntry,
) -> DeviceInfo:
    """Create device info from flat information."""
    if flat_info:
        # Build address string
        address_parts = [
            flat_info.get("street"),
            flat_info.get("housenumber"),
        ]
        address = " ".join(filter(None, address_parts))
        
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Ista VDM - {address}" if address else "Ista VDM",
            manufacturer="ista",
            model="VDM",
            configuration_url="https://ista-vdm.at/",
            sw_version=None,
            hw_version=None,
        )
    
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Ista VDM",
        manufacturer="ista",
        model="VDM",
        configuration_url="https://ista-vdm.at/",
    )


class IstaVdmBaseSensor(CoordinatorEntity[IstaVdmDataUpdateCoordinator], SensorEntity):
    """Base class for ista VDM sensors."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = device_info


class IstaVdmLastUpdatedSensor(IstaVdmBaseSensor):
    """Sensor for last updated timestamp."""

    entity_description = SensorEntityDescription(
        key="last_updated",
        name="Last Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_last_updated"

    @property
    def native_value(self) -> datetime | None:
        """Return the last update timestamp."""
        return self.coordinator.last_update_success_time


class IstaVdmHeatingSensor(IstaVdmBaseSensor):
    """Sensor for heating consumption."""

    entity_description = SensorEntityDescription(
        key="heating_consumption",
        name="Heating Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:radiator",
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the heating sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_heating_consumption"

    @property
    def native_value(self) -> float | None:
        """Return the latest consumption value."""
        if self.coordinator.data:
            latest = max(self.coordinator.data, key=lambda x: x.period_end)
            return latest.heating_consumption
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return historical data in attributes."""
        attrs: dict[str, Any] = {}
        
        if self.coordinator.data:
            sorted_data = sorted(
                self.coordinator.data, key=lambda x: x.period_start, reverse=True
            )
            
            latest = sorted_data[0]
            attrs["period_start"] = latest.period_start.isoformat()
            attrs["period_end"] = latest.period_end.isoformat()
            
            history = [
                {
                    "period_start": c.period_start.isoformat(),
                    "period_end": c.period_end.isoformat(),
                    "consumption_kwh": c.heating_consumption,
                }
                for c in sorted_data
            ]
            attrs["history"] = history
            attrs["total_months"] = len(history)
        
        return attrs


class IstaVdmHotWaterSensor(IstaVdmBaseSensor):
    """Sensor for hot water consumption."""

    entity_description = SensorEntityDescription(
        key="hot_water_consumption",
        name="Hot Water Consumption",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:water-boiler",
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the hot water sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_hot_water_consumption"

    @property
    def native_value(self) -> float | None:
        """Return the latest consumption value."""
        if self.coordinator.data:
            latest = max(self.coordinator.data, key=lambda x: x.period_end)
            return latest.hot_water_consumption
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return historical data in attributes."""
        attrs: dict[str, Any] = {}
        
        if self.coordinator.data:
            sorted_data = sorted(
                self.coordinator.data, key=lambda x: x.period_start, reverse=True
            )
            
            latest = sorted_data[0]
            attrs["period_start"] = latest.period_start.isoformat()
            attrs["period_end"] = latest.period_end.isoformat()
            
            history = [
                {
                    "period_start": c.period_start.isoformat(),
                    "period_end": c.period_end.isoformat(),
                    "consumption_m3": c.hot_water_consumption,
                }
                for c in sorted_data
            ]
            attrs["history"] = history
            attrs["total_months"] = len(history)
        
        return attrs


# Flat detail sensors (static information, diagnostic category)

class IstaVdmFlatCitySensor(IstaVdmBaseSensor):
    """Sensor for flat city."""

    entity_description = SensorEntityDescription(
        key="flat_city",
        name="City",
        icon="mdi:city",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_flat_city"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.flat_info:
            return self.coordinator.flat_info.get("city")
        return None


class IstaVdmFlatStreetSensor(IstaVdmBaseSensor):
    """Sensor for flat street."""

    entity_description = SensorEntityDescription(
        key="flat_street",
        name="Street",
        icon="mdi:road",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_flat_street"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.flat_info:
            return self.coordinator.flat_info.get("street")
        return None


class IstaVdmFlatHouseNumberSensor(IstaVdmBaseSensor):
    """Sensor for flat house number."""

    entity_description = SensorEntityDescription(
        key="flat_housenumber",
        name="House Number",
        icon="mdi:numeric",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_flat_housenumber"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.flat_info:
            return self.coordinator.flat_info.get("housenumber")
        return None


class IstaVdmFlatDoorSensor(IstaVdmBaseSensor):
    """Sensor for flat door number."""

    entity_description = SensorEntityDescription(
        key="flat_door",
        name="Door",
        icon="mdi:door",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_flat_door"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.flat_info:
            return self.coordinator.flat_info.get("door")
        return None


class IstaVdmFlatSquareMeterSensor(IstaVdmBaseSensor):
    """Sensor for flat square meters."""

    entity_description = SensorEntityDescription(
        key="flat_squaremeter",
        name="Square Meters",
        icon="mdi:ruler-square",
        native_unit_of_measurement="m²",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_flat_squaremeter"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.flat_info:
            return self.coordinator.flat_info.get("squaremeter")
        return None


class IstaVdmFlatPostalCodeSensor(IstaVdmBaseSensor):
    """Sensor for flat postal code."""

    entity_description = SensorEntityDescription(
        key="flat_postalcode",
        name="Postal Code",
        icon="mdi:mailbox",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(
        self,
        coordinator: IstaVdmDataUpdateCoordinator,
        entry: ConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, device_info)
        self._attr_unique_id = f"{entry.entry_id}_flat_postalcode"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.flat_info:
            return self.coordinator.flat_info.get("postalcode")
        return None