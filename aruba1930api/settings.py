"""Runtime configuration via environment variables."""

import functools

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file.

    All variables are prefixed with ``ARUBA_`` in the environment.

    Example:
        ``ARUBA_SWITCH_HOST=192.168.1.1``
    """

    switch_host: str
    """Hostname or IP address of the Aruba 1930 switch."""

    switch_session_path: str
    """Static session path segment, e.g. ``cs7acddc6f``. Found in the switch
    web-UI URL; it is stable (does not change per login)."""

    switch_username: str
    """Switch web-UI login username."""

    switch_password: str
    """Switch web-UI login password."""

    api_key: str
    """Secret API key required by callers in the ``X-API-Key`` header."""

    switch_verify_ssl: bool = True
    """Set to ``false`` to skip TLS certificate verification (self-signed certs
    are common on switches in private networks)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ARUBA_",
        case_sensitive=False,
    )

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_empty(cls, v: str) -> str:
        """Reject an empty or whitespace-only API key at startup."""
        if not v.strip():
            raise ValueError("ARUBA_API_KEY must not be empty or whitespace")
        return v


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (reads the environment once).

    The result is cached for the lifetime of the process.  Call
    ``get_settings.cache_clear()`` in tests that need to swap env vars.
    """
    return Settings()  # type: ignore[call-arg]
