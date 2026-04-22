"""Tests for the Aruba 1930 switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.aruba1930.switch import Aruba1930PortSwitch
from custom_components.aruba1930.switch_client import AuthError
from tests.conftest import _ConfigEntryAuthFailed

ENTRY_ID = "test_entry_id"


async def test_switch_is_on(mock_coordinator: MagicMock) -> None:
    """Switch reflects poe_enabled=True for port 1."""
    switch = Aruba1930PortSwitch(mock_coordinator, 1, ENTRY_ID)
    assert switch.is_on is True


async def test_switch_is_off(mock_coordinator: MagicMock) -> None:
    """Switch reflects poe_enabled=False for port 2."""
    switch = Aruba1930PortSwitch(mock_coordinator, 2, ENTRY_ID)
    assert switch.is_on is False


async def test_switch_is_none_for_missing_port(mock_coordinator: MagicMock) -> None:
    """Switch is_on is None when port is not in coordinator data."""
    switch = Aruba1930PortSwitch(mock_coordinator, 99, ENTRY_ID)
    assert switch.is_on is None


async def test_switch_turn_on(mock_coordinator: MagicMock) -> None:
    """async_turn_on calls set_poe(True) and requests a refresh."""
    switch = Aruba1930PortSwitch(mock_coordinator, 1, ENTRY_ID)
    await switch.async_turn_on()
    mock_coordinator.client.set_poe.assert_awaited_once_with(1, True)


async def test_switch_turn_on_auth_error_raises_config_entry_auth_failed(
    mock_coordinator: MagicMock,
) -> None:
    """AuthError during writes becomes ConfigEntryAuthFailed."""
    mock_coordinator.client.set_poe.side_effect = AuthError("bad creds")
    switch = Aruba1930PortSwitch(mock_coordinator, 1, ENTRY_ID)

    with pytest.raises(_ConfigEntryAuthFailed):
        await switch.async_turn_on()


async def test_switch_turn_off_auth_error_raises_config_entry_auth_failed(
    mock_coordinator: MagicMock,
) -> None:
    """AuthError during writes becomes ConfigEntryAuthFailed."""
    mock_coordinator.client.set_poe.side_effect = AuthError("bad creds")
    switch = Aruba1930PortSwitch(mock_coordinator, 1, ENTRY_ID)

    with pytest.raises(_ConfigEntryAuthFailed):
        await switch.async_turn_off()


async def test_switch_turn_off(mock_coordinator: MagicMock) -> None:
    """async_turn_off calls set_poe(False) and requests a refresh."""
    switch = Aruba1930PortSwitch(mock_coordinator, 2, ENTRY_ID)
    await switch.async_turn_off()
    mock_coordinator.client.set_poe.assert_awaited_once_with(2, False)


async def test_switch_unique_id(mock_coordinator: MagicMock) -> None:
    """unique_id follows the expected pattern."""
    switch = Aruba1930PortSwitch(mock_coordinator, 3, ENTRY_ID)
    assert switch.unique_id == f"{ENTRY_ID}_port_3_poe"


async def test_switch_name(mock_coordinator: MagicMock) -> None:
    """name uses the port ID."""
    switch = Aruba1930PortSwitch(mock_coordinator, 5, ENTRY_ID)
    assert switch.name == "Port 5 PoE"


async def test_switch_device_info_not_none(mock_coordinator: MagicMock) -> None:
    """device_info is set and not None."""
    switch = Aruba1930PortSwitch(mock_coordinator, 1, ENTRY_ID)
    assert switch.device_info is not None


async def test_switch_available_when_port_exists(mock_coordinator: MagicMock) -> None:
    """Switch is available when coordinator data contains the port."""
    switch = Aruba1930PortSwitch(mock_coordinator, 1, ENTRY_ID)
    assert switch.available is True


async def test_switch_unavailable_when_port_missing(mock_coordinator: MagicMock) -> None:
    """Switch is unavailable when coordinator data does not contain the port."""
    switch = Aruba1930PortSwitch(mock_coordinator, 99, ENTRY_ID)
    assert switch.available is False
