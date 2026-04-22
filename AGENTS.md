# AGENTS.md

## Project Goal

Expose tools for monitoring and controlling PoE on Aruba 1930 switches.

This repo ships two deliverables:

1. **Standalone REST API** (`aruba1930api/main.py`): Optional FastAPI server for external integrations.
2. **Home Assistant Custom Integration** (`custom_components/aruba1930/`): Native HA component with per-port switches and sensors.

Both use the same switch protocol implementation. The canonical `SwitchClient` currently lives in `custom_components/aruba1930/switch_client.py`, and `aruba1930api/switch_client.py` is a compatibility shim that re-exports it for the REST API and tests.

## Key Constraints

- **No native API or CLI**: All interaction goes through the switch's internal HTTP/XML interface.
- **Single switch per instance**: Each REST API process or HA config entry manages one switch.
- **Auth**: REST API uses a static API key. HA stores username/password in the config entry.
- **TLS**: Self-signed certs are common; both API and HA support disabling SSL verification.
- **Session limits**: Switch access is serialized through a single async lock in `SwitchClient`.

## Current Layout

```text
aruba1930api/
├── aruba1930api/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app
│   ├── settings.py                # Pydantic settings from env/.env
│   └── switch_client.py           # compatibility shim to HA client
├── custom_components/
│   └── aruba1930/
│       ├── __init__.py            # config entry setup/unload
│       ├── config_flow.py         # setup, reconfigure, options flow
│       ├── const.py               # domain constants and runtime dataclass
│       ├── coordinator.py         # DataUpdateCoordinator
│       ├── entity.py              # shared entity base
│       ├── manifest.json
│       ├── sensor.py              # power, status, voltage, current
│       ├── strings.json
│       ├── switch.py              # PoE switch entities
│       ├── switch_client.py       # canonical protocol implementation
│       └── translations/en.json
├── tests/
│   ├── test_api.py
│   ├── test_config_flow.py
│   ├── test_coordinator.py
│   ├── test_init.py
│   ├── test_sensor.py
│   ├── test_settings.py
│   ├── test_switch.py
│   └── test_switch_client.py
├── .pre-commit-config.yaml
├── Dockerfile
├── README.md
├── hacs.json
├── pyproject.toml
└── uv.lock
```

## Current Behavior

### REST API

- `aruba1930api/main.py` exposes `GET /health`, `GET /ports`, `GET /ports/{id}`, and `PUT /ports/{id}/poe`.
- All endpoints require `X-API-Key`.
- The FastAPI lifespan creates a shared `SwitchClient`, attempts login on startup, and logs out on shutdown.

### Home Assistant Integration

- `custom_components/aruba1930/__init__.py` creates `SwitchClient` directly from config entry data.
- `config_flow.py` supports initial setup, reconfigure, and an options flow for `poll_interval`.
- `coordinator.py` polls `get_ports()` on a configurable interval; default is 30 seconds.
- `switch.py` toggles PoE per port and requests an immediate coordinator refresh.
- `sensor.py` exposes power and status by default, with voltage and current disabled by default.

### Entity Mapping

For each port returned by `SwitchClient.get_ports()`:

| Platform | Entity | Default |
|---|---|---|
| `switch` | PoE on/off per port | Enabled |
| `sensor` | Power (W) per port | Enabled |
| `sensor` | Status (`none` / `delivering_power` / `unknown`) per port | Enabled |
| `sensor` | Voltage (V) per port | Disabled |
| `sensor` | Current (A) per port | Disabled |

## Switch Protocol As Implemented

### URL Structure

- Switch operations use `https://<host>/<session_path>/hpe/...`.
- The `session_path` is treated as a static path segment taken from the switch UI URL.

### Authentication Flow

1. Fetch encryption settings from `https://<host>/device/wcd?{EncryptionSetting}`.
2. Build plaintext credentials as `user={username}&password={url_encoded_password}&ssd=true&token={loginToken}&`.
3. Encrypt with RSA PKCS#1 v1.5 when `passwEncryptEnable == 1`.
4. Login with `GET /<session_path>/hpe/config/system.xml?action=login&cred=<hex>`.
5. Store the `sessionid` response header and send it back as a `Cookie` header on later requests.

If `passwEncryptEnable == 0`, the client refuses to send plaintext credentials.

### PoE Endpoints

- **List ports**: `GET /<session_path>/hpe/wcd?{PoEPSEInterfaceList}`
- **Set PoE**: `POST /<session_path>/hpe/wcd?{PoEPSEUnitList}{DiagnosticsUnitList}{PoEPSEInterfaceList}`
- `set_poe()` sends the XML body observed from the switch UI and expects `<statusCode>0</statusCode>` on success.

### Session Handling

- `SwitchClient` serializes all switch access with an internal `asyncio.Lock`.
- `401` and `403` responses invalidate the session and trigger one automatic re-login attempt.
- `logout()` calls `https://<host>/System.xml?action=logout` and closes the shared `httpx.AsyncClient`.

## Testing And Verification

- Tests cover the FastAPI layer, settings, switch client, and the HA integration setup/coordinator/config flow/entities.
- Tests use mocks and `respx`; they do not require real hardware.
- After making code changes, run `uv run pytest`.

## Code Conventions

- **Runtime**: Python 3.11+.
- **Typing**: `mypy` runs in strict mode.
- **Linting/formatting**: `ruff` plus the hooks in `.pre-commit-config.yaml`.
- **Switch protocol changes**: Update `custom_components/aruba1930/switch_client.py`; keep the shim in `aruba1930api/switch_client.py` compatible.
- **Constants**: Import from `custom_components/aruba1930/const.py`; do not hardcode `DOMAIN`, config keys, or platform lists.
- **Tests**: Mock `SwitchClient` for HA and API tests unless the test is specifically exercising the HTTP protocol layer.

## Open Question

- The `session_path` appears static and firmware-defined, but stability across switch reboots has not been verified.
