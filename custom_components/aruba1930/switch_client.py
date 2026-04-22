"""Vendored Aruba 1930 switch client.

This copy must stay in sync with ``aruba1930api.switch_client``.
"""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

logger = logging.getLogger(__name__)


class SwitchError(Exception):
    """Raised when the switch returns an error or cannot be reached."""


class AuthError(SwitchError):
    """Raised when login fails or the session is rejected."""


def _load_rsa_public_key_pem(pem_text: str) -> Any:
    key_bytes = pem_text.strip().encode()
    try:
        return load_pem_public_key(key_bytes)
    except (ValueError, TypeError) as exc:
        raise SwitchError(f"Cannot parse switch RSA public key: {exc}") from exc


def _encrypt_credential(public_key: Any, plaintext: str) -> str:
    ciphertext: bytes = public_key.encrypt(plaintext.encode("utf-8"), padding.PKCS1v15())
    return ciphertext.hex()


def _parse_text(element: ET.Element | None, tag: str, default: str = "") -> str:
    if element is None:
        return default
    child = element.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _parse_int(element: ET.Element | None, tag: str, default: int = 0) -> int:
    text = _parse_text(element, tag)
    try:
        return int(text)
    except (ValueError, TypeError):
        return default


def _parse_port(iface: ET.Element) -> dict[str, Any]:
    admin_enable = _parse_int(iface, "adminEnable", default=1)
    return {
        "id": _parse_int(iface, "interfaceID"),
        "name": _parse_text(iface, "interfaceName"),
        "poe_enabled": admin_enable == 1,
        "detection_status": _parse_int(iface, "detectionStatus"),
        "voltage_mv": _parse_int(iface, "outputVoltage"),
        "current_ma": _parse_int(iface, "outputCurrent"),
        "power_mw": _parse_int(iface, "outputPower"),
        "power_limit_mw": _parse_int(iface, "powerLimit"),
        "priority": _parse_int(iface, "powerPriority"),
    }


def _build_set_poe_xml(port_id: int, enabled: bool, power_priority: int = 2) -> bytes:
    admin_enable = 1 if enabled else 2
    xml = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<DeviceConfiguration>"
        '<PoEPSEInterfaceList action="set">'
        "<Interface>"
        f"<interfaceName>{port_id}</interfaceName>"
        f"<interfaceID>{port_id}</interfaceID>"
        f"<adminEnable>{admin_enable}</adminEnable>"
        "<timeRangeName></timeRangeName>"
        f"<powerPriority>{power_priority}</powerPriority>"
        "<portLegacy_powerDetectType>2</portLegacy_powerDetectType>"
        "<powerManagementMode>1</powerManagementMode>"
        "<portClassLimit>4</portClassLimit>"
        "</Interface>"
        "</PoEPSEInterfaceList>"
        "</DeviceConfiguration>"
    )
    return xml.encode("utf-8")


class SwitchClient:
    def __init__(
        self,
        host: str,
        session_path: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
    ) -> None:
        self._host = host
        self._session_path = session_path
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._base_url = f"https://{host}/{session_path}/hpe"
        self._session_cookie: str | None = None
        self._csrf_token: str | None = None
        self._session_valid: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def login(self) -> None:
        async with self._lock:
            await self._do_login()

    async def logout(self) -> None:
        async with self._lock:
            await self._do_logout()

    async def get_ports(self) -> list[dict[str, Any]]:
        async with self._lock:
            return await self._get_ports_locked()

    async def set_poe(self, port_id: int, enabled: bool) -> None:
        async with self._lock:
            await self._set_poe_locked(port_id, enabled)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=self._verify_ssl,
                timeout=httpx.Timeout(30.0),
                follow_redirects=False,
            )
        return self._client

    def _session_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if self._session_cookie:
            headers["Cookie"] = f"sessionid={self._session_cookie}"
        return headers

    def _invalidate_session(self) -> None:
        self._session_valid = False
        self._session_cookie = None
        self._csrf_token = None

    async def _do_login(self) -> None:
        client = self._get_client()
        enc_url = f"https://{self._host}/device/wcd?{{EncryptionSetting}}"
        try:
            enc_resp = await client.get(enc_url)
            enc_resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SwitchError(f"Cannot reach switch for encryption settings: {exc}") from exc

        root = self._parse_xml(enc_resp.text)
        enc_section = root.find(".//EncryptionSetting")
        if enc_section is None:
            raise SwitchError("EncryptionSetting not found in switch response.")

        encrypt_enabled = _parse_int(enc_section, "passwEncryptEnable", default=1)
        rsa_pem = _parse_text(enc_section, "rsaPublicKey")
        login_token = _parse_text(enc_section, "loginToken")
        encoded_password = quote(self._password, safe="")
        plaintext = (
            f"user={self._username}&password={encoded_password}&ssd=true&token={login_token}&"
        )

        if encrypt_enabled == 1:
            if not rsa_pem:
                raise SwitchError("Switch requested encryption but returned no RSA key.")
            public_key = _load_rsa_public_key_pem(rsa_pem)
            cred = _encrypt_credential(public_key, plaintext)
            login_url = f"{self._base_url}/config/system.xml?action=login&cred={cred}"
        else:
            raise SwitchError(
                "Switch reports password encryption is disabled "
                "(passwEncryptEnable=0).  Refusing to send credentials as "
                "plaintext URL parameters.  Enable RSA encryption on the switch."
            )

        try:
            login_resp = await client.get(login_url)
            login_resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AuthError(f"Switch login returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise SwitchError(f"Switch login request failed: {exc}") from exc

        raw_session = login_resp.headers.get("sessionid", "")
        if not raw_session:
            self._raise_if_xml_error(login_resp.text, context="login")
            raise AuthError("Switch did not return a sessionid header after login.")

        cookie_value = raw_session.split(";")[0].strip()
        self._session_cookie = cookie_value
        self._csrf_token = login_resp.headers.get("csrftoken", "")
        self._session_valid = True

    async def _do_logout(self) -> None:
        if self._session_valid:
            client = self._get_client()
            try:
                logout_url = f"https://{self._host}/System.xml?action=logout"
                await client.get(logout_url, headers=self._session_headers())
                logger.info("Switch logout successful.")
            except httpx.HTTPError as exc:
                logger.warning("Logout request failed (ignored): %s", exc)
            finally:
                self._invalidate_session()

        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_ports_locked(self) -> list[dict[str, Any]]:
        url = f"{self._base_url}/wcd?{{PoEPSEInterfaceList}}"
        text = await self._request("GET", url)
        self._raise_if_xml_error(text, context="get_ports")
        root = self._parse_xml(text)
        interfaces = root.findall(".//PoEPSEInterfaceList/Interface")
        ports = [_parse_port(iface) for iface in interfaces]
        logger.debug("Got %d PoE ports from switch.", len(ports))
        return ports

    async def _set_poe_locked(self, port_id: int, enabled: bool) -> None:
        url = (
            f"{self._base_url}/wcd?{{PoEPSEUnitList}}{{DiagnosticsUnitList}}{{PoEPSEInterfaceList}}"
        )
        body = _build_set_poe_xml(port_id, enabled)
        extra_headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        text = await self._request("POST", url, content=body, headers=extra_headers)
        self._raise_if_xml_error(text, context=f"set_poe(port={port_id}, enabled={enabled})")
        logger.info("PoE port %d set to enabled=%s.", port_id, enabled)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        if not self._session_valid:
            logger.debug("Session not valid — logging in before request.")
            await self._do_login()

        merged_headers = {**self._session_headers(), **(headers or {})}
        response = await self._send(method, url, content=content, headers=merged_headers)

        if response.status_code in (401, 403):
            logger.info(
                "Switch returned %s — session expired; re-logging in.", response.status_code
            )
            self._invalidate_session()
            await self._do_login()
            merged_headers = {**self._session_headers(), **(headers or {})}
            response = await self._send(method, url, content=content, headers=merged_headers)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SwitchError(
                f"Switch returned HTTP {exc.response.status_code} for {url}."
            ) from exc

        return response.text

    async def _send(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        client = self._get_client()
        try:
            return await client.request(method, url, content=content, headers=headers)
        except httpx.HTTPError as exc:
            self._invalidate_session()
            raise SwitchError(f"Network error communicating with switch: {exc}") from exc

    @staticmethod
    def _parse_xml(text: str) -> ET.Element:
        try:
            return ET.fromstring(text.strip())
        except ET.ParseError as exc:
            raise SwitchError(f"Switch returned invalid XML: {exc}") from exc

    @staticmethod
    def _raise_if_xml_error(text: str, *, context: str = "") -> None:
        if not text.strip():
            return
        try:
            root = ET.fromstring(text.strip())
        except ET.ParseError:
            return
        status_code_el = root.find(".//statusCode")
        status_string_el = root.find(".//statusString")
        if status_code_el is not None and status_code_el.text:
            code_text = status_code_el.text.strip()
            if code_text and code_text != "0":
                status_string = (
                    status_string_el.text.strip()
                    if status_string_el is not None and status_string_el.text
                    else "unknown error"
                )
                prefix = f"[{context}] " if context else ""
                raise SwitchError(f"{prefix}Switch error code {code_text}: {status_string}")
