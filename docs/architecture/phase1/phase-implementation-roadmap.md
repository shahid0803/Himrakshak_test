# HimRakshak Phase Implementation Roadmap

## Phase 0 — Audit and baseline

Completed. The current archive was inspected, the Stitch export was compared,
the live Render read-only endpoints were checked, and the current suite passed
118 tests. No application source was changed.

## Phase 1 — Architecture and contract lock

This document set defines the architecture, v1 compatibility contract, v2
proposal, data ownership, Stitch traceability, boundaries, and decisions.

**Exit criteria**

- v1 routes and validation are documented without semantic changes;
- every proposed v2 field has an owner and simulation label;
- every Stitch component has a supported, derived, simulated, or unavailable
  classification;
- no physical LoRa or prediction claim is implied.

## Phase 2 — Frontend foundation and Stitch adoption

Use the existing dashboard as the behavioral baseline and adopt Stitch visuals
incrementally. Introduce a data-source badge, component-level unavailable
states, and a shared mapping layer. Do not copy unsupported KPI values.

**Acceptance criteria**

- all 118 existing tests still pass;
- standalone/local/cloud mode behavior remains unchanged;
- backend risk and reasons match API responses exactly;
- station switching and history remain correct;
- unsupported RF/geospatial values are labelled or removed;
- desktop, tablet, and mobile visual checks pass.

## Phase 3 — API client and integration hardening

Centralize browser requests and error mapping. Add focused tests for 400, 401,
403, 404, 409, 413, 429, unavailable backend, and stale state.

**Dependency:** Phase 2 UI data ownership.

## Phase 4 — Virtual LoRa channel

Implement a seeded software channel with bounded queues, configurable
latency/loss/duplication/reordering, stable transmission IDs, and explicit
outcome counters.

**Dependency:** v2 transmission and diagnostics schemas.

## Phase 5 — Python virtual edge gateway

Implement receive, validation, retry, idempotency, backend forwarding, and
reconciliation. Preserve device sequence ownership and backend authority.

**Dependency:** Phase 4 channel and Phase 3 API client/contracts.

## Phase 6 — ESP32-S3/Wokwi integration

Adapt the current Wokwi pod to the requested ESP32-S3 and virtual sensor
model. Preserve secure transport, bounded queue, startup reconciliation, and
the v1 packet contract. Verify compile and manual execution.

**Dependency:** Phase 5 gateway endpoint and confirmed Wokwi pin/support
constraints.

## Phase 7 — Virtual power and diagnostics

Add solar/battery simulation, gateway health, radio configuration/status, and
per-node diagnostics. Keep these separate from raw telemetry and risk.

**Dependency:** Phase 4 and Phase 5 runtime state model.

## Phase 8 — Reliability and offline recovery

Run end-to-end outage, queue, retry, duplicate, stale, restart, and recovery
scenarios across ESP32, channel, gateway, backend, and browser.

**Dependency:** Phases 5–7.

## Phase 9 — Release verification

Run unit/integration/static checks, Wokwi manual checks, Render endpoint
checks, visual regression, documentation consistency, and disclosure review.
Record automated and manual evidence separately.

**Final release gate:** v1 compatibility, bounded state, no unsupported live
claims, and repeatable recovery demonstration.

## Change-control rule

Each phase is implemented and reviewed independently. No phase may alter an
existing v1 route or response shape without an explicit compatibility decision,
migration test, and review approval.
