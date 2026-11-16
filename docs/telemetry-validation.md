# Telemetry and risk validation

Phase 7 validates the software-only HimRakshak telemetry lifecycle without
claiming physical radio, Wokwi runtime, field calibration, or geotechnical
prediction.

## Lifecycle and authority

```text
ESP32-S3 sensor values
  -> rounded canonical JSON payload
  -> LoRaPacket bytes
  -> VirtualLoRaChannel
  -> ReceivedPacket and radio metrics
  -> VirtualEdgeGateway JSON/schema validation
  -> StationManager sequence reconciliation
  -> risk.assess_risk()
  -> bounded station and gateway histories
```

The firmware rounds the four numeric measurements to one decimal place before
local risk display and serialization. This makes the local demonstration
assessment use the same values that the backend receives. The Python backend
remains authoritative: client-supplied risk fields, scores, reasons, model
identifiers, and illustrative flags are retained only as metadata and never
override `assess_risk()`.

The canonical measurements are soil moisture percent (0-100), tilt degrees
(0-15), vibration level (0-100), and battery percent (0-100). Missing,
non-finite, boolean, negative, and over-range values are rejected. Legacy
aliases remain accepted for API v1 compatibility. Unknown metadata is retained
but is not trusted as a measurement or risk result.

## Risk vectors

The reproducible vectors cover normal operation, each warning input boundary,
the score warning boundary, critical tilt, the critical moisture/tilt
combination, and the critical score boundary. They are executed against the
Python engine in `tests/test_risk_validation.py`. Firmware comparison is
source-level because Arduino CLI, PlatformIO, and Wokwi CLI/runtime were not
available during validation.

The model is the existing illustrative engine
`himrakshak-demo-risk-engine-v1`. It uses the documented moisture, tilt, and
vibration weights and thresholds in `docs/risk-model.md`; no ML model or
scientific accuracy claim is introduced.

## Identity, sequences, and timestamps

`packet_id` identifies a logical reading. `attempt_id` changes for each
transmission attempt, while `idempotency_key` identifies the submission
attempt at the gateway boundary. Duplicate radio copies preserve logical
identity and are accepted by the backend at most once. `StationManager` alone
classifies equal sequences as duplicates and lower sequences as stale.

Sensor acquisition timestamps remain inside the reading payload. `SIMULATED`
is valid only with `WOKWI_SOFTWARE_SIMULATION`. Gateway and station event
timestamps are separate UTC processing timestamps; they do not replace the
sensor timestamp. Radio send/receive times are simulated channel metadata.
Browser rendering time is outside the backend contract.

## Failure categories and bounds

The channel, gateway, schema, station, and API diagnostics distinguish packet
loss, queue-full, gateway unavailability, invalid/schema payloads, duplicate
logical packets, stale sequences, and backend rejection. Channel, gateway,
idempotency, station event, and diagnostic histories are bounded in memory.
Restarting the software state clears those in-memory caches; accepted
historical data is not durable.

The Phase 5 transmission endpoint remains protected by the existing admin
authorization boundary in remote mode. The Wokwi firmware does not embed an
admin key, so protected remote submission requires a future least-privilege
device-authentication mechanism. No bypass was added.

## Validation boundary

Run the complete suite with:

```powershell
python -m unittest discover -s tests -v
```

Phase 6 baseline before Phase 7 was 152 tests. Phase 7 adds contract, risk,
and end-to-end coverage. Firmware source checks validate the envelope,
identity, rounding, secure transport, and thresholds; they are not a firmware
compile or live Wokwi execution.
