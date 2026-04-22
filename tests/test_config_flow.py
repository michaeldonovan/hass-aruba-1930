"""Tests for the Aruba 1930 config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.aruba1930.config_flow import Aruba1930ConfigFlow, Aruba1930OptionsFlow
from custom_components.aruba1930.switch_client import AuthError, SwitchError

_VALID_INPUT = {
    "host": "192.168.1.10",
    "session_path": "cs7acddc6f",
    "username": "admin",
    "password": "secret",
    "poll_interval": 30,
    "verify_ssl": True,
}

_VALID_RECONFIGURE_INPUT = {
    "host": "192.168.1.10",
    "session_path": "cs7acddc6f",
    "username": "admin",
    "password": "secret",
    "verify_ssl": True,
}


def _make_flow(*, configured_hosts: set | None = None) -> Aruba1930ConfigFlow:
    """Return a fresh config flow instance."""
    flow = Aruba1930ConfigFlow()
    flow.hass = MagicMock()
    flow._configured_unique_ids = configured_hosts or set()
    return flow


def _make_entry(*, data: dict | None = None, options: dict | None = None) -> MagicMock:
    """Return a fake config entry."""
    entry = MagicMock()
    entry.data = data or dict(_VALID_INPUT)
    entry.options = options or {}
    return entry


def _make_options_flow(
    options: dict | None = None, data: dict | None = None
) -> Aruba1930OptionsFlow:
    """Return an options flow bound to a fake entry."""
    return Aruba1930OptionsFlow(_make_entry(data=data, options=options))


def _make_reconfigure_flow(entry: MagicMock | None = None) -> Aruba1930ConfigFlow:
    """Return a reconfigure flow bound to a fake entry."""
    flow = _make_flow()
    flow.config_entry = entry or _make_entry()
    return flow


@pytest.fixture(autouse=True)
def patch_switch_client_cls():
    """Patch SwitchClient at the config_flow module level for every test."""
    with patch(
        "custom_components.aruba1930.config_flow.SwitchClient",
        autospec=True,
    ) as mock_cls:
        yield mock_cls


async def test_form_shows_on_no_input(patch_switch_client_cls: MagicMock) -> None:
    """Step with no input should return a form."""
    flow = _make_flow()

    result = await flow.async_step_user(None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_form_includes_poll_interval_default(
    patch_switch_client_cls: MagicMock,
) -> None:
    """The setup form should expose the polling interval field."""
    flow = _make_flow()

    result = await flow.async_step_user(None)

    schema = result["data_schema"]
    data = schema({"host": "a", "session_path": "b", "username": "c", "password": "d"})
    assert data["poll_interval"] == 30


async def test_form_success(patch_switch_client_cls: MagicMock) -> None:
    """Successful validation should create an entry."""
    mock_instance = patch_switch_client_cls.return_value
    mock_instance.login = AsyncMock()
    mock_instance.logout = AsyncMock()

    flow = _make_flow()
    result = await flow.async_step_user(_VALID_INPUT)

    mock_instance.login.assert_awaited_once()
    mock_instance.logout.assert_awaited_once()
    assert result["type"] == "create_entry"
    assert result["title"] == "Aruba 1930 (192.168.1.10)"
    assert result["data"]["host"] == "192.168.1.10"
    assert result["data"]["poll_interval"] == 30


async def test_form_invalid_auth(patch_switch_client_cls: MagicMock) -> None:
    """AuthError should surface as invalid_auth form error."""
    mock_instance = patch_switch_client_cls.return_value
    mock_instance.login = AsyncMock(side_effect=AuthError("bad creds"))

    flow = _make_flow()
    result = await flow.async_step_user(_VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


async def test_form_cannot_connect(patch_switch_client_cls: MagicMock) -> None:
    """SwitchError should surface as cannot_connect form error."""
    mock_instance = patch_switch_client_cls.return_value
    mock_instance.login = AsyncMock(side_effect=SwitchError("unreachable"))

    flow = _make_flow()
    result = await flow.async_step_user(_VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_form_unknown_exception(patch_switch_client_cls: MagicMock) -> None:
    """Unexpected exceptions should surface as unknown form error."""
    mock_instance = patch_switch_client_cls.return_value
    mock_instance.login = AsyncMock(side_effect=RuntimeError("oops"))

    flow = _make_flow()
    result = await flow.async_step_user(_VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "unknown"


async def test_already_configured_aborts(patch_switch_client_cls: MagicMock) -> None:
    """Submitting a host that is already configured should abort the flow."""
    from tests.conftest import _AbortFlow

    flow = _make_flow(configured_hosts={"192.168.1.10"})
    with pytest.raises(_AbortFlow) as exc_info:
        await flow.async_step_user(_VALID_INPUT)

    assert exc_info.value.reason == "already_configured"


async def test_reconfigure_form_shows_current_connection_defaults(
    patch_switch_client_cls: MagicMock,
) -> None:
    """Reconfigure form should prefill the current connection settings."""
    flow = _make_reconfigure_flow()

    result = await flow.async_step_reconfigure(None)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    data = result["data_schema"]({})
    assert data["host"] == "192.168.1.10"
    assert data["session_path"] == "cs7acddc6f"
    assert data["username"] == "admin"
    assert data["password"] == "secret"
    assert data["verify_ssl"] is True
    assert "poll_interval" not in data


async def test_reconfigure_success_updates_entry_data(
    patch_switch_client_cls: MagicMock,
) -> None:
    """Valid reconfigure input should update the existing entry and abort."""
    mock_instance = patch_switch_client_cls.return_value
    mock_instance.login = AsyncMock()
    mock_instance.logout = AsyncMock()

    entry = _make_entry()
    flow = _make_reconfigure_flow(entry)
    user_input = {
        "host": "192.168.1.20",
        "session_path": "newpath",
        "username": "operator",
        "password": "newsecret",
        "verify_ssl": False,
    }

    result = await flow.async_step_reconfigure(user_input)

    assert result == {"type": "abort", "reason": "reconfigure_success"}
    assert entry.data["host"] == "192.168.1.20"
    assert entry.data["session_path"] == "newpath"
    assert entry.data["username"] == "operator"
    assert entry.data["password"] == "newsecret"
    assert entry.data["verify_ssl"] is False
    assert entry.data["poll_interval"] == 30


async def test_reconfigure_invalid_auth(
    patch_switch_client_cls: MagicMock,
) -> None:
    """AuthError during reconfigure should return the form with invalid_auth."""
    mock_instance = patch_switch_client_cls.return_value
    mock_instance.login = AsyncMock(side_effect=AuthError("bad creds"))

    flow = _make_reconfigure_flow()
    result = await flow.async_step_reconfigure(_VALID_RECONFIGURE_INPUT)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"]["base"] == "invalid_auth"


async def test_reconfigure_cannot_connect(
    patch_switch_client_cls: MagicMock,
) -> None:
    """SwitchError during reconfigure should return the form with cannot_connect."""
    mock_instance = patch_switch_client_cls.return_value
    mock_instance.login = AsyncMock(side_effect=SwitchError("unreachable"))

    flow = _make_reconfigure_flow()
    result = await flow.async_step_reconfigure(_VALID_RECONFIGURE_INPUT)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"]["base"] == "cannot_connect"


async def test_options_form_shows_current_poll_interval() -> None:
    """Options form should expose the configured polling interval."""
    flow = _make_options_flow(options={"poll_interval": 45})

    result = await flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    data = result["data_schema"]({})
    assert data["poll_interval"] == 45


async def test_options_save_success() -> None:
    """Saving options should create an options entry."""
    flow = _make_options_flow()

    result = await flow.async_step_init({"poll_interval": 60})

    assert result["type"] == "create_entry"
    assert result["data"]["poll_interval"] == 60
