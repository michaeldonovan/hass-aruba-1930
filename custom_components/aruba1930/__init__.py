"""The Aruba 1930 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aruba 1930 from a config entry."""
    from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

    from .const import CONF_SESSION_PATH, CONF_VERIFY_SSL, DOMAIN, PLATFORMS, Aruba1930RuntimeData
    from .coordinator import Aruba1930Coordinator
    from .switch_client import AuthError, SwitchClient, SwitchError

    client = SwitchClient(
        host=entry.data[CONF_HOST],
        session_path=entry.data[CONF_SESSION_PATH],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )

    try:
        await client.login()
    except AuthError as exc:
        raise ConfigEntryAuthFailed(f"Invalid credentials: {exc}") from exc
    except SwitchError as exc:
        raise ConfigEntryNotReady(f"Failed to connect to switch: {exc}") from exc

    try:
        coordinator = Aruba1930Coordinator(hass, client)
        await coordinator.async_config_entry_first_refresh()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = Aruba1930RuntimeData(
            client=client,
            coordinator=coordinator,
        )

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except AuthError as exc:
        await client.logout()
        domain_data = hass.data.get(DOMAIN)
        if domain_data is not None:
            domain_data.pop(entry.entry_id, None)
            if not domain_data:
                hass.data.pop(DOMAIN, None)
        raise ConfigEntryAuthFailed(f"Authentication failed during setup: {exc}") from exc
    except Exception:
        await client.logout()
        domain_data = hass.data.get(DOMAIN)
        if domain_data is not None:
            domain_data.pop(entry.entry_id, None)
            if not domain_data:
                hass.data.pop(DOMAIN, None)
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from .const import DOMAIN, PLATFORMS

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        runtime_data = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime_data.client.logout()

    return unload_ok
