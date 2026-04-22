"""Unit tests for the FastAPI application layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from aruba1930api.main import app
from aruba1930api.switch_client import SwitchError

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_PORTS = [
    {
        "id": 1,
        "name": "1",
        "poe_enabled": True,
        "detection_status": 3,
        "voltage_mv": 55000,
        "current_ma": 152,
        "power_mw": 8300,
        "power_limit_mw": 30000,
        "priority": 1,
    },
    {
        "id": 2,
        "name": "2",
        "poe_enabled": False,
        "detection_status": 2,
        "voltage_mv": 0,
        "current_ma": 0,
        "power_mw": 0,
        "power_limit_mw": 30000,
        "priority": 2,
    },
]

VALID_API_KEY = "test-api-key-abc123"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_switch() -> MagicMock:
    """Return a MagicMock SwitchClient with async method stubs."""
    switch = MagicMock()
    switch.get_ports = AsyncMock(return_value=SAMPLE_PORTS)
    switch.set_poe = AsyncMock(return_value=None)
    return switch


@pytest.fixture()
def api_client(mock_switch: MagicMock) -> AsyncClient:
    """Return an httpx AsyncClient backed by the FastAPI app.

    Patches both the switch client singleton and the settings so tests are
    fully isolated from environment variables and real hardware.
    """
    # We patch at the module level so FastAPI dependencies see our mocks.
    with (
        patch("aruba1930api.main._switch_client", mock_switch),
        patch(
            "aruba1930api.main.get_settings",
            return_value=MagicMock(
                switch_host="switch.test",
                switch_session_path="cs7acddc6f",
                switch_username="admin",
                switch_password="secret",
                api_key=VALID_API_KEY,
                switch_verify_ssl=False,
            ),
        ),
        patch(
            "aruba1930api.settings.Settings",
            return_value=MagicMock(
                switch_host="switch.test",
                api_key=VALID_API_KEY,
            ),
        ),
    ):
        yield AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestApiKeyAuth:
    """Test API key enforcement."""

    async def test_missing_api_key_returns_401(self, api_client: AsyncClient) -> None:
        """No X-API-Key header → 401."""
        async with api_client as client:
            resp = await client.get("/health")
        assert resp.status_code == 401
        assert "X-API-Key" in resp.json()["detail"]

    async def test_wrong_api_key_returns_403(self, api_client: AsyncClient) -> None:
        """Wrong X-API-Key value → 403."""
        async with api_client as client:
            resp = await client.get("/health", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403
        assert "Invalid" in resp.json()["detail"]

    async def test_correct_api_key_passes(self, api_client: AsyncClient) -> None:
        """Correct X-API-Key → request proceeds (not 401/403)."""
        async with api_client as client:
            resp = await client.get("/health", headers={"X-API-Key": VALID_API_KEY})
        # Health may return 200 or 503 depending on mock — just not auth errors.
        assert resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    """Test GET /health endpoint."""

    async def test_health_ok(self, api_client: AsyncClient, mock_switch: MagicMock) -> None:
        """Returns 200 with status=ok when switch is reachable."""
        async with api_client as client:
            resp = await client.get("/health", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["switch"] == "switch.test"
        mock_switch.get_ports.assert_called_once()

    async def test_health_switch_error_returns_503(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """Returns 503 when switch raises SwitchError."""
        mock_switch.get_ports.side_effect = SwitchError("Connection refused")

        async with api_client as client:
            resp = await client.get("/health", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 503
        assert "Connection refused" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /ports
# ---------------------------------------------------------------------------


class TestListPorts:
    """Test GET /ports endpoint."""

    async def test_returns_all_ports(self, api_client: AsyncClient, mock_switch: MagicMock) -> None:
        """Returns a list of port dicts."""
        async with api_client as client:
            resp = await client.get("/ports", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[0]["poe_enabled"] is True
        assert data[1]["poe_enabled"] is False

    async def test_switch_error_returns_503(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """Returns 503 when the switch raises SwitchError."""
        mock_switch.get_ports.side_effect = SwitchError("timeout")

        async with api_client as client:
            resp = await client.get("/ports", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /ports/{port_id}
# ---------------------------------------------------------------------------


class TestGetPort:
    """Test GET /ports/{port_id} endpoint."""

    async def test_returns_single_port(self, api_client: AsyncClient) -> None:
        """Returns the port dict for a valid port ID."""
        async with api_client as client:
            resp = await client.get("/ports/1", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["poe_enabled"] is True
        assert data["voltage_mv"] == 55000

    async def test_returns_disabled_port(self, api_client: AsyncClient) -> None:
        """Returns the port dict for a disabled port."""
        async with api_client as client:
            resp = await client.get("/ports/2", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 2
        assert data["poe_enabled"] is False

    async def test_nonexistent_port_returns_404(self, api_client: AsyncClient) -> None:
        """Returns 404 for a port ID that does not exist."""
        async with api_client as client:
            resp = await client.get("/ports/99", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 404
        assert "99" in resp.json()["detail"]

    async def test_switch_error_returns_503(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """Returns 503 when switch raises SwitchError."""
        mock_switch.get_ports.side_effect = SwitchError("switch down")

        async with api_client as client:
            resp = await client.get("/ports/1", headers={"X-API-Key": VALID_API_KEY})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# PUT /ports/{port_id}/poe
# ---------------------------------------------------------------------------


class TestUpdatePoe:
    """Test PUT /ports/{port_id}/poe endpoint."""

    async def test_enable_poe_calls_set_poe(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """PUT with enabled=true calls set_poe(port_id, True)."""
        async with api_client as client:
            resp = await client.put(
                "/ports/1/poe",
                json={"enabled": True},
                headers={"X-API-Key": VALID_API_KEY},
            )
        assert resp.status_code == 200
        mock_switch.set_poe.assert_called_once_with(1, True)

    async def test_nonexistent_port_returns_404_before_set_poe(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """Missing port returns 404 and does not attempt a write."""
        async with api_client as client:
            resp = await client.put(
                "/ports/99/poe",
                json={"enabled": True},
                headers={"X-API-Key": VALID_API_KEY},
            )
        assert resp.status_code == 404
        mock_switch.set_poe.assert_not_called()

    async def test_disable_poe_calls_set_poe(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """PUT with enabled=false calls set_poe(port_id, False)."""
        async with api_client as client:
            resp = await client.put(
                "/ports/2/poe",
                json={"enabled": False},
                headers={"X-API-Key": VALID_API_KEY},
            )
        assert resp.status_code == 200
        mock_switch.set_poe.assert_called_once_with(2, False)

    async def test_returns_updated_port(self, api_client: AsyncClient) -> None:
        """Returns the updated port dict after toggling."""
        async with api_client as client:
            resp = await client.put(
                "/ports/1/poe",
                json={"enabled": True},
                headers={"X-API-Key": VALID_API_KEY},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1

    async def test_set_poe_error_returns_503(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """Returns 503 when set_poe raises SwitchError."""
        mock_switch.set_poe.side_effect = SwitchError("write protected")

        async with api_client as client:
            resp = await client.put(
                "/ports/1/poe",
                json={"enabled": True},
                headers={"X-API-Key": VALID_API_KEY},
            )
        assert resp.status_code == 503
        assert "write protected" in resp.json()["detail"]

    async def test_nonexistent_port_after_update_returns_404(
        self, api_client: AsyncClient, mock_switch: MagicMock
    ) -> None:
        """Returns 404 if port ID is not in the port list returned after update."""
        async with api_client as client:
            resp = await client.put(
                "/ports/99/poe",
                json={"enabled": True},
                headers={"X-API-Key": VALID_API_KEY},
            )
        assert resp.status_code == 404

    async def test_invalid_body_returns_422(self, api_client: AsyncClient) -> None:
        """Malformed request body (missing required field) returns 422."""
        async with api_client as client:
            resp = await client.put(
                "/ports/1/poe",
                json={},  # missing required 'enabled' field
                headers={"X-API-Key": VALID_API_KEY},
            )
        assert resp.status_code == 422
