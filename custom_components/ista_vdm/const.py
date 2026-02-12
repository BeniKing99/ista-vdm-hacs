"""Constants for the ista VDM integration."""

from homeassistant.const import Platform

DOMAIN = "ista_vdm"
PLATFORMS: list[Platform] = [Platform.SENSOR]

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Update interval (once per day since data is only updated monthly)
UPDATE_INTERVAL = 86400  # 24 hours in seconds

# Default sensor names
DEFAULT_NAME = "Ista VDM"

# API Constants
BASE_URL = "https://ista-vdm.at"
LOGIN_URL = "https://login.ista.com/realms/vdm/protocol/openid-connect/auth"
TOKEN_URL = "https://login.ista.com/realms/vdm/protocol/openid-connect/token"