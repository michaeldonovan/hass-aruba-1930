"""FastAPI application for the Aruba 1930 PoE REST API."""

from __future__ import annotations

import hmac
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Path, status
from pydantic import BaseModel

from aruba1930api.settings import Settings, get_settings
from aruba1930api.switch_client import AuthError, SwitchClient, SwitchError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan — manage SwitchClient across application lifetime
# ---------------------------------------------------------------------------

_switch_client: SwitchClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create the SwitchClient, log in on startup, and log out on shutdown."""
    global _switch_client  # noqa: PLW0603

    settings = get_settings()
    client = SwitchClient(
        host=settings.switch_host,
        session_path=settings.switch_session_path,
        username=settings.switch_username,
        password=settings.switch_password,
        verify_ssl=settings.switch_verify_ssl,
    )
    logger.info("Connecting to Aruba 1930 switch at %s …", settings.switch_host)
    try:
        await client.login()
    except (SwitchError, AuthError) as exc:
        # Log the error but do not crash the process — the health endpoint
        # will surface the failure and the client will retry on next request.
        logger.error("Initial switch login failed: %s", exc)

    _switch_client = client
    yield

    logger.info("Shutting down — logging out of switch.")
    if _switch_client is not None:
        await _switch_client.logout()
        _switch_client = None


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Aruba 1930 PoE API",
    version="0.1.0",
    description=(
        "REST API for monitoring and controlling Power-over-Ethernet (PoE) "
        "on an Aruba 1930 switch via its reverse-engineered web interface."
    ),
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_switch_client() -> SwitchClient:
    """FastAPI dependency that returns the shared SwitchClient instance.

    Raises:
        HTTPException: 503 if the client is not yet initialised.
    """
    if _switch_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Switch client not initialised.",
        )
    return _switch_client


def get_verified_settings() -> Settings:
    """FastAPI dependency that returns validated settings."""
    return get_settings()


async def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_verified_settings),
) -> None:
    """FastAPI dependency that enforces API key authentication.

    Uses ``hmac.compare_digest`` to prevent timing-based enumeration.

    Args:
        x_api_key: Value of the ``X-API-Key`` request header.
        settings: Loaded application settings.

    Raises:
        HTTPException: 401 if the header is absent, 403 if the key is wrong.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required.",
        )
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class PoEUpdateRequest(BaseModel):
    """Request body for ``PUT /ports/{port_id}/poe``."""

    enabled: bool
    """``true`` to enable PoE on the port, ``false`` to disable."""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    dependencies=[Depends(require_api_key)],
    summary="Health check",
    tags=["health"],
)
async def health(
    switch: SwitchClient = Depends(get_switch_client),
    settings: Settings = Depends(get_verified_settings),
) -> dict[str, str]:
    """Return ``{"status": "ok"}`` if the switch is reachable.

    Performs a live ``get_ports()`` call so transient connectivity issues are
    surfaced immediately.

    Raises:
        HTTPException: 503 if the switch cannot be reached.
    """
    try:
        await switch.get_ports()
    except SwitchError as exc:
        logger.warning("Health check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Switch unreachable: {exc}",
        ) from exc

    return {"status": "ok", "switch": settings.switch_host}


@app.get(
    "/ports",
    dependencies=[Depends(require_api_key)],
    summary="List all PoE ports",
    tags=["ports"],
)
async def list_ports(
    switch: SwitchClient = Depends(get_switch_client),
) -> list[dict[str, Any]]:
    """Return the current PoE status of all switch ports.

    Raises:
        HTTPException: 503 if the switch cannot be reached.
    """
    try:
        return await switch.get_ports()
    except SwitchError as exc:
        logger.error("list_ports failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@app.get(
    "/ports/{port_id}",
    dependencies=[Depends(require_api_key)],
    summary="Get a single PoE port",
    tags=["ports"],
)
async def get_port(
    port_id: Annotated[int, Path(ge=1, description="Switch port ID (1-based)")],
    switch: SwitchClient = Depends(get_switch_client),
) -> dict[str, Any]:
    """Return the current PoE status of a specific port.

    Args:
        port_id: 1-based switch port interface ID.

    Raises:
        HTTPException: 404 if the port is not found.
        HTTPException: 503 if the switch cannot be reached.
    """
    try:
        ports = await switch.get_ports()
    except SwitchError as exc:
        logger.error("get_port(%d) failed: %s", port_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    for port in ports:
        if port["id"] == port_id:
            return port

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Port {port_id} not found.",
    )


@app.put(
    "/ports/{port_id}/poe",
    dependencies=[Depends(require_api_key)],
    summary="Enable or disable PoE on a port",
    tags=["ports"],
)
async def update_poe(
    port_id: Annotated[int, Path(ge=1, description="Switch port ID (1-based)")],
    body: PoEUpdateRequest,
    switch: SwitchClient = Depends(get_switch_client),
) -> dict[str, Any]:
    """Toggle PoE power on a specific port and return the updated port state.

    Args:
        port_id: 1-based switch port interface ID.
        body: ``{"enabled": true|false}``

    Raises:
        HTTPException: 404 if the port does not exist.
        HTTPException: 503 if the switch cannot be reached or returns an error.
    """
    try:
        ports = await switch.get_ports()
    except SwitchError as exc:
        logger.error("get_ports before set_poe failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    for port in ports:
        if port["id"] == port_id:
            try:
                await switch.set_poe(port_id, body.enabled)
            except SwitchError as exc:
                logger.error("set_poe(port=%d, enabled=%s) failed: %s", port_id, body.enabled, exc)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc

            # Fetch updated state.
            try:
                ports = await switch.get_ports()
            except SwitchError as exc:
                logger.error("get_ports after set_poe failed: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc

            for updated_port in ports:
                if updated_port["id"] == port_id:
                    return updated_port

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Port {port_id} not found after update.",
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Port {port_id} not found.",
    )
