# ESP32-S3 Wokwi integration

Phase 6 keeps the HimRakshak backend and Phase 5 virtual gateway authoritative.
The firmware is a software-only sender: Wokwi models sensor inputs, local
indicators, Wi-Fi, and HTTPS, while the backend still validates readings,
reconciles sequences, and calculates risk.

## Data flow

```text
potentiometers/button + MPU6050
        -> ESP32-S3 local reading and alert
        -> bounded packet queue
        -> HTTPS /api/v2/radio/transmissions
        -> Phase 5 VirtualEdgeGateway
        -> schema validation, sequence reconciliation, backend risk
```

The packet payload uses `SIMULATED` timestamps only with
`WOKWI_SOFTWARE_SIMULATION`. The envelope preserves device sequence and
contains stable packet identity (`idempotency_key`) plus a new attempt
identity (`transmission_id`) for retries.

## Reliability and outage behavior

Sensor acquisition and local alert outputs run before network work and on every
loop. Wi-Fi connection attempts are scheduled with `millis()`, not a blocking
startup loop. A ten-entry RAM FIFO queues readings. Network failures, timeout,
429, and 5xx responses retry with capped exponential backoff; `Retry-After` is
honored and bounded for 429 responses. Permanent 400, 401, 403, 404, and 409
responses are reported and removed rather than retried forever. Device states
expose offline queueing, retrying, queue full, sensor fault, and local-only
operation. A reset loses queued packets by design.

## Authorization boundary

The Phase 5 v2 transmission route accepts a station-scoped device token in
remote mode. Firmware does not contain or request an admin credential. The
optional `HIMRAKSHAK_DEVICE_TOKEN` compile-time hook is empty by default and
must be supplied outside tracked source for a live demonstration; the server
maps it through `HIMRAKSHAK_DEVICE_TOKENS`. The token cannot change radio
configuration or invoke administrative routes.

## Validation boundary

Python contract and risk-parity tests, JSON validation, and source checks can
run locally. Arduino CLI/PlatformIO and live Wokwi execution are optional and
must be reported as unavailable when not installed; no compile or cloud result
is inferred from static checks.
