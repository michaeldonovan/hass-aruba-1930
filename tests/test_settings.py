"""Tests for aruba1930api.settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def _make_settings(**overrides: str | bool):
    """Return a Settings instance with minimal required fields, allowing overrides."""
    from aruba1930api.settings import Settings

    defaults = {
        "switch_host": "192.168.1.1",
        "switch_session_path": "cs7acddc6f",
        "switch_username": "admin",
        "switch_password": "secret",
        "api_key": "valid-key-1234",
    }
    defaults.update(overrides)
    return Settings.model_validate(defaults)


class TestApiKeyValidation:
    def test_valid_api_key_accepted(self) -> None:
        settings = _make_settings(api_key="supersecret")
        assert settings.api_key == "supersecret"

    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            _make_settings(api_key="")

    def test_whitespace_only_api_key_raises(self) -> None:
        with pytest.raises(ValidationError, match="must not be empty"):
            _make_settings(api_key="   ")
