"""Compatibility shim for the Aruba 1930 switch client.

The real implementation lives in ``custom_components.aruba1930.switch_client``.
"""

from __future__ import annotations

from custom_components.aruba1930.switch_client import (
    AuthError,
    SwitchClient,
    SwitchError,
    _build_set_poe_xml,
    _encrypt_credential,
    _load_rsa_public_key_pem,
    _parse_port,
)

__all__ = [
    "AuthError",
    "SwitchClient",
    "SwitchError",
    "_build_set_poe_xml",
    "_encrypt_credential",
    "_load_rsa_public_key_pem",
    "_parse_port",
]
