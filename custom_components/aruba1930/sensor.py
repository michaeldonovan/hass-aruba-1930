"""Sensor platform for Aruba 1930 integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DETECTION_STATUS_MAP, DOMAIN
from .entity import Aruba1930DeviceEntity, Aruba1930Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aruba 1930 sensors from a config entry."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime_data.coordinator

    sensors: list[SensorEntity] = [Aruba1930TotalPowerSensor(coordinator, entry.entry_id)]
    for port in coordinator.data:
        port_id = port["id"]
        sensors.append(Aruba1930PowerSensor(coordinator, port_id, entry.entry_id))
        sensors.append(Aruba1930StatusSensor(coordinator, port_id, entry.entry_id))
        sensors.append(Aruba1930VoltageSensor(coordinator, port_id, entry.entry_id))
        sensors.append(Aruba1930CurrentSensor(coordinator, port_id, entry.entry_id))

    async_add_entities(sensors)


class Aruba1930TotalPowerSensor(Aruba1930DeviceEntity, SensorEntity):
    """Total PoE power usage sensor for the switch."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_total_poe_power"
        self._attr_name = "Total PoE Power"

    @property
    def native_value(self) -> float | None:
        """Return the total power draw in watts."""
        if self.coordinator.data is None:
            return None
        return sum(port["power_mw"] for port in self.coordinator.data) / 1000.0


class Aruba1930PowerSensor(Aruba1930Entity, SensorEntity):
    """Power sensor for an Aruba 1930 port."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, port_id: int, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, port_id, entry_id)
        self._attr_unique_id = f"{entry_id}_port_{port_id}_power"
        self._attr_name = f"Port {port_id} Power"

    @property
    def native_value(self) -> float | None:
        """Return the power draw in watts."""
        port = self.port_data
        if port is None:
            return None
        return port["power_mw"] / 1000.0


class Aruba1930StatusSensor(Aruba1930Entity, SensorEntity):
    """Status sensor for an Aruba 1930 port."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["none", "delivering_power", "unknown"]

    def __init__(self, coordinator, port_id: int, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, port_id, entry_id)
        self._attr_unique_id = f"{entry_id}_port_{port_id}_status"
        self._attr_name = f"Port {port_id} Status"

    @property
    def native_value(self) -> str | None:
        """Return the detection status as a string."""
        port = self.port_data
        if port is None:
            return None
        return DETECTION_STATUS_MAP.get(port["detection_status"], "unknown")


class Aruba1930VoltageSensor(Aruba1930Entity, SensorEntity):
    """Voltage sensor for an Aruba 1930 port."""

    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, port_id: int, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, port_id, entry_id)
        self._attr_unique_id = f"{entry_id}_port_{port_id}_voltage"
        self._attr_name = f"Port {port_id} Voltage"

    @property
    def native_value(self) -> float | None:
        """Return the voltage in volts."""
        port = self.port_data
        if port is None:
            return None
        return port["voltage_mv"] / 1000.0


class Aruba1930CurrentSensor(Aruba1930Entity, SensorEntity):
    """Current sensor for an Aruba 1930 port."""

    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, port_id: int, entry_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, port_id, entry_id)
        self._attr_unique_id = f"{entry_id}_port_{port_id}_current"
        self._attr_name = f"Port {port_id} Current"

    @property
    def native_value(self) -> float | None:
        """Return the current in amperes."""
        port = self.port_data
        if port is None:
            return None
        return port["current_ma"] / 1000.0
