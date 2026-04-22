"""Constants for the Aruba 1930 integration."""

from dataclasses import dataclass
from typing import Any

from homeassistant.const import Platform

DOMAIN = "aruba1930"
PLATFORMS = [Platform.SWITCH, Platform.SENSOR]
DEFAULT_SCAN_INTERVAL = 30

# Config entry keys (not provided by homeassistant.const)
CONF_SESSION_PATH = "session_path"
CONF_VERIFY_SSL = "verify_ssl"

# Port detection status mapping for the status sensor
DETECTION_STATUS_MAP = {
    2: "none",
    3: "delivering_power",
}


@dataclass
class Aruba1930RuntimeData:
    """Runtime data stored in hass.data[DOMAIN][entry_id]."""

    client: Any  # SwitchClient, typed as Any to avoid import at module load
    coordinator: Any  # Aruba1930Coordinator, typed as Any for same reason
