# Virtual edge gateway

Phase 5 adds `VirtualEdgeGateway`, an in-memory adapter between the Phase 4
`VirtualLoRaChannel` and the existing `StationManager`. It is software-only:
there is no SX1262 device, RF transmission, LoRaWAN implementation, or physical
gateway.

## Architecture

```text
LoRaPacket
    -> VirtualLoRaChannel
    -> ReceivedPacket
    -> VirtualEdgeGateway
    -> validate_reading()
    -> StationManager.ingest()
    -> existing assess_risk()
```

The gateway does not calculate risk or reconcile station sequences. It preserves
the packet bytes and radio metrics, validates the canonical reading, and
delegates backend acceptance to the existing station manager. A queued channel
transmission is not a received packet and is not a backend acceptance.

## Packet identity and idempotency

`packet_id` identifies the logical reading, while `attempt_id` identifies a
transmission attempt. Duplicate radio copies retain both identities and expose
`copy_index`. The gateway keeps bounded idempotency and accepted-packet caches.
The first valid delivery can be ingested once; later copies or retries of the
same logical packet are reported as `duplicate` without creating another station
event. A reused idempotency key with different packet content is rejected.

Invalid payloads never update station state. Duplicate and stale sequence
decisions remain `StationManager` decisions and are returned as `duplicate` or
`stale` gateway outcomes with the backend reason.

## Failure and recovery

`set_gateway_available(False)` prevents new submissions and leaves due
deliveries in the channel queue while the gateway is unavailable. The virtual
channel remains responsible for its bounded queue and simulated clock.
Recovery does not erase accepted station history; queued packets are processed
through the normal validation and sequence path, while a new attempt can use a
distinct `attempt_id`. Idempotency prevents an already accepted logical packet
from being ingested twice.

Gateway statistics distinguish channel delivery, gateway validation, and backend
ingestion. Histories, idempotency entries, and channel queues are bounded.
State is in memory and is lost on process restart.

Validation diagnostics use distinct outcomes for channel loss or queue-full,
gateway unavailability, invalid/schema payloads, duplicate logical packets,
stale sequences, and backend rejection. Status responses additionally expose
gateway, channel, and ingestion state plus recovery and last-successful-forward
timestamps. A gateway history timestamp records processing time; it does not
replace the sensor timestamp in the payload.

## API v2 diagnostics

The server adds these routes without changing API v1:

* `POST /api/v2/radio/transmissions` — admin-bound emulator or device-token
  firmware submission.
* `GET /api/v2/radio/config` and admin `PUT /api/v2/radio/config`.
* `GET /api/v2/radio/status`.
* `GET /api/v2/stations/{node_id}/radio-diagnostics`.
* `GET /api/v2/gateway/health`.

v2 responses use the documented `{api_version, generated_at, data}` envelope.
Configuration changes use the existing `X-HimRakshak-Admin` boundary and
`expected_revision` returns `409` when stale. Request bodies retain the server's
64 KiB limit and JSON validation. Remote transmissions may use only the token
mapped to their station; read-only diagnostics state that the radio is not
physical and expose no credentials.

The v2 transmission endpoint schedules a packet; virtual time and gateway
consumers determine when it becomes a received delivery. It does not silently
claim backend acceptance.

## Phase 6 boundary

Future Wokwi/ESP32 firmware integration should encode the canonical reading into
a `LoRaPacket` and submit it through this interface. The future integration must
continue to use `StationManager.ingest()` and the existing risk authority.
No firmware, frontend, physical radio, solar, battery, or new risk model is
included in Phase 5.

## Phase 7 validation boundary

Phase 7 validates the merged Phase 6 source contract and the complete
software-only path with deterministic Python tests. Arduino CLI, PlatformIO,
and live Wokwi execution remain separate validation capabilities and must not
be inferred from source-level checks.
