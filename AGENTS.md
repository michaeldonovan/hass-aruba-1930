# AGENTS.md

## Project Goal

Expose tools for monitoring and controlling PoE on Aruba 1930 switches.

This repo contains two deliverables that share a single core library:

1. **Standalone REST API** (`aruba1930api/main.py`): Optional FastAPI server for external integrations.
2. **Home Assistant Custom Integration** (`custom_components/aruba1930/`): Native HA component that uses `SwitchClient` directly — no separate API instance required.

Both consume `aruba1930api.switch_client.SwitchClient`, which handles all HTTP/XML protocol details.

## Key Constraints

- **No Native API/CLI**: The switches lack a built-in API or CLI; all interactions go through the switch's internal HTTP/XML interface (reverse-engineered from the web UI).
- **Single switch per instance**: Each API instance / HA config entry manages one switch.
- **Auth**: Single static API key for the REST API (env var); username/password for the HA integration (stored in config entry).
- **Deployment**: REST API supports local dev and Docker container. HA integration is installed as a custom component (HACS or manual copy).

## Stack

- **Runtime**: Python 3.11+
- **Shared Library**: `aruba1930api/` — `SwitchClient`, RSA crypto, XML parsing
- **REST API**: FastAPI (optional, async, auto-generates OpenAPI docs)
- **HA Integration**: `custom_components/aruba1930/` — config flow, DataUpdateCoordinator, switch + sensor platforms
- **HTTP Client**: httpx (async) — no browser automation needed
- **Crypto**: `cryptography` library (RSA PKCS#1 v1.5 for switch login)
- **Config**: Pydantic Settings for REST API; HA config entry for integration
- **Testing**: pytest + pytest-asyncio + httpx + pytest-homeassistant-custom-component
- **Docker**: Python slim image (~50MB) for REST API

## Switch Protocol (from HAR analysis)

### URL Structure
All switch endpoints live under a static path prefix: `https://<host>/<session_path>/hpe/...`
The `<session_path>` (e.g. `cs7acddc6f`) is a fixed segment, not per-session.

### Authentication Flow
1. **Fetch RSA key**: `GET /<path>/hpe/wcd?{ConnectedUserList}{EncryptionSetting}`
   - Returns `rsaPublicKey` (PEM), `loginToken`, `passwEncryptEnable`
2. **Encrypt credentials**: If `passwEncryptEnable == 1`, encrypt the credential string with RSA PKCS#1 v1.5, hex-encode the result. The JS does: `"crypto_!" + rsa.encrypt(value)` — need to confirm exact plaintext format (likely `"username\npassword"` or similar concatenation) against live hardware.
3. **Login**: `GET /<path>/hpe/config/system.xml?action=login&cred=<hex>`
   - Response headers: `sessionid` (cookie value), `csrftoken`
4. **Logout**: `GET /System.xml?action=logout`

### PoE Endpoints
- **List ports**: `GET /<path>/hpe/wcd?{PoEPSEInterfaceList}`
  - Returns XML with per-port: `interfaceName`, `interfaceID`, `adminEnable` (1=on, 2=off), `detectionStatus`, `outputVoltage`, `outputCurrent`, `outputPower`, `powerLimit`, `powerPriority`, etc.
- **Set PoE**: `POST /<path>/hpe/wcd?{...}` with XML body:
  ```xml
  <?xml version='1.0' encoding='utf-8'?>
  <DeviceConfiguration>
    <PoEPSEInterfaceList action="set">
      <Interface>
        <interfaceName>9</interfaceName>
        <interfaceID>9</interfaceID>
        <adminEnable>1</adminEnable>          <!-- 1=enable, 2=disable -->
        <timeRangeName></timeRangeName>
        <powerPriority>2</powerPriority>
        <portLegacy_powerDetectType>2</portLegacy_powerDetectType>
        <powerManagementMode>1</powerManagementMode>
        <portClassLimit>4</portClassLimit>
      </Interface>
    </PoEPSEInterfaceList>
  </DeviceConfiguration>
  ```
  - Response: `<statusCode>0</statusCode>` and `<statusString>OK</statusString>` on success.
  - Request header: `X-Requested-With: XMLHttpRequest`
  - Content-Type: `application/x-www-form-urlencoded; charset=UTF-8`

### Session Notes
- No cookies used — session is URL-path-based.
- Switch web UI likely allows only 1-2 concurrent sessions; serialize access.
- Sessions time out — re-auth on failure or use keepalive polling.

## Home Assistant Integration Architecture

### Design Principles
- **Direct connection**: The HA integration instantiates `SwitchClient` directly. No local REST API server is required.
- **Shared library**: `aruba1930api.switch_client.SwitchClient` is the single source of truth for switch communication. Both the FastAPI server and the HA integration import from the same module.
- **Import bootstrap**: `custom_components/aruba1930/__init__.py` implements a try/except import strategy:
  1. Try `from aruba1930api.switch_client import ...`
  2. On `ImportError`, insert the repo root into `sys.path` and retry.
  This supports symlinked repos, copied `custom_components/`, and `pip install -e .`.

### Directory Layout
```
aruba1930api/                         # repo root
├── aruba1930api/                     # shared Python package
│   ├── __init__.py
│   ├── switch_client.py              # core async client
│   ├── settings.py
│   └── main.py                       # optional standalone FastAPI
├── custom_components/
│   └── aruba1930/                    # HA domain = aruba1930
│       ├── __init__.py               # setup/unload entry, import bootstrap
│       ├── manifest.json
│       ├── const.py                  # DOMAIN, PLATFORMS, dataclass, status map
│       ├── entity.py                 # Base entity class with port lookup
│       ├── config_flow.py            # UI setup wizard
│       ├── coordinator.py            # DataUpdateCoordinator
│       ├── switch.py                 # PoE SwitchEntity per port
│       ├── sensor.py                 # Power/Voltage/Current/Status sensors
│       ├── strings.json
│       └── translations/
│           └── en.json
├── tests/                            # all tests (SwitchClient + HA integration)
├── hacs.json                         # HACS metadata
└── pyproject.toml
```

### Entity Mapping
For each port returned by `SwitchClient.get_ports()`:

| Platform | Entity | Default |
|---|---|---|
| `switch` | PoE on/off per port | Enabled |
| `sensor` | Power (W) per port | Enabled |
| `sensor` | Status (none / delivering_power / unknown) per port | Enabled |
| `sensor` | Voltage (V) per port | **Disabled** |
| `sensor` | Current (A) per port | **Disabled** |

All entities link to a single Device Registry entry named "Aruba 1930".

### Polling & Serialization
- `DataUpdateCoordinator` polls `SwitchClient.get_ports()` every 30 seconds.
- `SwitchClient` already serializes all switch access via an internal `asyncio.Lock`, so the coordinator's refresh is naturally serialized even if multiple entities trigger updates.
- When a user toggles a switch, `async_turn_on/off` calls `set_poe()` directly, then immediately requests a coordinator refresh so all entities update.

### Config Flow
- Fields: Host, Session Path, Username, Password, Verify SSL
- Validation: instantiate `SwitchClient`, call `login()`, then `logout()`
- Errors: `cannot_connect` (network), `invalid_auth` (credentials)
- Deduplication: `unique_id = host`; aborts if already configured
- Startup resilience: `ConfigEntryNotReady` is raised if the switch is unreachable during HA startup, triggering automatic retry with backoff

## Build Plan

### Phase 1: Switch Client (Completed)
`aruba1930api/switch_client.py` with:
- `SwitchClient(host, session_path, username, password)`
- `login()` → fetch RSA key, encrypt creds, authenticate
- `get_ports()` → parse PoEPSEInterfaceList XML
- `set_poe(port_id, enabled)` → POST XML toggle
- `logout()`
- Auto-re-login on session expiry

### Phase 2: REST API (Completed)
`aruba1930api/main.py` with FastAPI:
- `GET /health`, `GET /ports`, `GET /ports/{id}`, `PUT /ports/{id}/poe`
- API key auth via `X-API-Key`
- Optional standalone server

### Phase 3: Packaging (Completed)
- `Dockerfile`, `.env.example`, `pyproject.toml`, basic README

### Phase 4: Home Assistant Integration
- Restructure repo (`src/aruba1930api` → `aruba1930api/`)
- Create `custom_components/aruba1930/` with manifest, config flow, coordinator, switch, sensor
- Add `const.py` and `entity.py` for shared constants and base class
- Add `hacs.json` for HACS compatibility
- Add tests for config flow, switch platform, sensor platform
- Update README with HA integration instructions

## Code Conventions

- **Shared library** (`aruba1930api/`): strict typing, full ruff + mypy
- **HA integration** (`custom_components/aruba1930/`): follows HA patterns; ruff ignores `ANN` for `hass` args
- **Constants**: always import from `const.py`; never hardcode `DOMAIN` or platform names
- **Base entity**: all platform entities inherit from `Aruba1930Entity` in `entity.py`
- **Tests**: mock `SwitchClient` with `AsyncMock`; do not require real hardware

## Open Questions

**Resolved by live hardware testing (2026-04-22):**

- **RSA credential plaintext** — CONFIRMED: `"user={username}&password={url_encoded_password}&ssd=true&token={loginToken}&"`. The password is URL-encoded (`urllib.parse.quote`) before RSA encryption, matching the JS `encodeURIComponent` call. Implemented correctly in `switch_client.py`.
- **csrftoken on POST requests** — NOT required. The switch returns `csrftoken` at login but `set_poe()` POST requests succeed without sending it. Stored in `self._csrf_token` for future use if needed.
- **session_path stability** — Presumed static/firmware-embedded (e.g. `cs7acddc6f`). Confirmed present and unchanged; reboots not tested but the path is documented as static in the switch firmware.
- **detection_status values** (observed from 24-port switch): `2` = no device connected (searching), `3` = delivering power. These match `DETECTION_STATUS_MAP` in `const.py`.
- **Port data shape confirmed** — 24 ports; `power_limit_mw = 30000` (30W default); `priority = 1` (critical) for port 1, `priority = 2` (high) for all others. Voltage/current/power are `0` when no device attached.

**Still open:**

- What does the `session_path` represent exactly, and is it stable across switch reboots? (Not yet tested.)
