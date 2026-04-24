"""Tests for the Aruba 1930 sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.aruba1930.sensor import (
    Aruba1930CurrentSensor,
    Aruba1930PowerSensor,
    Aruba1930StatusSensor,
    Aruba1930TotalPowerSensor,
    Aruba1930VoltageSensor,
)

ENTRY_ID = "test_entry_id"


# ---------------------------------------------------------------------------
# Total power sensor
# ---------------------------------------------------------------------------


async def test_total_power_sensor_value(mock_coordinator: MagicMock) -> None:
    """Total power sensor sums per-port power in watts."""
    sensor = Aruba1930TotalPowerSensor(mock_coordinator, ENTRY_ID)
    assert sensor.native_value == pytest.approx(8.3)


async def test_total_power_sensor_updates_with_multiple_ports(
    mock_coordinator: MagicMock,
) -> None:
    """Total power sensor includes all ports in the coordinator data."""
    mock_coordinator.data.append(
        {
            "id": 3,
            "name": "3",
            "poe_enabled": True,
            "detection_status": 3,
            "voltage_mv": 54000,
            "current_ma": 200,
            "power_mw": 10800,
            "power_limit_mw": 30000,
            "priority": 1,
        }
    )
    sensor = Aruba1930TotalPowerSensor(mock_coordinator, ENTRY_ID)
    assert sensor.native_value == pytest.approx(19.1)


async def test_total_power_sensor_enabled_by_default(
    mock_coordinator: MagicMock,
) -> None:
    """Total power sensor is enabled by default."""
    sensor = Aruba1930TotalPowerSensor(mock_coordinator, ENTRY_ID)
    assert sensor._attr_entity_registry_enabled_default is True


# ---------------------------------------------------------------------------
# Power sensor
# ---------------------------------------------------------------------------


async def test_power_sensor_value(mock_coordinator: MagicMock) -> None:
    """Power sensor converts mW to W."""
    sensor = Aruba1930PowerSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor.native_value == pytest.approx(8.3)


async def test_power_sensor_zero_when_off(mock_coordinator: MagicMock) -> None:
    """Power sensor is 0 W when the port has no device."""
    sensor = Aruba1930PowerSensor(mock_coordinator, 2, ENTRY_ID)
    assert sensor.native_value == pytest.approx(0.0)


async def test_power_sensor_none_when_port_missing(mock_coordinator: MagicMock) -> None:
    """Power sensor returns None for an unknown port."""
    sensor = Aruba1930PowerSensor(mock_coordinator, 99, ENTRY_ID)
    assert sensor.native_value is None


async def test_power_sensor_enabled_by_default(mock_coordinator: MagicMock) -> None:
    """Power sensor is enabled by default."""
    sensor = Aruba1930PowerSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor._attr_entity_registry_enabled_default is True


# ---------------------------------------------------------------------------
# Status sensor
# ---------------------------------------------------------------------------


async def test_status_sensor_delivering(mock_coordinator: MagicMock) -> None:
    """Status sensor maps detection_status=3 to 'delivering_power'."""
    sensor = Aruba1930StatusSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor.native_value == "delivering_power"


async def test_status_sensor_none(mock_coordinator: MagicMock) -> None:
    """Status sensor maps detection_status=2 to 'none'."""
    sensor = Aruba1930StatusSensor(mock_coordinator, 2, ENTRY_ID)
    assert sensor.native_value == "none"


async def test_status_sensor_unknown_fallback(mock_coordinator: MagicMock) -> None:
    """Status sensor maps unknown detection_status to 'unknown'."""
    mock_coordinator.data[0]["detection_status"] = 999
    sensor = Aruba1930StatusSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor.native_value == "unknown"


async def test_status_sensor_enabled_by_default(mock_coordinator: MagicMock) -> None:
    """Status sensor is enabled by default."""
    sensor = Aruba1930StatusSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor._attr_entity_registry_enabled_default is True


async def test_status_sensor_device_class_is_enum(mock_coordinator: MagicMock) -> None:
    """Status sensor has ENUM device class so HA knows the valid option set."""
    sensor = Aruba1930StatusSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor._attr_device_class == "enum"


# ---------------------------------------------------------------------------
# Voltage sensor
# ---------------------------------------------------------------------------


async def test_voltage_sensor_value(mock_coordinator: MagicMock) -> None:
    """Voltage sensor converts mV to V."""
    sensor = Aruba1930VoltageSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor.native_value == pytest.approx(55.0)


async def test_voltage_sensor_disabled_by_default(mock_coordinator: MagicMock) -> None:
    """Voltage sensor is disabled by default."""
    sensor = Aruba1930VoltageSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor._attr_entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# Current sensor
# ---------------------------------------------------------------------------


async def test_current_sensor_value(mock_coordinator: MagicMock) -> None:
    """Current sensor converts mA to A."""
    sensor = Aruba1930CurrentSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor.native_value == pytest.approx(0.152)


async def test_current_sensor_disabled_by_default(mock_coordinator: MagicMock) -> None:
    """Current sensor is disabled by default."""
    sensor = Aruba1930CurrentSensor(mock_coordinator, 1, ENTRY_ID)
    assert sensor._attr_entity_registry_enabled_default is False


# ---------------------------------------------------------------------------
# Common: unique_id and device_info
# ---------------------------------------------------------------------------


async def test_sensor_unique_ids(mock_coordinator: MagicMock) -> None:
    """All sensors get distinct unique IDs."""
    ids = [
        Aruba1930TotalPowerSensor(mock_coordinator, ENTRY_ID).unique_id,
        Aruba1930PowerSensor(mock_coordinator, 1, ENTRY_ID).unique_id,
        Aruba1930StatusSensor(mock_coordinator, 1, ENTRY_ID).unique_id,
        Aruba1930VoltageSensor(mock_coordinator, 1, ENTRY_ID).unique_id,
        Aruba1930CurrentSensor(mock_coordinator, 1, ENTRY_ID).unique_id,
    ]
    assert ids == [
        f"{ENTRY_ID}_total_poe_power",
        f"{ENTRY_ID}_port_1_power",
        f"{ENTRY_ID}_port_1_status",
        f"{ENTRY_ID}_port_1_voltage",
        f"{ENTRY_ID}_port_1_current",
    ]


async def test_sensor_device_info_not_none(mock_coordinator: MagicMock) -> None:
    """All sensors have device_info set."""
    total_sensor = Aruba1930TotalPowerSensor(mock_coordinator, ENTRY_ID)
    assert total_sensor.device_info is not None

    for cls in (
        Aruba1930PowerSensor,
        Aruba1930StatusSensor,
        Aruba1930VoltageSensor,
        Aruba1930CurrentSensor,
    ):
        sensor = cls(mock_coordinator, 1, ENTRY_ID)
        assert sensor.device_info is not None
