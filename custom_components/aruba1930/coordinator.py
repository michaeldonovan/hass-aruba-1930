"""DataUpdateCoordinator for Aruba 1930."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL
from .switch_client import AuthError

_LOGGER = logging.getLogger(__name__)


class Aruba1930Coordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator to manage fetching data from the Aruba 1930 switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Any,
        poll_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: The Home Assistant instance.
            client: The SwitchClient instance.
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Aruba 1930",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from the switch."""
        try:
            return await self.client.get_ports()
        except AuthError as exc:
            raise ConfigEntryAuthFailed(f"Authentication failed: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"Failed to communicate with switch: {exc}") from exc
