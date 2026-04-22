"""Switch platform for Aruba 1930 integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import Aruba1930Entity
from .switch_client import AuthError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aruba 1930 switches from a config entry."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime_data.coordinator

    switches = [
        Aruba1930PortSwitch(coordinator, port["id"], entry.entry_id) for port in coordinator.data
    ]

    async_add_entities(switches)


class Aruba1930PortSwitch(Aruba1930Entity, SwitchEntity):
    """Representation of a PoE switch on an Aruba 1930 port."""

    def __init__(self, coordinator, port_id: int, entry_id: str) -> None:
        """Initialize the switch.

        Args:
            coordinator: The Aruba1930Coordinator instance.
            port_id: The switch interface ID for this port.
            entry_id: The config entry ID for deduplication.
        """
        super().__init__(coordinator, port_id, entry_id)
        self._attr_unique_id = f"{entry_id}_port_{port_id}_poe"
        self._attr_name = f"Port {port_id} PoE"

    @property
    def is_on(self) -> bool | None:
        """Return True if PoE is enabled on this port."""
        port = self.port_data
        if port is None:
            return None
        return port["poe_enabled"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable PoE on this port."""
        try:
            await self.coordinator.client.set_poe(self._port_id, True)
        except AuthError as exc:
            raise ConfigEntryAuthFailed(f"Authentication failed: {exc}") from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable PoE on this port."""
        try:
            await self.coordinator.client.set_poe(self._port_id, False)
        except AuthError as exc:
            raise ConfigEntryAuthFailed(f"Authentication failed: {exc}") from exc
        await self.coordinator.async_request_refresh()
