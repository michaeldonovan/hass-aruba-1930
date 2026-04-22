"""Tests for the Aruba 1930 coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.aruba1930.coordinator import Aruba1930Coordinator
from custom_components.aruba1930.switch_client import AuthError, SwitchError
from tests.conftest import _ConfigEntryAuthFailed, _UpdateFailed


async def test_coordinator_returns_port_data(mock_switch_client: MagicMock) -> None:
    """Successful refresh returns the switch port list."""
    coordinator = Aruba1930Coordinator(MagicMock(), mock_switch_client)

    data = await coordinator._async_update_data()

    assert data == mock_switch_client.get_ports.return_value


async def test_coordinator_auth_error_raises_config_entry_auth_failed(
    mock_switch_client: MagicMock,
) -> None:
    """Auth failures during refresh trigger HA reauthentication."""
    mock_switch_client.get_ports = AsyncMock(side_effect=AuthError("bad creds"))
    coordinator = Aruba1930Coordinator(MagicMock(), mock_switch_client)

    with pytest.raises(_ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_switch_error_raises_update_failed(
    mock_switch_client: MagicMock,
) -> None:
    """Non-auth communication failures still surface as UpdateFailed."""
    mock_switch_client.get_ports = AsyncMock(side_effect=SwitchError("timeout"))
    coordinator = Aruba1930Coordinator(MagicMock(), mock_switch_client)

    with pytest.raises(_UpdateFailed):
        await coordinator._async_update_data()
