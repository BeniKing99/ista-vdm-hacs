"""Application credentials platform for ista VDM.

This module handles OAuth application credentials for the ista VDM integration.
"""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

# OAuth2 endpoints for ista VDM (Keycloak)
AUTHORIZATION_SERVER = AuthorizationServer(
    authorize_url="https://login.ista.com/realms/vdm/protocol/openid-connect/auth",
    token_url="https://login.ista.com/realms/vdm/protocol/openid-connect/token",
)

CLIENT_ID = "vdm-frontend"


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AUTHORIZATION_SERVER


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "oauth_creds_url": "https://ista-vdm.at/",
        "oauth_creds_help": "Log in to your ista VDM portal to obtain credentials.",
    }