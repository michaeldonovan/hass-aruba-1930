"""Shared fixtures for Aruba 1930 tests.

Home Assistant is not installed in the dev environment, so all HA modules are
stubbed here at import time before any custom-component code is loaded.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Ensure the repo root is on sys.path so aruba1930api is importable.
# ---------------------------------------------------------------------------

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# ---------------------------------------------------------------------------
# Stub Home Assistant modules before any component code is imported.
# ---------------------------------------------------------------------------

# homeassistant.const
_ha_const = MagicMock()
_ha_const.Platform.SWITCH = "switch"
_ha_const.Platform.SENSOR = "sensor"
_ha_const.CONF_HOST = "host"
_ha_const.CONF_PASSWORD = "password"
_ha_const.CONF_USERNAME = "username"
_ha_const.UnitOfPower.WATT = "W"
_ha_const.UnitOfElectricPotential.VOLT = "V"
_ha_const.UnitOfElectricCurrent.AMPERE = "A"
sys.modules["homeassistant.const"] = _ha_const

# homeassistant.core
sys.modules["homeassistant.core"] = MagicMock()

# homeassistant.config_entries
_ha_config_entries = MagicMock()


class _AbortFlow(Exception):
    """Stub for data_entry_flow.AbortFlow raised by _abort_if_unique_id_configured."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _MockConfigFlow:
    """Minimal stub for homeassistant.config_entries.ConfigFlow."""

    def __init_subclass__(cls, domain: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = domain

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        """Raise AbortFlow if this unique_id is already configured."""
        unique_id = getattr(self, "_unique_id", None)
        configured = getattr(self, "_configured_unique_ids", set())
        if unique_id in configured:
            raise _AbortFlow("already_configured")

    def async_create_entry(self, *, title: str, data: dict) -> dict:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: object = None,
        errors: dict | None = None,
    ) -> dict:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_abort(self, *, reason: str) -> dict:
        return {"type": "abort", "reason": reason}


_ha_config_entries.ConfigFlow = _MockConfigFlow
_ha_config_entries.ConfigFlowResult = dict
_ha_config_entries.ConfigEntry = MagicMock()
_ha_config_entries.AbortFlow = _AbortFlow
sys.modules["homeassistant.config_entries"] = _ha_config_entries

# homeassistant.exceptions
_ha_exceptions = MagicMock()


class _ConfigEntryNotReady(Exception):
    """Stub for ConfigEntryNotReady."""


class _ConfigEntryAuthFailed(Exception):
    """Stub for ConfigEntryAuthFailed."""


_ha_exceptions.ConfigEntryNotReady = _ConfigEntryNotReady
_ha_exceptions.ConfigEntryAuthFailed = _ConfigEntryAuthFailed
sys.modules["homeassistant.exceptions"] = _ha_exceptions

# homeassistant.helpers.device_registry
_ha_device_registry = MagicMock()


class _DeviceInfo:
    """Stub for DeviceInfo."""

    def __init__(self, **kwargs: object) -> None:
        self._info = kwargs

    def __repr__(self) -> str:
        return f"DeviceInfo({self._info})"


_ha_device_registry.DeviceInfo = _DeviceInfo
sys.modules["homeassistant.helpers.device_registry"] = _ha_device_registry

# homeassistant.helpers.update_coordinator
_ha_coordinator = MagicMock()


class _CoordinatorEntity:
    """Stub for CoordinatorEntity."""

    def __init__(self, coordinator: object) -> None:
        self.coordinator = coordinator
        self._attr_unique_id: str | None = None
        self._attr_device_info: object = None
        self._attr_name: str | None = None

    @property
    def available(self) -> bool:
        return True

    @property
    def unique_id(self) -> str | None:
        return self._attr_unique_id

    @property
    def device_info(self) -> object:
        return self._attr_device_info

    @property
    def name(self) -> str | None:
        return self._attr_name


class _DataUpdateCoordinator:
    """Stub for DataUpdateCoordinator."""

    # Allow DataUpdateCoordinator[T] subscript syntax.
    def __class_getitem__(cls, item: object) -> type:
        return cls

    def __init__(
        self,
        hass: object,
        logger: object,
        name: str,
        update_interval: object,
    ) -> None:
        self.hass = hass
        self.name = name
        self.update_interval = update_interval
        self.data: list[dict] = []
        self.last_update_success: bool = True

    async def async_request_refresh(self) -> None:
        pass

    async def async_config_entry_first_refresh(self) -> None:
        pass


class _UpdateFailed(Exception):
    """Stub for UpdateFailed."""


_ha_coordinator.CoordinatorEntity = _CoordinatorEntity
_ha_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
_ha_coordinator.UpdateFailed = _UpdateFailed
sys.modules["homeassistant.helpers.update_coordinator"] = _ha_coordinator

# homeassistant.helpers.entity_platform
_ha_entity_platform = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = _ha_entity_platform

# homeassistant.components.switch
_ha_switch = MagicMock()


class _SwitchEntity:
    """Stub for SwitchEntity."""


_ha_switch.SwitchEntity = _SwitchEntity
sys.modules["homeassistant.components.switch"] = _ha_switch

# homeassistant.components.sensor
_ha_sensor = MagicMock()


class _SensorEntity:
    """Stub for SensorEntity."""

    _attr_entity_registry_enabled_default: bool = True
    _attr_native_unit_of_measurement: str | None = None
    _attr_device_class: object = None
    _attr_state_class: object = None
    _attr_options: list | None = None

    @property
    def native_value(self) -> object:
        return None


class _SensorDeviceClass:
    POWER = "power"
    VOLTAGE = "voltage"
    CURRENT = "current"
    ENUM = "enum"


class _SensorStateClass:
    MEASUREMENT = "measurement"


_ha_sensor.SensorEntity = _SensorEntity
_ha_sensor.SensorDeviceClass = _SensorDeviceClass
_ha_sensor.SensorStateClass = _SensorStateClass
sys.modules["homeassistant.components.sensor"] = _ha_sensor

# ---------------------------------------------------------------------------
# Now that all HA stubs are installed, import pytest and define fixtures.
# ---------------------------------------------------------------------------

import pytest  # noqa: E402

SAMPLE_PORTS = [
    {
        "id": 1,
        "name": "1",
        "poe_enabled": True,
        "detection_status": 3,
        "voltage_mv": 55000,
        "current_ma": 152,
        "power_mw": 8300,
        "power_limit_mw": 30000,
        "priority": 1,
    },
    {
        "id": 2,
        "name": "2",
        "poe_enabled": False,
        "detection_status": 2,
        "voltage_mv": 0,
        "current_ma": 0,
        "power_mw": 0,
        "power_limit_mw": 30000,
        "priority": 2,
    },
]


@pytest.fixture
def mock_switch_client() -> MagicMock:
    """Return a mock SwitchClient with realistic port data."""
    client = MagicMock()
    client.login = AsyncMock()
    client.logout = AsyncMock()
    client.get_ports = AsyncMock(return_value=list(SAMPLE_PORTS))
    client.set_poe = AsyncMock()
    return client


@pytest.fixture
def mock_coordinator(mock_switch_client: MagicMock) -> _DataUpdateCoordinator:
    """Return a pre-populated coordinator stub."""
    coordinator = _DataUpdateCoordinator(hass=None, logger=None, name="test", update_interval=None)
    coordinator.client = mock_switch_client
    coordinator.data = list(SAMPLE_PORTS)
    return coordinator
