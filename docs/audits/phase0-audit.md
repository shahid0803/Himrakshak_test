# Phase 0 Audit Baseline

> **Historical baseline:** this report records the Phase 0 audit performed
> before the migration into `Himrakshak_test`. It is not a new test run made
> during repository publication.

## Verified baseline

- The previous HimRakshak source archive contained the Python backend,
  vanilla JavaScript frontend, Wokwi project, tests, documentation, Render
  configuration, and GitHub Pages workflow.
- The complete Python test suite passed **118 tests**.
- Python source and tests passed `python -B -m compileall`.
- The inline dashboard JavaScript passed Node syntax validation with
  `node --check`.
- The current API v1 behavior was verified: health, legacy state, station
  roster/detail, telemetry ingestion, simulation, reliability routes,
  validation, sequence conflicts, rate limiting, and remote admin controls.
- The referenced Render deployment returned HTTP 200 for `/api/health` and
  `/api/stations/HR-01`.
- The Wokwi contract checks validated required packet fields, TLS certificate
  markers, sequence reconciliation markers, sender profiles, diagram JSON,
  and the bounded firmware queue.

## Existing architecture

The backend is a Python standard-library HTTP service. `schema.py` validates
canonical readings and legacy aliases; `risk.py` calculates the
authoritative, illustrative rule-based assessment; `stations.py` owns three
isolated in-memory stations; `reliability.py` models bounded software
communication faults; and `server.py` exposes the local/cloud API.

The frontend is a standalone HTML/CSS/vanilla JavaScript dashboard. It can run
as a browser-only simulation or synchronize with the same-origin Python API
in local/cloud mode. It does not silently substitute browser-generated values
for unavailable backend state.

The Wokwi project uses virtual ESP32 firmware, simulated inputs, and
Wi-Fi/HTTPS. It does not implement physical SX1262 LoRa communication or
prove radio propagation.

## Known gaps

1. The Stitch export is a static design reference, not an integrated runtime
   frontend.
2. Stitch mockups contain unsupported RF, gateway, elevation, topology, and
   prediction-style metrics that require explicit simulation contracts or
   unavailable states.
3. Wokwi compilation, Wokwi-GUEST networking, live TLS delivery, three-sender
   operation, and live cloud ingestion require manual verification.
4. Station state and event history are process-memory only and reset on
   restart/cold start.
5. Public reading ingestion is not device-authenticated; allowlisting,
   validation, sequence checks, payload limits, and rate limiting are
   demonstration safeguards, not production device identity.
6. The release report in the historical source archive listed 117 tests,
   while the audited source executed 118; the 118-test result is the baseline
   used for this migration.

## Migration boundary

Phase 0 made no application behavior changes. This repository import preserves
the working frontend, backend, Wokwi project, tests, deployment configuration,
and existing project documentation. Google Stitch files are stored under
`design-reference/stitch/`, and Phase 1 architecture documents are stored
under `docs/architecture/phase1/`; neither replaces the working application.
