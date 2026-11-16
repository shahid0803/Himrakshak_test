# HimRakshak final system architecture

## Trust boundaries

The browser dashboard is a presentation and local-simulation client. It may
read v1 state and diagnostics, but it never contains the admin key or a device
token and never becomes the source of risk truth. The Python server validates
incoming readings, owns station state and sequence reconciliation, and
recalculates every risk assessment with the backend risk engine.

Remote telemetry is station-scoped. A device sends
`X-HimRakshak-Device-Token`; the server compares it with the configured
`HIMRAKSHAK_DEVICE_TOKENS` mapping for the URL/body station. Administrative
simulation and radio configuration remain protected by
`X-HimRakshak-Admin`. Local loopback mode keeps the existing development
behavior.

## Runtime paths

1. A sensor or Wokwi firmware instance creates a validated reading and a
   device-owned sequence.
2. The virtual LoRa channel applies configured loss and delay behavior.
3. The gateway bounds its queue, deduplicates attempts, and delivers packets
   when available.
4. `StationManager` validates identity, rejects duplicate/stale sequences, and
   stores bounded event history.
5. The frontend polls v1 state and v2 diagnostics, maps timestamps and
   freshness states, and renders loading, unavailable, stale, and recovery
   states without inventing telemetry.

## Deployment modes

| Mode | Backend | Mutations | Telemetry |
|---|---|---|---|
| Standalone `file://` | none | browser simulation only | local synthetic simulation |
| Local | loopback Python server | open development routes | local API and simulation |
| Cloud/Render | `--allow-remote` Python server | admin-authenticated | station-token authenticated |
| GitHub Pages | static artifact | browser simulation only | API unavailable/read-only |

The GitHub Pages workflow is authoritative for publication: it copies only
`index.html` and `frontend/` into `site/`. No physical LoRa, gateway, solar,
or safety-certified telemetry is represented by this software-only system.
