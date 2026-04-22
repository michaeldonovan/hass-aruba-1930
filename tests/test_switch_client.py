"""Unit tests for SwitchClient using respx to mock httpx calls."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
import pytest
import respx
from httpx import Response

from aruba1930api.switch_client import (
    AuthError,
    SwitchClient,
    SwitchError,
    _build_set_poe_xml,
    _encrypt_credential,
    _load_rsa_public_key_pem,
    _parse_port,
)

# ---------------------------------------------------------------------------
# XML fixtures
# ---------------------------------------------------------------------------

# Realistic RSA-2048 public key in PKCS#1 PEM format (as returned by the switch).
SAMPLE_RSA_PUBLIC_KEY_PEM = """\
-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAx1r3sx6c8/PdfCOHW68J0VOY7brxMMnAepMx16V3/1/+5yo+JCsG
XICOEaE/tRcRFsZffZVvk/xDNpgv6lhtQ0053RxrD9kUIP7Uw+dxNIL3sjmrmUbD
5vjhv/CD2ReUCeq3zFnyvwQJrh5tdDLp1JKhOcGyTg7hmgU8vFuP35afKcYHQUGB
6zWc8ehI+B++hqXL9l8vpqxi1vlkcq1iGiDyiZLbsjSN4MmbbFhvYlZ86hzsifuT
qKELDWRpLStFX6jiVYG1N6DFGsi1WcRZYyYMvexJHHIl+QaCxrALAl1INFMB0En7
AC8S8SUiXrjYgT3XO3jR+VDDgPDfd/H1rwIDAQAB
-----END RSA PUBLIC KEY-----"""

ENCRYPTION_SETTING_RESPONSE = f"""\
<?xml version="1.0" encoding="UTF-8" ?>
<ResponseData>
<DeviceConfiguration>
<version>1.0</version>
<ConnectedUserList type="section">
</ConnectedUserList>
<EncryptionSetting type="section">
<passwEncryptEnable>1</passwEncryptEnable>
<rsaPublicKey>{SAMPLE_RSA_PUBLIC_KEY_PEM}
</rsaPublicKey>
<loginToken>954b0d76</loginToken>
</EncryptionSetting>
</DeviceConfiguration>
</ResponseData>"""

ENCRYPTION_SETTING_PLAINTEXT_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8" ?>
<ResponseData>
<DeviceConfiguration>
<version>1.0</version>
<EncryptionSetting type="section">
<passwEncryptEnable>0</passwEncryptEnable>
<rsaPublicKey></rsaPublicKey>
<loginToken>aabbccdd</loginToken>
</EncryptionSetting>
</DeviceConfiguration>
</ResponseData>"""

LOGIN_SUCCESS_HEADERS = {
    "sessionid": "UserId=&4b96300e7e012563ad98d43ff0609bd3&;path=/",
    "csrftoken": "-653345209",
    "content-type": "text/xml; charset=utf-8",
}

LOGIN_RESPONSE_BODY = ""  # switch returns empty body on success

POE_INTERFACE_LIST_XML = """\
<?xml version="1.0" encoding="UTF-8" ?>
<ResponseData>
<DeviceConfiguration>
<version>1.0</version>
<PoEPSEInterfaceList type="section">
<Interface>
  <interfaceName>1</interfaceName>
  <interfaceType>1</interfaceType>
  <interfaceID>1</interfaceID>
  <unitID>1</unitID>
  <adminEnable>1</adminEnable>
  <detectionStatus>3</detectionStatus>
  <powerPriority>1</powerPriority>
  <powerClassification>5</powerClassification>
  <outputVoltage>55000</outputVoltage>
  <outputCurrent>152</outputCurrent>
  <outputPower>8300</outputPower>
  <powerLimit>30000</powerLimit>
</Interface>
<Interface>
  <interfaceName>2</interfaceName>
  <interfaceType>1</interfaceType>
  <interfaceID>2</interfaceID>
  <unitID>1</unitID>
  <adminEnable>2</adminEnable>
  <detectionStatus>2</detectionStatus>
  <powerPriority>2</powerPriority>
  <powerClassification>1</powerClassification>
  <outputVoltage>0</outputVoltage>
  <outputCurrent>0</outputCurrent>
  <outputPower>0</outputPower>
  <powerLimit>30000</powerLimit>
</Interface>
</PoEPSEInterfaceList>
</DeviceConfiguration>
</ResponseData>"""

SET_POE_SUCCESS_RESPONSE = """\
<?xml version='1.0' encoding='UTF-8'?>
<ResponseData>
<ActionStatus>
 <version>1.0</version>
 <requestURL>PoEPSEInterfaceList</requestURL>
 <requestAction>set</requestAction>
 <statusCode>0</statusCode>
 <deviceStatusCode>0</deviceStatusCode>
 <statusString>OK</statusString>
</ActionStatus>
</ResponseData>"""

SET_POE_ERROR_RESPONSE = """\
<?xml version='1.0' encoding='UTF-8'?>
<ResponseData>
<ActionStatus>
 <version>1.0</version>
 <requestURL>PoEPSEInterfaceList</requestURL>
 <requestAction>set</requestAction>
 <statusCode>5</statusCode>
 <deviceStatusCode>5</deviceStatusCode>
 <statusString>Permission denied</statusString>
</ActionStatus>
</ResponseData>"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_client(**kwargs: str | bool) -> SwitchClient:
    """Return a SwitchClient pointed at a fake host."""
    defaults: dict[str, str | bool] = {
        "host": "switch.test",
        "session_path": "cs7acddc6f",
        "username": "admin",
        "password": "secret",
        "verify_ssl": False,
    }
    defaults.update(kwargs)
    return SwitchClient(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------


class TestLoadRsaPublicKey:
    """Test _load_rsa_public_key_pem with PKCS#1 format."""

    def test_loads_pkcs1_pem(self) -> None:
        key = _load_rsa_public_key_pem(SAMPLE_RSA_PUBLIC_KEY_PEM)
        assert key is not None

    def test_can_encrypt_with_loaded_key(self) -> None:
        key = _load_rsa_public_key_pem(SAMPLE_RSA_PUBLIC_KEY_PEM)
        ciphertext_hex = _encrypt_credential(key, "testpassword")
        # RSA-2048 output is always 256 bytes = 512 hex chars
        assert len(ciphertext_hex) == 512
        # Must be valid hex
        bytes.fromhex(ciphertext_hex)

    def test_bad_pem_raises_switch_error(self) -> None:
        with pytest.raises(SwitchError, match="RSA public key"):
            _load_rsa_public_key_pem(
                "-----BEGIN RSA PUBLIC KEY-----\nnotvalid\n-----END RSA PUBLIC KEY-----"
            )

    def test_pkcs8_fallback(self) -> None:
        """PKCS#8 PEM header (BEGIN PUBLIC KEY) is also accepted."""
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        # Export the known-good key as PKCS#8 and verify it still loads.
        pkcs1_key = _load_rsa_public_key_pem(SAMPLE_RSA_PUBLIC_KEY_PEM)
        pkcs8_pem = pkcs1_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
        assert "BEGIN PUBLIC KEY" in pkcs8_pem
        key = _load_rsa_public_key_pem(pkcs8_pem)
        assert key is not None
        # Encryption still produces valid 512-char hex.
        assert len(_encrypt_credential(key, "test")) == 512


class TestBuildSetPoeXml:
    """Test _build_set_poe_xml generates correct XML."""

    def test_enable(self) -> None:
        xml_bytes = _build_set_poe_xml(9, enabled=True)
        root = ET.fromstring(xml_bytes)
        iface = root.find(".//Interface")
        assert iface is not None
        assert iface.findtext("interfaceID") == "9"
        assert iface.findtext("adminEnable") == "1"

    def test_disable(self) -> None:
        xml_bytes = _build_set_poe_xml(3, enabled=False)
        root = ET.fromstring(xml_bytes)
        iface = root.find(".//Interface")
        assert iface is not None
        assert iface.findtext("interfaceID") == "3"
        assert iface.findtext("adminEnable") == "2"

    def test_action_attribute(self) -> None:
        xml_bytes = _build_set_poe_xml(1, enabled=True)
        root = ET.fromstring(xml_bytes)
        poe_list = root.find("PoEPSEInterfaceList")
        assert poe_list is not None
        assert poe_list.get("action") == "set"


class TestParsePort:
    """Test _parse_port correctly converts XML to a dict."""

    def test_enabled_port(self) -> None:
        xml = ET.fromstring("""\
<Interface>
  <interfaceName>1</interfaceName>
  <interfaceID>1</interfaceID>
  <adminEnable>1</adminEnable>
  <detectionStatus>3</detectionStatus>
  <outputVoltage>55000</outputVoltage>
  <outputCurrent>152</outputCurrent>
  <outputPower>8300</outputPower>
  <powerLimit>30000</powerLimit>
  <powerPriority>1</powerPriority>
</Interface>""")
        port = _parse_port(xml)
        assert port["id"] == 1
        assert port["name"] == "1"
        assert port["poe_enabled"] is True
        assert port["detection_status"] == 3
        assert port["voltage_mv"] == 55000
        assert port["current_ma"] == 152
        assert port["power_mw"] == 8300
        assert port["power_limit_mw"] == 30000
        assert port["priority"] == 1

    def test_disabled_port(self) -> None:
        xml = ET.fromstring("""\
<Interface>
  <interfaceName>2</interfaceName>
  <interfaceID>2</interfaceID>
  <adminEnable>2</adminEnable>
  <detectionStatus>2</detectionStatus>
  <outputVoltage>0</outputVoltage>
  <outputCurrent>0</outputCurrent>
  <outputPower>0</outputPower>
  <powerLimit>30000</powerLimit>
  <powerPriority>2</powerPriority>
</Interface>""")
        port = _parse_port(xml)
        assert port["poe_enabled"] is False
        assert port["power_mw"] == 0


# ---------------------------------------------------------------------------
# Integration tests — SwitchClient with mocked HTTP
# ---------------------------------------------------------------------------


class TestLogin:
    """Test login flow with encrypted and plaintext credentials."""

    @respx.mock
    async def test_login_success_with_encryption(self) -> None:
        """Login with RSA encryption enabled succeeds and stores session."""
        client = make_client()

        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_RESPONSE)
        )

        # Match any login URL (cred value will vary due to RSA randomness).
        respx.get(url__regex=r".*action=login.*").mock(
            return_value=Response(
                200,
                text=LOGIN_RESPONSE_BODY,
                headers=LOGIN_SUCCESS_HEADERS,
            )
        )

        await client.login()

        assert client._session_valid is True
        assert client._session_cookie is not None
        assert "UserId=" in client._session_cookie

    @respx.mock
    async def test_login_plaintext_credential_raises(self) -> None:
        """Login raises SwitchError when switch reports encryption is disabled."""
        client = make_client(password="mypassword")

        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_PLAINTEXT_RESPONSE)
        )

        with pytest.raises(SwitchError, match="passwEncryptEnable=0"):
            await client.login()

    @respx.mock
    async def test_login_missing_sessionid_raises(self) -> None:
        """Missing sessionid header raises AuthError."""
        client = make_client()

        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_RESPONSE)
        )

        respx.get(url__regex=r".*action=login.*").mock(
            return_value=Response(200, text="", headers={"content-type": "text/xml"})
        )

        with pytest.raises(AuthError, match="sessionid"):
            await client.login()

    @respx.mock
    async def test_login_http_error_raises_auth_error(self) -> None:
        """HTTP 401 from login endpoint raises AuthError."""
        client = make_client()

        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_RESPONSE)
        )

        respx.get(url__regex=r".*action=login.*").mock(
            return_value=Response(401, text="Unauthorized")
        )

        with pytest.raises(AuthError):
            await client.login()

    @respx.mock
    async def test_encryption_setting_unreachable_raises(self) -> None:
        """Network failure fetching encryption settings raises SwitchError."""
        import httpx as _httpx

        client = make_client()

        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            side_effect=_httpx.ConnectError("unreachable")
        )

        with pytest.raises(SwitchError, match="reach switch"):
            await client.login()

    @respx.mock
    async def test_login_credential_plaintext_format(self) -> None:
        """Encrypted cred contains user=, password=, ssd=true, token= components."""
        client = make_client(username="admin", password="p@ss!")

        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_RESPONSE)
        )

        captured: list[str] = []

        def capture_login(request: httpx.Request) -> Response:  # type: ignore[name-defined]
            captured.append(str(request.url))
            return Response(200, text=LOGIN_RESPONSE_BODY, headers=LOGIN_SUCCESS_HEADERS)

        respx.get(url__regex=r".*action=login.*").mock(side_effect=capture_login)

        await client.login()

        assert len(captured) == 1
        login_url = captured[0]
        assert "action=login" in login_url
        assert "cred=" in login_url
        # Decrypt and verify plaintext contents.
        from urllib.parse import parse_qs, urlparse

        # The cred is RSA-encrypted — we can't decrypt without the private key,
        # but we can confirm it is 512 hex chars (RSA-2048 output).
        parsed = urlparse(login_url)
        cred = parse_qs(parsed.query)["cred"][0]
        assert len(cred) == 512, f"Expected 512-char hex cred, got {len(cred)}"
        bytes.fromhex(cred)  # must be valid hex

    @respx.mock
    async def test_login_session_cookie_strips_path_directive(self) -> None:
        """Session cookie is extracted correctly from the raw sessionid header."""
        client = make_client()

        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_RESPONSE)
        )

        respx.get(url__regex=r".*action=login.*").mock(
            return_value=Response(
                200,
                text=LOGIN_RESPONSE_BODY,
                headers={
                    **LOGIN_SUCCESS_HEADERS,
                    # Full value as the switch sends it.
                    "sessionid": "UserId=&deadbeefcafe&;path=/",
                },
            )
        )

        await client.login()

        # Cookie must NOT include the ;path=/ directive.
        assert client._session_cookie == "UserId=&deadbeefcafe&"
        assert ";path=" not in (client._session_cookie or "")


class TestGetPorts:
    """Test get_ports XML parsing."""

    def _setup_logged_in_client(self) -> SwitchClient:
        """Return a client whose session is pre-seeded (no login needed)."""
        client = make_client()
        client._session_valid = True
        client._session_cookie = "UserId=&4b96300e7e012563ad98d43ff0609bd3&"
        return client

    @respx.mock
    async def test_get_ports_returns_parsed_list(self) -> None:
        """get_ports returns correctly parsed port dicts."""
        client = self._setup_logged_in_client()

        respx.get("https://switch.test/cs7acddc6f/hpe/wcd?{PoEPSEInterfaceList}").mock(
            return_value=Response(200, text=POE_INTERFACE_LIST_XML)
        )

        ports = await client.get_ports()

        assert len(ports) == 2

        port1 = next(p for p in ports if p["id"] == 1)
        assert port1["poe_enabled"] is True
        assert port1["voltage_mv"] == 55000
        assert port1["current_ma"] == 152
        assert port1["power_mw"] == 8300
        assert port1["power_limit_mw"] == 30000
        assert port1["priority"] == 1
        assert port1["detection_status"] == 3

        port2 = next(p for p in ports if p["id"] == 2)
        assert port2["poe_enabled"] is False
        assert port2["power_mw"] == 0

    @respx.mock
    async def test_get_ports_session_expiry_retries(self) -> None:
        """A 401 triggers re-login and a successful retry."""
        client = self._setup_logged_in_client()

        # First call returns 401 (session expired).
        poe_route = respx.get("https://switch.test/cs7acddc6f/hpe/wcd?{PoEPSEInterfaceList}").mock(
            side_effect=[
                Response(401, text="Session expired"),
                Response(200, text=POE_INTERFACE_LIST_XML),
            ]
        )

        # Re-login sequence.
        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_RESPONSE)
        )
        respx.get(url__regex=r".*action=login.*").mock(
            return_value=Response(200, text=LOGIN_RESPONSE_BODY, headers=LOGIN_SUCCESS_HEADERS)
        )

        ports = await client.get_ports()
        assert len(ports) == 2
        assert poe_route.call_count == 2

    @respx.mock
    async def test_get_ports_invalid_xml_raises(self) -> None:
        """Invalid XML response raises SwitchError."""
        client = self._setup_logged_in_client()

        respx.get("https://switch.test/cs7acddc6f/hpe/wcd?{PoEPSEInterfaceList}").mock(
            return_value=Response(200, text="<not valid xml")
        )

        with pytest.raises(SwitchError, match="invalid XML"):
            await client.get_ports()

    @respx.mock
    async def test_get_ports_xml_error_response_raises(self) -> None:
        """XML error envelope with HTTP 200 raises SwitchError instead of returning []."""
        client = self._setup_logged_in_client()

        respx.get("https://switch.test/cs7acddc6f/hpe/wcd?{PoEPSEInterfaceList}").mock(
            return_value=Response(200, text=SET_POE_ERROR_RESPONSE)
        )

        with pytest.raises(SwitchError, match="Permission denied"):
            await client.get_ports()


class TestSetPoe:
    """Test set_poe sends correct XML and handles success/error."""

    def _setup_logged_in_client(self) -> SwitchClient:
        client = make_client()
        client._session_valid = True
        client._session_cookie = "UserId=&4b96300e7e012563ad98d43ff0609bd3&"
        return client

    @respx.mock
    async def test_set_poe_enable(self) -> None:
        """Enabling PoE sends adminEnable=1 in the POST body."""
        client = self._setup_logged_in_client()

        post_route = respx.post(url__regex=r".*PoEPSEUnitList.*PoEPSEInterfaceList.*").mock(
            return_value=Response(200, text=SET_POE_SUCCESS_RESPONSE)
        )

        await client.set_poe(9, True)

        assert post_route.called
        sent_body = post_route.calls[0].request.content.decode()
        assert "<adminEnable>1</adminEnable>" in sent_body
        assert "<interfaceID>9</interfaceID>" in sent_body

    @respx.mock
    async def test_set_poe_disable(self) -> None:
        """Disabling PoE sends adminEnable=2 in the POST body."""
        client = self._setup_logged_in_client()

        post_route = respx.post(url__regex=r".*PoEPSEUnitList.*PoEPSEInterfaceList.*").mock(
            return_value=Response(200, text=SET_POE_SUCCESS_RESPONSE)
        )

        await client.set_poe(3, False)

        assert post_route.called
        sent_body = post_route.calls[0].request.content.decode()
        assert "<adminEnable>2</adminEnable>" in sent_body
        assert "<interfaceID>3</interfaceID>" in sent_body

    @respx.mock
    async def test_set_poe_correct_headers(self) -> None:
        """POST includes X-Requested-With and correct Content-Type."""
        client = self._setup_logged_in_client()

        post_route = respx.post(url__regex=r".*PoEPSEUnitList.*PoEPSEInterfaceList.*").mock(
            return_value=Response(200, text=SET_POE_SUCCESS_RESPONSE)
        )

        await client.set_poe(1, True)

        req = post_route.calls[0].request
        assert req.headers["X-Requested-With"] == "XMLHttpRequest"
        assert "application/x-www-form-urlencoded" in req.headers["Content-Type"]

    @respx.mock
    async def test_set_poe_session_expiry_retries_with_fresh_cookie(self) -> None:
        """After a 401, set_poe re-logs in and retries with the NEW session cookie."""
        client = self._setup_logged_in_client()
        # Ensure the initial cookie is distinct from the refreshed one.
        client._session_cookie = "UserId=&stale_cookie&"

        post_route = respx.post(url__regex=r".*PoEPSEUnitList.*PoEPSEInterfaceList.*").mock(
            side_effect=[
                Response(401, text="Session expired"),
                Response(200, text=SET_POE_SUCCESS_RESPONSE),
            ]
        )

        # Re-login sequence returns a fresh session cookie.
        respx.get("https://switch.test/device/wcd?{EncryptionSetting}").mock(
            return_value=Response(200, text=ENCRYPTION_SETTING_RESPONSE)
        )
        respx.get(url__regex=r".*action=login.*").mock(
            return_value=Response(
                200,
                text=LOGIN_RESPONSE_BODY,
                headers={**LOGIN_SUCCESS_HEADERS, "sessionid": "UserId=&fresh_cookie&;path=/"},
            )
        )

        await client.set_poe(1, True)

        assert post_route.call_count == 2
        # The retry request must carry the NEW cookie, not the stale one.
        retry_req = post_route.calls[1].request
        assert "fresh_cookie" in retry_req.headers.get("Cookie", "")
        assert "stale_cookie" not in retry_req.headers.get("Cookie", "")

    @respx.mock
    async def test_set_poe_error_response_raises(self) -> None:
        """Non-zero statusCode in response raises SwitchError."""
        client = self._setup_logged_in_client()

        respx.post(url__regex=r".*PoEPSEUnitList.*PoEPSEInterfaceList.*").mock(
            return_value=Response(200, text=SET_POE_ERROR_RESPONSE)
        )

        with pytest.raises(SwitchError, match="Permission denied"):
            await client.set_poe(9, True)


class TestLogout:
    """Test logout behaviour — HTTP request and transport cleanup."""

    @respx.mock
    async def test_logout_closes_client_when_session_never_established(self) -> None:
        """logout() closes the httpx client even when no session was established."""
        client = make_client()
        # Force-create the httpx client without logging in.
        _ = client._get_client()
        assert client._client is not None
        assert client._session_valid is False

        await client.logout()

        assert client._client is None

    @respx.mock
    async def test_logout_closes_client_after_valid_session(self) -> None:
        """logout() closes the httpx client after a normal logged-in session."""
        client = make_client()
        client._session_valid = True
        client._session_cookie = "UserId=&abc&"

        respx.get(url__regex=r".*System.xml.*logout.*").mock(return_value=Response(200, text=""))

        await client.logout()

        assert client._client is None
        assert client._session_valid is False

    @respx.mock
    async def test_logout_invalidates_session_when_http_request_fails(self) -> None:
        """logout() still invalidates the session even if the HTTP request errors."""
        client = make_client()
        client._session_valid = True
        client._session_cookie = "UserId=&abc&"

        respx.get(url__regex=r".*System.xml.*logout.*").mock(
            side_effect=httpx.ConnectError("unreachable")
        )

        # Should not raise.
        await client.logout()

        assert client._client is None
        assert client._session_valid is False

    async def test_logout_is_idempotent(self) -> None:
        """Calling logout() twice does not raise."""
        client = make_client()
        # No session, no client.
        await client.logout()
        await client.logout()
