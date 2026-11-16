# Phase 9 final validation report

## Scope

This release hardens remote telemetry authentication, reconciles the frontend,
backend, virtual gateway, firmware contract, and deployment documentation, and
adds acceptance and release-contract coverage. It does not add physical radio,
gateway, power, solar, or firmware-upgrade features.

## Required checks

The final handoff records the exact command output for:

```powershell
python -m unittest discover -s tests -v
python -m py_compile himrakshak\*.py tests\*.py
git diff --check
```

Every frontend JavaScript file is checked with Node's syntax checker. The Wokwi
diagram is parsed as JSON, the Pages workflow is checked for complete asset
packaging, and static assets are scanned for credentials or invented network
telemetry.

## Security result

Remote v1 reading ingestion and station-scoped v2 transmission submission
require `X-HimRakshak-Device-Token` mapped to the station. Admin authorization
remains separate for simulator and configuration mutation. No credentials are
committed or embedded in browser assets.

## Deployment result

Render health and GitHub Pages availability must be reported from live checks,
not inferred from repository files. A provider configuration failure is a
deployment blocker and is recorded as such rather than hidden by a local pass.
