"""Config flow for Aruba 1930 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_POLL_INTERVAL,
    CONF_SESSION_PATH,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .switch_client import AuthError, SwitchClient, SwitchError

_LOGGER = logging.getLogger(__name__)


def _build_user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the setup schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
            vol.Required(
                CONF_SESSION_PATH,
                default=defaults.get(CONF_SESSION_PATH, vol.UNDEFINED),
            ): str,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, vol.UNDEFINED)): str,
            vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, vol.UNDEFINED)): str,
            vol.Optional(
                CONF_POLL_INTERVAL,
                default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)): bool,
        }
    )


def _build_reconfigure_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the reconfigure schema for connection settings."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
            vol.Required(CONF_SESSION_PATH, default=defaults[CONF_SESSION_PATH]): str,
            vol.Required(CONF_USERNAME, default=defaults[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD, default=defaults[CONF_PASSWORD]): str,
            vol.Optional(CONF_VERIFY_SSL, default=defaults[CONF_VERIFY_SSL]): bool,
        }
    )


async def _validate_connection(user_input: dict[str, Any]) -> str | None:
    """Validate switch connectivity/auth for the supplied settings."""
    client = SwitchClient(
        host=user_input[CONF_HOST],
        session_path=user_input[CONF_SESSION_PATH],
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
        verify_ssl=user_input[CONF_VERIFY_SSL],
    )

    try:
        await client.login()
        await client.logout()
    except AuthError:
        return "invalid_auth"
    except SwitchError:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception during login")
        return "unknown"

    return None


class Aruba1930ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aruba 1930."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> Aruba1930OptionsFlow:
        """Return the options flow for this config entry."""
        return Aruba1930OptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            error = await _validate_connection(user_input)
            if error is None:
                return self.async_create_entry(
                    title=f"Aruba 1930 ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of connection settings."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            current_host = entry.data[CONF_HOST]
            if user_input[CONF_HOST] != current_host:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()

            error = await _validate_connection(user_input)
            if error is None:
                return await self.async_update_reload_and_abort(
                    entry,
                    data_updates={**entry.data, **user_input},
                )
            errors["base"] = error

        defaults = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_SESSION_PATH: entry.data[CONF_SESSION_PATH],
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
            CONF_VERIFY_SSL: entry.data[CONF_VERIFY_SSL],
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema(defaults),
            errors=errors,
        )

    def _get_reconfigure_entry(self) -> ConfigEntry:
        """Return the entry being reconfigured."""
        return self.config_entry


class Aruba1930OptionsFlow(OptionsFlowWithConfigEntry):
    """Handle Aruba 1930 options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the polling interval option."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POLL_INTERVAL, default=current_interval): vol.All(
                        int, vol.Range(min=1)
                    ),
                }
            ),
            errors={},
        )
