"""Base entity classes for Aruba 1930."""

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class Aruba1930DeviceEntity(CoordinatorEntity):
    """Base entity bound to the Aruba 1930 device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the base device entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Aruba 1930",
            manufacturer="Aruba",
            model="1930",
        )


class Aruba1930Entity(Aruba1930DeviceEntity):
    """Base entity for an Aruba 1930 port."""

    def __init__(self, coordinator, port_id: int, entry_id: str) -> None:
        """Initialize the base port entity.

        Args:
            coordinator: The Aruba1930Coordinator instance.
            port_id: The switch interface ID for this port.
            entry_id: The config entry ID for deduplication.
        """
        super().__init__(coordinator, entry_id)
        self._port_id = port_id

    @property
    def port_data(self) -> dict[str, Any] | None:
        """Return the coordinator data dict for this port, or None."""
        return next(
            (p for p in self.coordinator.data if p["id"] == self._port_id),
            None,
        )

    @property
    def available(self) -> bool:
        """Entity is available if coordinator succeeded and port exists in data."""
        return super().available and self.port_data is not None
