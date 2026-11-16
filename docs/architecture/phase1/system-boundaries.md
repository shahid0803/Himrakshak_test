# HimRakshak System Boundaries

## 1. Browser versus backend

### Browser responsibilities

- render current backend state and assessment;
- run standalone synthetic simulation only when explicitly in standalone mode;
- submit public telemetry packets;
- show protected-operation failures clearly;
- display channel/gateway/power diagnostics as simulated data;
- export the visible session/history where supported.

### Backend responsibilities

- validate and normalize telemetry;
- enforce station allowlisting and device sequence semantics;
- calculate authoritative risk;
- maintain bounded station/event state;
- enforce remote rate limiting and administrative authorization;
- expose gateway and emulator diagnostics after v2 implementation.

The browser must never treat an unavailable backend as permission to invent
cloud telemetry or backend history.

## 2. ESP32 local versus cloud

### ESP32 local responsibilities

- sample virtual inputs;
- perform local validation and advisory risk;
- drive local indicators;
- own device sequence;
- buffer and retry packets;
- reconcile duplicates/stale packets.

### Cloud/backend responsibilities

- authoritative schema and risk assessment;
- accepted event history;
- station sequence conflict response;
- cross-node overview;
- bounded server-side reliability state.

The cloud must not trust local risk labels. The ESP32 must not require the
cloud to continue local alerts.

## 3. Virtual LoRa boundary

The virtual channel accepts a logical packet and produces a modelled
transmission outcome. It may add delay, loss, duplication, reordering, and
configuration metadata. It does not provide:

- physical radio range;
- actual RF propagation;
- calibrated RSSI/SNR;
- SX1262 register behavior;
- antenna or interference evidence;
- regulatory compliance evidence.

Any physical SX1262 adapter must be implemented separately and identified by a
different transport value.

## 4. Offline and recovery boundary

Offline state is local to each layer:

- ESP32 queue: local RAM, bounded, lost on reset;
- channel queue: emulator process state, bounded;
- gateway queue: bounded retry state;
- backend station state: current in-memory v1 behavior.

Recovery uses stable packet identity and device sequence. A timeout is
ambiguous, not proof of rejection. Retries must reconcile before removing a
queued packet.

## 5. Security boundary

- v1 public ingestion is intentionally unauthenticated and accepts only
  allowlisted station IDs plus schema-valid packets.
- v1 simulation and fault controls require the configured admin key in remote
  mode and are disabled when no key is configured.
- v2 configuration, power controls, and emulator mutation remain admin-only.
- Admin credentials never appear in browser source, Wokwi firmware, logs, or
  public documentation.
- TLS protects HTTPS transport where used, but it does not authenticate a
  sender in the current public ingestion design.
- No sensitive or real personal/geospatial data belongs in this prototype.

## 6. Deployment boundary

### Local

The Python server binds to `127.0.0.1:8765` by default, serves the dashboard
and API from one origin, and permits local simulation controls.

### Render/cloud

Render runs `python -m himrakshak.server --allow-remote` on `0.0.0.0:$PORT`.
The health path is `/api/health`. Remote state is in-memory and may reset on
cold start/restart. Public ingestion remains available for demonstration
senders; administrative routes are protected.

### Static Pages

GitHub Pages publishes the browser-only dashboard. It does not host Python,
the gateway, the channel, or the v2 diagnostics services.

## 7. Failure ownership

| Failure | Owner | Required user-visible state |
|---|---|---|
| Sensor input invalid | ESP32/schema layer | packet rejected; local error |
| Channel drop/delay | virtual channel | simulated transport outcome |
| Gateway unavailable | gateway | queued/retrying, not accepted |
| Backend 409 | gateway/sender reconciliation | duplicate/stale/superseded classification |
| Backend 429 | gateway/sender retry | retry-after/backoff |
| Backend unavailable | gateway/browser | unavailable; preserve queue/last known state |
| Browser offline | browser | standalone or unavailable mode, never false cloud state |

## 8. Deployment and observability principles

Every diagnostic must identify its source (`local`, `channel`, `gateway`, or
`backend`) and whether it is measured, configured, or simulated. A successful
gateway receipt is not a successful backend acceptance. A backend assessment
is not a physical safety warning.
