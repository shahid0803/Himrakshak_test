# Google Stitch Component-to-Data Mapping

## Classification

- **Existing API field:** directly available from current v1.
- **Backend-derived:** computed from current API data without claiming a new
  measurement.
- **New simulated field:** requires the proposed channel/gateway/power model.
- **Unavailable/unsupported:** must not be presented as live or measured.

## Cross-screen mapping

| Stitch component/data | Screens | Classification | Contract/source | Required treatment |
|---|---|---|---|---|
| HimRakshak title, simulation disclosure | all | Existing/documented | frontend copy and project boundary | Keep; make disclosure prominent |
| Station roster and node IDs | overview, sensor stations, live monitoring | Existing API field | `GET /api/stations` | Replace mock labels with `HR-01`–`HR-03` unless location labels become explicit metadata |
| Risk level | overview, live monitoring, sensor stations | Existing API field | `station.latest.assessment.risk_level` | Backend assessment is authoritative |
| Demonstration score | overview, live monitoring | Existing API field | `demo_score` | Label as illustrative/demo score |
| Risk reasons | overview, live monitoring | Existing API field | `reasons[]` | Render exact backend reasons |
| Soil moisture | overview, sensor stations, simulation lab | Existing API field | `reading.soil_moisture_pct` | Use percentage semantics; do not call it calibrated VWC |
| Tilt | overview, sensor stations, live monitoring, simulation lab | Existing API field | `reading.tilt_deg` | Label as simulated tilt |
| Vibration | sensor stations, live monitoring, simulation lab | Existing API field | `reading.vibration_level` | Label as normalized demo vibration |
| Battery percentage | sensor stations, simulation lab | Existing API field | `reading.battery_pct` | Existing field; voltage requires v2 power model |
| Sequence number | overview, live monitoring, diagnostics | Existing API field | `reading.sequence`, `next_sequence` | Distinguish device sequence from event order |
| Accepted event history | overview, live monitoring | Existing API field | station `events[]`, global `events[]` | Show bounded in-memory history |
| Scenario controls | overview, simulation lab | Existing API route | local `POST .../simulate` | Protected/disabled in remote mode |
| Drop/delay/release/duplicate/stale controls | diagnostics, simulation lab | Existing API route | local `/faults/*` | Label software reliability simulation |
| Receiver connected/disconnected | overview, live monitoring | Existing API field | `receiver_connected`, communication state | Distinguish backend receiver state from radio hardware |
| Packet pending/dropped/delivered counters | overview, diagnostics | Existing API field | `communication` object | Counters are software model outcomes |
| Frontend local clock | all | Backend-derived/UI-only | browser clock | Never use as sensor timestamp |
| Static screenshots and decorative terrain | all | UI-only | Stitch assets | No telemetry meaning |

## RF and gateway fields

| Stitch component/data | Classification | Reason |
|---|---|---|
| RSSI in dBm | Unavailable/unsupported | No physical receiver or calibrated RF model exists |
| SNR in dB | Unavailable/unsupported | No demodulator/PHY measurement exists |
| Packet delivery percentage | New simulated field | Can be derived from virtual channel counters only; must be labelled emulator PDR |
| Packet drop percentage | New simulated field | Can be derived from configured/outcome counters; not field radio loss |
| Airtime and duty cycle | New simulated field | Requires an explicit model using configured profile; not a measured regulatory result |
| Frequency/bandwidth/spreading factor | New simulated field | Configuration labels only; not proof of actual RF transmission |
| Gateway latency/RTT | New simulated field | Can be measured between software components; must identify the measured path |
| Gateway health | New simulated field | Proposed `/api/v2/gateway/health` |
| Per-node radio diagnostics | New simulated field | Proposed `/api/v2/stations/{id}/radio-diagnostics` |
| LoRa mesh topology / relay hops | New simulated field | Requires an explicit graph model; current backend has no mesh |
| PHY frame/PCAP stream | Unavailable/unsupported | No real PHY frames are produced |
| SX1262 lock/antenna/radio hardware status | Unavailable/unsupported | No SX1262 or physical hardware integration |

## Geospatial and prediction claims

| Stitch component/data | Classification | Required treatment |
|---|---|---|
| NH-109/Rudraprayag/Kedar Valley labels | Unavailable/unsupported as live location | Keep only as fictional/demo context or add explicit static metadata |
| Elevation/ASL | Unavailable/unsupported | Do not imply GPS/DEM data |
| Slope cross-section/stratigraphy/phreatic table | UI-only or unsupported | Use illustrative schematic labels, not measured geology |
| “Prediction”, “early warning”, “hazard index” | Unavailable/unsupported as scientific claim | Use “demonstration risk assessment” and “synthetic scenario” |
| Road closure/evacuation/public warning actions | Unavailable/unsupported | Never expose as operational authority |

## Screen-specific notes

### Overview dashboard

The visual KPI layout can be retained. Active nodes, risk counts, sensor
values, accepted packets, and bounded history map to v1. Gateway, RF, terrain,
and hazard-index KPIs require v2 models or must be replaced with clearly
labelled “not available”/“simulation configuration” values.

### Sensor stations telemetry

Gauge components map well to v1 raw readings and backend assessment. Raw frame
buffers, firmware versions, sensor self-test claims, and hardware health are
not current API data.

### Live monitoring

The live timeline can use accepted station events. Schematic terrain,
coordinates, elevation, moisture-at-elevation, and physical alert claims are
not current measurements.

### Simulation lab stress controls

The control concept is compatible with v1 scenarios and local reliability
operations. Additional solar, battery voltage, load, and channel controls
belong to v2 simulation endpoints.

### LoRa network diagnostics and virtual LoRa laboratory

These screens require the proposed channel and gateway models. Until those
models exist, they must display configuration and emulator outcomes only,
never fabricated RSSI/SNR/PHY observations.

## Stitch implementation rule

Stitch HTML is a design reference, not a drop-in runtime. The existing
contract-tested dashboard remains the behavioral baseline. Visual adoption
must proceed component-by-component with a data owner and an explicit
unsupported-state treatment for every metric.
