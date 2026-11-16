# HimRakshak Data Model v2

## 1. Data ownership

| Model | Owner | Authority |
|---|---|---|
| Raw sensor telemetry | ESP32 sender, validated by backend | Raw observation within the simulation |
| Local ESP32 risk status | ESP32 firmware | Advisory/local only |
| Backend risk assessment | Python risk engine | Authoritative application assessment |
| Virtual LoRa metadata | Channel emulator | Simulated transport facts |
| Gateway reception metadata | Python gateway | Gateway processing facts |
| Solar/battery state | Power simulator | Simulated power facts |
| Alert/event history | Backend event store | Accepted application history |

Client-supplied risk fields are metadata only. The backend always recalculates
the assessment from validated raw telemetry.

## 2. Raw sensor telemetry

Canonical v1-compatible payload:

```json
{
  "node_id": "HR-01",
  "sequence": 42,
  "timestamp": "2026-11-16T17:00:00Z",
  "soil_moisture_pct": 70.0,
  "tilt_deg": 4.2,
  "vibration_level": 30.0,
  "battery_pct": 82.0,
  "transport": "VIRTUAL_LORA_SIMULATION"
}
```

Required v1 fields and ranges are unchanged. Optional v2 metadata may include
`sensor_sample_id`, `sensor_firmware_version`, `tilt_pitch_deg`,
`tilt_roll_deg`, `sample_duration_ms`, and `is_simulated`, but these are
non-authoritative until explicitly promoted into a versioned contract.

## 3. Local ESP32 risk status

```json
{
  "status_id": "local-HR-01-42",
  "node_id": "HR-01",
  "sequence": 42,
  "computed_at": "2026-11-16T17:00:00Z",
  "risk_level": "WARNING",
  "demo_score": 48,
  "reasons": ["Elevated simulated moisture"],
  "alert_outputs": {
    "green_led": false,
    "yellow_led": true,
    "red_led": false,
    "buzzer": false
  },
  "model_id": "himrakshak-demo-risk-engine-v1",
  "authoritative": false
}
```

Local status is useful for offline demonstrations and must be visibly
labelled as device-local. It cannot replace a backend assessment.

## 4. Backend risk assessment

The existing authoritative shape remains:

```json
{
  "risk_level": "WARNING",
  "demo_score": 48,
  "reasons": ["Elevated simulated moisture"],
  "model_id": "himrakshak-demo-risk-engine-v1",
  "illustrative": true
}
```

No client value for `risk_level`, `demo_score`, or `reasons` is trusted.
Unknown input metadata may be retained for inspection but is never merged into
the assessment.

## 5. Virtual LoRa transmission metadata

```json
{
  "transmission_id": "tx-HR-01-000042-a1b2",
  "idempotency_key": "HR-01:42:a1b2",
  "node_id": "HR-01",
  "device_sequence": 42,
  "attempt": 2,
  "queued_at": "2026-11-16T17:00:00Z",
  "released_at": "2026-11-16T17:00:00.250Z",
  "channel_profile": "baseline",
  "channel_outcome": "delivered",
  "is_physical_radio": false
}
```

`transmission_id` identifies one logical sender packet. `attempt` identifies a
retry attempt. A retry must reuse the logical transmission ID and idempotency
key, while its attempt counter increases.

## 6. Gateway reception metadata

```json
{
  "gateway_id": "GW-01",
  "received_id": "rx-GW-01-000901",
  "transmission_id": "tx-HR-01-000042-a1b2",
  "received_at": "2026-11-16T17:00:00.260Z",
  "forwarded_at": "2026-11-16T17:00:00.270Z",
  "backend_status": 200,
  "backend_outcome": "accepted",
  "backend_sequence": 42,
  "retryable": false
}
```

Gateway receipt does not mean backend acceptance. These states must remain
separate in the UI and history.

## 7. Solar and battery simulation state

```json
{
  "node_id": "HR-01",
  "sampled_at": "2026-11-16T17:00:00Z",
  "battery_pct": 82.0,
  "battery_voltage_v": 3.92,
  "solar_input_w": 0.8,
  "load_w": 0.35,
  "charging": true,
  "state": "charging",
  "is_simulated": true
}
```

This state is diagnostic. The canonical v1 `battery_pct` in a telemetry
packet remains the value used by any future model that explicitly declares it.

## 8. Alert and event history

```json
{
  "event_id": "evt-000901",
  "event_type": "backend_assessment",
  "station_id": "HR-01",
  "occurred_at": "2026-11-16T17:00:00Z",
  "source": "backend",
  "sequence": 42,
  "transmission_id": "tx-HR-01-000042-a1b2",
  "reading": {},
  "assessment": {},
  "delivery_state": "accepted"
}
```

Only accepted backend readings enter the existing station event history.
Channel, gateway, local-alert, and rejected-packet events may be stored in a
separate diagnostics stream and must not be confused with accepted telemetry.

## 9. Identity, time, and sequencing

- `node_id` identifies a registered virtual station.
- `sequence` is owned by the device and is preserved by the backend.
- `transmission_id` identifies one logical transport packet across retries.
- `attempt` identifies each channel/gateway retry.
- `idempotency_key` makes repeated submission safe.
- `timestamp` is sensor/sample time; `created_at`, `received_at`, and
  `generated_at` describe processing stages.
- All server and gateway timestamps use UTC ISO 8601 with `Z`.
- `SIMULATED` is allowed only under the existing Wokwi transport exception.

## 10. Idempotency behavior

1. Same idempotency key and same canonical payload: return the original
   transmission outcome without a second backend event.
2. Same idempotency key and different payload: return `409` conflict.
3. New idempotency key with duplicate device sequence: preserve v1 `409`
   duplicate semantics.
4. Lower device sequence: preserve v1 `409` stale semantics.
5. Gateway timeout after forwarding: retry with the same logical identity;
   never assume failure until reconciliation completes.

## 11. Retention and limits

The existing v1 station history remains bounded to 100 events and in-memory.
Any v2 diagnostics retention, queue size, payload size, and idempotency store
must be bounded and documented before implementation. No design may require
unbounded memory or silently discard an unresolved packet.
