"""Tests for the Aruba 1930 config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.aruba1930.config_flow import Aruba1930ConfigFlow
from custom_components.aruba1930.switch_client import AuthError, SwitchError

_VALID_INPUT = {
    "host": "192.168.1.10",
    "session_path": "cs7acddc6f",
    "username": "admin",
    "password": "secret",
    "verify_ssl": True,
}


def _make_flow(*, configured_hosts: set | None = None) -> Aruba1930ConfigFlow:
    """Return a fresh config flow instance.

    Args:
        configured_hosts: Set of host strings that simulate already-configured
            entries; causes ``_abort_if_unique_id_configured`` to raise.
    """
    flow = Aruba1930ConfigFlow()
    flow.hass = MagicMock()
    flow._configured_unique_ids = configured_hosts or set()
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
