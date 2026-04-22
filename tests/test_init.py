"""Tests for custom_components.aruba1930.__init__ (async_setup_entry)."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.aruba1930.switch_client import AuthError, SwitchError
from tests.conftest import _ConfigEntryAuthFailed, _ConfigEntryNotReady

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENTRY_DATA = {
    "host": "192.168.1.10",
    "session_path": "cs7acddc6f",
    "username": "admin",
    "password": "secret",
    "verify_ssl": True,
}


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = _ENTRY_DATA
    return entry


def _make_hass() -> MagicMock:
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    return hass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("custom_components.aruba1930.switch_client.SwitchClient", autospec=True)
@patch("custom_components.aruba1930.coordinator.Aruba1930Coordinator", autospec=True)
async def test_setup_entry_success(
    mock_coordinator_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """Happy path: client and coordinator stored in hass.data, platforms forwarded."""
    from custom_components.aruba1930 import async_setup_entry

    mock_client = mock_client_cls.return_value
    mock_client.login = AsyncMock()
    mock_client.logout = AsyncMock()

    mock_coordinator = mock_coordinator_cls.return_value
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.data = []

    hass = _make_hass()
    entry = _make_entry()

    result = await async_setup_entry(hass, entry)

    assert result is True
    mock_client.login.assert_awaited_once()
    mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()
    # Client must NOT be logged out on success.
    mock_client.logout.assert_not_awaited()


def test_vendored_switch_client_importable() -> None:
    """HA code should import the vendored switch client directly."""
    from custom_components.aruba1930.switch_client import SwitchClient

    assert SwitchClient is not None


def test_custom_component_package_imports_without_home_assistant() -> None:
    """Package import must not require Home Assistant to be installed."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import custom_components.aruba1930.switch_client as m; print(m.SwitchClient.__name__)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "SwitchClient"


@patch("custom_components.aruba1930.switch_client.SwitchClient", autospec=True)
async def test_setup_entry_auth_error_raises_config_entry_auth_failed(
    mock_client_cls: MagicMock,
) -> None:
    """AuthError during login must raise ConfigEntryAuthFailed, not ConfigEntryNotReady."""
    from custom_components.aruba1930 import async_setup_entry

    mock_client = mock_client_cls.return_value
    mock_client.login = AsyncMock(side_effect=AuthError("bad creds"))

    hass = _make_hass()
    entry = _make_entry()

    with pytest.raises(_ConfigEntryAuthFailed):
        await async_setup_entry(hass, entry)


@patch("custom_components.aruba1930.switch_client.SwitchClient", autospec=True)
async def test_setup_entry_switch_error_raises_config_entry_not_ready(
    mock_client_cls: MagicMock,
) -> None:
    """SwitchError during login must raise ConfigEntryNotReady."""
    from custom_components.aruba1930 import async_setup_entry

    mock_client = mock_client_cls.return_value
    mock_client.login = AsyncMock(side_effect=SwitchError("unreachable"))

    hass = _make_hass()
    entry = _make_entry()

    with pytest.raises(_ConfigEntryNotReady):
        await async_setup_entry(hass, entry)


@patch("custom_components.aruba1930.switch_client.SwitchClient", autospec=True)
@patch("custom_components.aruba1930.coordinator.Aruba1930Coordinator", autospec=True)
async def test_setup_entry_coordinator_auth_error_raises_config_entry_auth_failed(
    mock_coordinator_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """AuthError from the coordinator refresh must bubble as ConfigEntryAuthFailed."""
    from custom_components.aruba1930 import async_setup_entry

    mock_client = mock_client_cls.return_value
    mock_client.login = AsyncMock()
    mock_client.logout = AsyncMock()

    mock_coordinator = mock_coordinator_cls.return_value
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=AuthError("expired"))

    hass = _make_hass()
    entry = _make_entry()

    with pytest.raises(_ConfigEntryAuthFailed):
        await async_setup_entry(hass, entry)

    mock_client.logout.assert_awaited_once()


@patch("custom_components.aruba1930.switch_client.SwitchClient", autospec=True)
@patch("custom_components.aruba1930.coordinator.Aruba1930Coordinator", autospec=True)
async def test_setup_entry_coordinator_failure_calls_logout(
    mock_coordinator_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """If coordinator first refresh fails, client.logout() must be called."""
    from custom_components.aruba1930 import async_setup_entry

    mock_client = mock_client_cls.return_value
    mock_client.login = AsyncMock()
    mock_client.logout = AsyncMock()

    mock_coordinator = mock_coordinator_cls.return_value
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=RuntimeError("coordinator blew up")
    )

    hass = _make_hass()
    entry = _make_entry()

    with pytest.raises(RuntimeError, match="coordinator blew up"):
        await async_setup_entry(hass, entry)

    mock_client.logout.assert_awaited_once()


@patch("custom_components.aruba1930.switch_client.SwitchClient", autospec=True)
@patch("custom_components.aruba1930.coordinator.Aruba1930Coordinator", autospec=True)
async def test_setup_entry_platform_forward_failure_calls_logout(
    mock_coordinator_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """If async_forward_entry_setups fails, client.logout() must be called."""
    from custom_components.aruba1930 import async_setup_entry

    mock_client = mock_client_cls.return_value
    mock_client.login = AsyncMock()
    mock_client.logout = AsyncMock()

    mock_coordinator = mock_coordinator_cls.return_value
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.data = []

    hass = _make_hass()
    hass.config_entries.async_forward_entry_setups = AsyncMock(
        side_effect=RuntimeError("platform setup failed")
    )
    entry = _make_entry()

    with pytest.raises(RuntimeError, match="platform setup failed"):
        await async_setup_entry(hass, entry)

    mock_client.logout.assert_awaited_once()


@patch("custom_components.aruba1930.switch_client.SwitchClient", autospec=True)
@patch("custom_components.aruba1930.coordinator.Aruba1930Coordinator", autospec=True)
async def test_setup_entry_platform_forward_failure_leaves_no_runtime_entry(
    mock_coordinator_cls: MagicMock, mock_client_cls: MagicMock
) -> None:
    """No runtime data entry should remain after a failing setup."""
    from custom_components.aruba1930 import async_setup_entry
    from custom_components.aruba1930.const import DOMAIN

    mock_client = mock_client_cls.return_value
    mock_client.login = AsyncMock()
    mock_client.logout = AsyncMock()

    mock_coordinator = mock_coordinator_cls.return_value
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.data = []

    hass = _make_hass()
    hass.config_entries.async_forward_entry_setups = AsyncMock(
        side_effect=RuntimeError("platform setup failed")
    )
    entry = _make_entry()

    with pytest.raises(RuntimeError, match="platform setup failed"):
        await async_setup_entry(hass, entry)

    assert DOMAIN not in hass.data
