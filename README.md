# aruba1930api

Monitoring and control for Power-over-Ethernet (PoE) on Aruba 1930 switches.

The Aruba 1930 has no built-in REST API or CLI. This project reverse-engineers its web UI's HTTP/XML protocol and exposes it through two interfaces:

1. **Home Assistant custom integration** — native HA component with per-port switches and sensors
2. **Standalone REST API** — optional FastAPI server for external integrations

---

## Home Assistant Integration

### Installation

This integration is designed for a self-contained local install from this repository.
The shared switch client lives in `custom_components/aruba1930/switch_client.py`, and the repo packaging installs both that package and `aruba1930api/` so the REST app can import the same implementation.

Use HACS or copy `custom_components/aruba1930` into your Home Assistant configuration directory:

```
<ha_config>/
└── custom_components/
    └── aruba1930/
```

Restart Home Assistant and add the integration via the UI.

### Config flow fields

| Field | Description |
|---|---|
| **Host** | Switch hostname or IP address (e.g. `192.168.1.1`) |
| **Session Path** | Static path prefix from the switch firmware (e.g. `cs7acddc6f`) |
| **Username** | Switch web UI login username |
| **Password** | Switch web UI login password |
| **Verify SSL** | Uncheck to skip TLS certificate verification (self-signed certs are common on switches) |

See [Finding the session path](#finding-the-session-path) below.

### Entities

The integration creates the following entities for **each PoE-capable port**:

| Platform | Entity | Unit | Enabled by default |
|---|---|---|---|
| `switch` | Port N PoE | — | Yes |
| `sensor` | Port N Power | W | Yes |
| `sensor` | Port N Status | — | Yes |
| `sensor` | Port N Voltage | V | No |
| `sensor` | Port N Current | A | No |

**Status sensor values:** `delivering_power` · `none` · `unknown`

Voltage and Current sensors are disabled by default to reduce clutter. Enable them individually in **Settings → Entities**.

### Polling

The integration polls the switch every 30 seconds. When a switch entity is toggled, the change is applied immediately and the coordinator refreshes all entities right away.

---

## Alternative: Standalone REST API

### Requirements

- Python 3.11+
- An Aruba 1930 switch reachable over HTTPS

### Quick start

```bash
cp .env.example .env
# Edit .env with your switch details and API key
uv venv && uv pip install -e .
uv run uvicorn aruba1930api.main:app --host 0.0.0.0 --port 8000
```

Interactive docs: http://localhost:8000/docs

### Docker

```bash
docker build -t aruba1930api .
docker run --env-file .env -p 8000:8000 aruba1930api
```

### Configuration

All configuration is via environment variables (or a `.env` file in the working directory).

| Variable | Required | Default | Description |
|---|---|---|---|
| `ARUBA_SWITCH_HOST` | yes | — | Switch hostname or IP address |
| `ARUBA_SWITCH_SESSION_PATH` | yes | — | Static path prefix from the switch firmware (e.g. `cs7acddc6f`) |
| `ARUBA_SWITCH_USERNAME` | yes | — | Web UI login username |
| `ARUBA_SWITCH_PASSWORD` | yes | — | Web UI login password |
| `ARUBA_API_KEY` | yes | — | API key required on all requests (`X-API-Key` header) |
| `ARUBA_SWITCH_VERIFY_SSL` | no | `true` | Set `false` to skip TLS verification (self-signed certs) |

### API endpoints

All endpoints require the `X-API-Key` header.

#### `GET /health`

Returns `200 OK` if the switch is reachable. Performs a live port list query.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/health
```

```json
{"status": "ok", "switch": "192.168.1.1"}
```

#### `GET /ports`

List all PoE-capable ports with current status.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/ports
```

```json
[
  {
    "id": 1,
    "name": "1",
    "poe_enabled": true,
    "detection_status": 3,
    "voltage_mv": 55000,
    "current_ma": 152,
    "power_mw": 8300,
    "power_limit_mw": 30000,
    "priority": 1
  }
]
```

| Field | Unit | Notes |
|---|---|---|
| `id` | — | Switch interface ID |
| `name` | — | Port label as shown in the switch UI |
| `poe_enabled` | — | `true` = PoE on, `false` = PoE off |
| `detection_status` | — | `2` = no device, `3` = device powered |
| `voltage_mv` | millivolts | `0` when no device connected |
| `current_ma` | milliamps | `0` when no device connected |
| `power_mw` | milliwatts | Current draw |
| `power_limit_mw` | milliwatts | Configured maximum |
| `priority` | — | `1` = critical, `2` = high, `3` = low |

#### `GET /ports/{id}`

Get a single port. Returns `404` if the port does not exist.

#### `PUT /ports/{id}/poe`

Enable or disable PoE on a port.

```bash
curl -X PUT -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  http://localhost:8000/ports/9/poe
```

Returns the updated port object.

---

## Finding the session path

Open the switch web UI in a browser and look at the URL. The path segment between the hostname and `/hpe/` is the session path:

```
https://192.168.1.1/cs7acddc6f/hpe/config/login.htm
                    ^^^^^^^^^^^
```

This value is static — it is embedded in the switch firmware and does not change per login or reboot.

---

## Development

```bash
uv venv && uv pip install -e ".[dev]"
```

### Running tests

Tests mock all network calls — no switch hardware required.

```bash
# Run all tests
uv run pytest

# Verbose output
uv run pytest -v

# Run a specific file
uv run pytest tests/test_switch_client.py -v
```

---

## Known limitations

- **Single switch per instance.** Run one container / config entry per switch.
- **Session serialisation.** The switch supports 1–2 concurrent web sessions. All requests are serialised through a single async lock — high request rates will queue.
