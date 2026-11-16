# HimRakshak API v2 Proposal

## Status and compatibility rule

This is a proposal only. No endpoints are implemented by Phase 1.

The existing routes do not contain a `/v1` path segment, but they are treated
as API v1 for compatibility. Existing request and response shapes, aliases,
status codes, sequence semantics, and security behavior remain unchanged.
New functionality uses `/api/v2`.

## Existing API v1 contract

### Read-only routes

| Method and route | Request | Success response |
|---|---|---|
| `GET /api/health` | none | `{status, service, api_version, model_id, illustrative, station_count}` |
| `GET /api/state` | none | `{latest, events}`; legacy HR-01-compatible latest result and global bounded events |
| `GET /api/stations` | none | `{stations: [...], events: [...]}` |
| `GET /api/stations/{node_id}` | none | `{station: {...}}` |

Station summaries contain `node_id`, `label`, `scenario`,
`receiver_connected`, `next_sequence`, `latest`, `event_count`, and
`communication`. Station details additionally contain `events` and `pending`.

### Telemetry and simulation routes

| Method and route | Request | Success response |
|---|---|---|
| `POST /api/readings` | canonical or legacy-alias reading; station defaults to HR-01 | `{reading, assessment}` |
| `POST /api/stations/{node_id}/readings` | canonical or alias reading whose normalized node ID matches the URL | `{reading, assessment}` |
| `POST /api/simulate` | `{"scenario": ...}`; optional `station` or `node_id` | `{reading, assessment}` |
| `POST /api/stations/{node_id}/simulate` | `{"scenario": ...}` | `{reading, assessment}` |

Supported scenarios are `normal`, `heavy_rain`, `slope_shift`, and
`vibration_burst`. Simulation routes are administratively protected in remote
mode and open in local mode without an admin key.

### Reliability routes

All routes are `POST /api/stations/{node_id}/faults/{action}`:

`drop`, `delay`, `release`, `deliver`, `duplicate`, `stale`, `disconnect`,
and `reconnect`.

Packet actions accept a reading directly or as `{"reading": {...}}`.
`release`, `disconnect`, and `reconnect` accept `{}` or an empty body.
Successful responses contain `outcome`; delivery responses also contain
`reading`, `assessment`, and `communication`. These routes are protected in
remote mode.

### v1 validation

- Required: `node_id`, `sequence`, `timestamp`, `soil_moisture_pct`,
  `tilt_deg`, `vibration_level`, `battery_pct`.
- Legacy aliases: `node`, `moisture`, `tilt`, `vibration`.
- `node_id`: trimmed non-empty string, maximum 40 characters.
- `sequence`: non-negative integer; booleans rejected.
- `timestamp`: timezone-aware ISO 8601; `SIMULATED` allowed only with exact
  `transport: WOKWI_SOFTWARE_SIMULATION`.
- Soil moisture: 0–100; tilt: 0–15; vibration: 0–100; battery: 0–100.
- Numeric values must be finite and booleans are rejected.
- Canonical/alias pairs must match when both are supplied.
- Unknown metadata is retained; supplied risk fields are not trusted.
- Only `HR-01`, `HR-02`, and `HR-03` are registered stations.
- Accepted device sequences are preserved. Equal latest sequence is duplicate;
  lower sequence is stale.
- History is bounded to 100 events and state is in-memory only.
- Request bodies are limited to 64 KiB.

### v1 errors

```json
{
  "error": {
    "status": 400,
    "message": "human-readable message"
  }
}
```

Observed statuses are:

- `400`: malformed JSON, non-object body, invalid schema, alias conflict,
  invalid scenario, or station identity mismatch;
- `401`: missing remote administrative header;
- `403`: invalid admin header or remote mutation disabled without a key;
- `404`: unknown station, route, or reliability action;
- `405`: unsupported method;
- `409`: duplicate/stale sequence, disconnected station, full queue, or empty
  release queue;
- `413`: body over 64 KiB;
- `429`: remote ingestion rate limit, with `Retry-After`;
- `500`: unexpected processing failure.

Sequence conflicts additionally include `classification`, `sequence`, and
`latest_sequence`.

## Proposed v2 resource model

All v2 response envelopes should include:

```json
{
  "api_version": 2,
  "generated_at": "2026-11-16T17:00:00Z",
  "data": {}
}
```

`generated_at` is the server response time, not sensor time.

### Virtual radio transmission

`POST /api/v2/radio/transmissions`

Request:

```json
{
  "transmission_id": "tx-HR-01-000042-a1b2",
  "idempotency_key": "HR-01:42:a1b2",
  "node_id": "HR-01",
  "device_sequence": 42,
  "created_at": "2026-11-16T17:00:00Z",
  "payload": {
    "node_id": "HR-01",
    "sequence": 42,
    "timestamp": "2026-11-16T17:00:00Z",
    "soil_moisture_pct": 70,
    "tilt_deg": 4.2,
    "vibration_level": 30,
    "battery_pct": 82,
    "transport": "VIRTUAL_LORA_SIMULATION"
  },
  "channel_profile": "baseline"
}
```

Response:

```json
{
  "api_version": 2,
  "generated_at": "...",
  "data": {
    "transmission_id": "...",
    "idempotency_key": "...",
    "status": "scheduled",
    "attempt": 1,
    "channel": "virtual-lora"
  }
}
```

The endpoint represents submission to the emulator, not backend acceptance.
The payload is validated before scheduling. Reusing an idempotency key with
the same content returns the original result; reuse with different content
returns `409`.

### Radio configuration

`GET /api/v2/radio/config` returns the active emulator profile:

```json
{
  "profile": "baseline",
  "frequency_mhz": 868.1,
  "bandwidth_khz": 125,
  "spreading_factor": 9,
  "coding_rate": "4/5",
  "configured_loss_pct": 0,
  "configured_latency_ms": 0,
  "seed": 42,
  "is_physical_radio": false
}
```

`PUT /api/v2/radio/config` accepts the same fields, with server-side bounds
and an optional `expected_revision`. Configuration mutation is admin-only and
must return `409` for a stale revision. Frequency and PHY-looking fields are
configuration labels for the emulator, not measurements or regulatory proof.

### Radio network status

`GET /api/v2/radio/status` returns:

```json
{
  "network_id": "virtual-lora",
  "profile": "baseline",
  "connected": true,
  "queued_transmissions": 0,
  "delivered_transmissions": 0,
  "dropped_transmissions": 0,
  "duplicated_transmissions": 0,
  "reordered_transmissions": 0,
  "last_transition_at": "...",
  "is_physical_radio": false
}
```

Counters describe emulator outcomes and reset according to the selected
storage policy. No RSSI/SNR values are implied.

### Per-node radio diagnostics

`GET /api/v2/stations/{node_id}/radio-diagnostics` returns:

```json
{
  "node_id": "HR-01",
  "connection_state": "connected",
  "pending_transmissions": 0,
  "attempts": 4,
  "accepted_by_gateway": 4,
  "accepted_by_backend": 3,
  "duplicate": 1,
  "stale": 0,
  "last_transmission_id": "...",
  "last_backend_sequence": 42,
  "model": {
    "name": "virtual-lora",
    "is_physical_radio": false
  }
}
```

### Gateway health

`GET /api/v2/gateway/health` returns:

```json
{
  "gateway_id": "GW-01",
  "status": "healthy",
  "process_uptime_seconds": 123,
  "channel_connected": true,
  "backend_reachable": true,
  "queued_packets": 0,
  "last_successful_forward_at": "...",
  "last_error": null
}
```

This is process and dependency health, not proof of physical gateway
availability.

### Virtual power and battery

`GET /api/v2/stations/{node_id}/power` returns:

```json
{
  "node_id": "HR-01",
  "battery_pct": 82,
  "battery_voltage_v": 3.92,
  "solar_input_w": 0.8,
  "load_w": 0.35,
  "charging": true,
  "state": "charging",
  "sampled_at": "...",
  "is_simulated": true
}
```

`POST /api/v2/stations/{node_id}/power/simulation` is an admin-only control
for changing virtual sunlight/load inputs. It must not silently rewrite the
v1 reading or risk assessment.

## Authentication and authorization

v1 public reading ingestion remains compatible and unauthenticated as a
prototype limitation. v2 emulator configuration, fault injection, power
controls, and gateway administrative operations require the existing admin
boundary or a future gateway credential. Browser clients must never receive
the admin secret. Read-only diagnostics may be public but must disclose that
values are simulated.
