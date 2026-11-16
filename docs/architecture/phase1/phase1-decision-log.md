# Phase 1 Decision Log

## D-001 — Preserve API v1

The current routes, aliases, validation, response shapes, sequence semantics,
and status codes remain the compatibility baseline. New capabilities use
additive `/api/v2` resources.

## D-002 — Backend risk is authoritative

ESP32-local risk is useful for offline alerts but is advisory. Client-supplied
risk fields are never trusted or merged into the backend assessment.

## D-003 — Treat Stitch as a visual reference

The Stitch export is static mockup HTML with no current API integration. It
will guide visual adoption but will not replace the tested dashboard wholesale.

## D-004 — Separate transport facts from sensor facts

Raw telemetry, local risk, channel outcomes, gateway receipt, backend
acceptance, and power state are separate schemas and histories.

## D-005 — Virtual LoRa is not SX1262

The software channel may model deterministic outcomes but cannot claim physical
RF measurements, range, antenna behavior, or hardware status.

## D-006 — Stable identity for retries

Device sequence remains sender-owned. A logical retry reuses
`transmission_id` and `idempotency_key`, increments `attempt`, and reconciles
before queue removal.

## D-007 — Bounded state

All queues, histories, counters, and idempotency records must have explicit
limits and reset/retention semantics. Existing v1 history remains bounded to
100 in-memory events.

## D-008 — Explicit unavailable states

The UI must distinguish configured, simulated, measured, unavailable, stale,
gateway-received, and backend-accepted values. It must never fill unsupported
metrics with invented live-looking numbers.

## D-009 — No Phase 1 implementation

Phase 1 produces specifications only. Existing application source,
configuration, frontend, firmware, and production deployment are unchanged.
