"""Config flow for ista VDM integration."""

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from ista_vdm_api import IstaVdmAPI, IstaVdmAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Args:
        hass: Home Assistant instance
        data: User input data
        
    Returns:
        Dictionary with validated data
        
    Raises:
        CannotConnect: If connection fails
        InvalidAuth: If authentication fails
    """
    api = IstaVdmAPI(data[CONF_EMAIL], data[CONF_PASSWORD])
    
    try:
        async with api:
            if not await api.authenticate():
                raise InvalidAuth
            
            # Get consumption data to verify everything works
            consumption_data = await api.get_consumption_data()
            
            if not consumption_data:
                _LOGGER.warning("No consumption data found, but authentication successful")
            
            return {
                "title": f"Ista VDM ({data[CONF_EMAIL]})",
                "flat_id": api.flat_id,
                "user_id": api.user_id,
            }
    except IstaVdmAuthError as e:
        _LOGGER.error(f"Authentication error: {e}")
        raise InvalidAuth from e
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Connection error: {e}")
        raise CannotConnect from e
    except Exception as e:
        _LOGGER.exception(f"Unexpected error: {e}")
        raise CannotConnect from e


class IstaVDMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ista VDM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()
            
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)
        
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauthorization request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Get the existing entry
            entry = self.hass.config_entries.async_get_entry(
                self.context.get("entry_id")
            )
            if entry is None:
                return self.async_abort(reason="reauth_failed")
            
            # Merge existing data with new password
            new_data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            
            try:
                # Validate the credentials
                await validate_input(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                # Update the entry with new data
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
            description_placeholders={"email": self.context.get("email", "")},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ista VDM."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""