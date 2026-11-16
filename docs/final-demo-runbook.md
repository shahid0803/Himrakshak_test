# Final demo runbook

## 1. Static browser demo

Open `index.html` directly or open the GitHub Pages URL after the Pages
workflow succeeds. Confirm the banner identifies standalone/static mode, select
HR-01 through HR-03, run each local scenario, inspect the local event history,
and export CSV. Do not describe the browser simulation as live telemetry.

## 2. Local backend demo

Start:

```powershell
python -m himrakshak.server
```

Open `http://127.0.0.1:8765/`. Verify health, station switching, normal and
high-risk simulations, duplicate/stale responses, recovery diagnostics, and
CSV export. Local mode is for development and does not require device tokens.

## 3. Cloud telemetry demo

Configure Render with a secret JSON mapping such as
`{"HR-01":"<secret>","HR-02":"<secret>","HR-03":"<secret>"}` under
`HIMRAKSHAK_DEVICE_TOKENS`. Supply the matching token only through firmware or
an operator-controlled test client. Verify `/api/health`, read-only station
endpoints, authenticated telemetry, and rejection of missing or mismatched
tokens. Keep `HIMRAKSHAK_ADMIN_KEY` and device tokens out of browser code,
Wokwi diagrams, logs, screenshots, and commits.

## 4. Failure demonstration

Use the virtual channel to demonstrate packet loss, gateway unavailability,
bounded queueing, duplicate retry, stale sequence rejection, and recovery.
State clearly that these are deterministic software simulations and that
Arduino CLI, live Wokwi execution, physical radio, and production monitoring
are outside this release.
