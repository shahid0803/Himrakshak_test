# HimRakshak Digital Twin System Architecture

## 1. Purpose and non-goals

HimRakshak is a software-only digital twin for demonstrating landslide
telemetry, explainable risk assessment, virtual communications faults, and
offline recovery. It is not a field warning system, a calibrated geotechnical
model, or a physical LoRa deployment.

The architecture preserves the current Python API v1 and its browser
simulation. New virtual-radio and gateway capabilities are additive and must
not change the meaning of existing sensor packets or backend assessments.

## 2. Logical architecture

```text
Wokwi ESP32-S3 sensor pod
  ├─ MPU6050 virtual tilt sensor
  ├─ virtual soil-moisture input
  ├─ virtual vibration input
  ├─ virtual battery/solar state
  ├─ local validation, risk classification, LED/buzzer alert
  └─ radio packet producer
          │
          ▼
Software-emulated LoRa channel
  ├─ deterministic delay, loss, duplication and reordering
  ├─ configurable virtual radio parameters
  └─ transmission/reception diagnostics
          │
          ▼
Python virtual edge gateway
  ├─ receives channel frames
  ├─ validates packet envelope and node identity
  ├─ performs retry/idempotency handling
  └─ forwards canonical telemetry to the existing API
          │
          ▼
Existing HimRakshak backend
  ├─ schema.validate_reading()
  ├─ StationManager
  ├─ risk.assess_risk()
  ├─ station history and reliability state
  └─ API v1 plus future additive API v2 diagnostics
          │
          ▼
HimRakshak frontend
  ├─ browser-only standalone simulation
  ├─ local backend mode
  ├─ cloud read-only/telemetry mode
  └─ explicit unavailable/offline states
```

## 3. Virtual sensor pod

### 3.1 ESP32-S3

The ESP32-S3 is the virtual edge device and owns local sampling cadence,
packet sequencing, local alert output, bounded buffering, and transport
retries. Wokwi execution is software emulation of firmware and peripherals.
It does not prove electrical behavior, sensor calibration, radio propagation,
or field survivability.

The existing firmware contract remains the compatibility baseline:

- canonical node ID and non-negative device sequence;
- `timestamp` as a timezone-aware ISO value, or `SIMULATED` only with
  `WOKWI_SOFTWARE_SIMULATION`;
- soil moisture, tilt, vibration, and battery percentages;
- no admin secret in firmware;
- bounded RAM queue and structured sequence-conflict reconciliation.

### 3.2 MPU6050 virtual tilt sensing

The MPU6050 represents a virtual inertial measurement source. The pod derives
the demonstration `tilt_deg` value from configured pitch/roll stimulus. The
backend contract currently accepts one bounded `tilt_deg` value from 0 to 15.
Future raw axes may be carried as optional metadata, but they must not alter
the v1 risk engine until a separately versioned model contract exists.

### 3.3 Virtual soil-moisture sensing

The soil-moisture input is a Wokwi analog/control source normalized to
`soil_moisture_pct` in the range 0–100. It is a synthetic control value, not
volumetric water-content instrumentation or a calibrated probe.

### 3.4 Virtual vibration sensing

The vibration input is a synthetic anomaly/control source normalized to
`vibration_level` in the range 0–100. A button or scripted stimulus may create
a burst. It does not represent a calibrated geophone or acceleration spectrum.

### 3.5 Virtual power

The pod may model battery state, solar input, load, and charging transitions.
The existing v1 `battery_pct` remains the only authoritative sensor field for
the current risk engine. Power diagnostics are additive metadata and must not
silently replace `battery_pct`.

## 4. Local ESP32 logic

The pod performs:

1. input normalization and finite/range checks;
2. local demonstration risk classification using the same documented rule
   thresholds where practical;
3. local LED/buzzer indication;
4. packet construction with a device-owned sequence;
5. bounded queueing while the channel is unavailable;
6. retry with backoff and explicit duplicate/stale reconciliation.

Local risk is advisory device state. It is never accepted as authoritative by
the backend. The backend validates the raw telemetry and recalculates risk
with `assess_risk()`.

## 5. Virtual LoRa channel

The channel is a deterministic software transport between a sender and the
gateway. It may model packet delay, drop, duplication, reordering, disconnect,
configuration, and bounded queues. A seeded run must be repeatable.

This channel is **not** an SX1262 driver, a LoRa PHY, a spectrum simulation,
or evidence of radio range. It must not claim real RSSI, SNR, airtime, duty
cycle, propagation loss, antenna behavior, or regulatory compliance unless
those values are explicitly labelled as model outputs.

The channel should expose model diagnostics such as configured loss rate,
scheduled delivery time, queue depth, and simulated outcome. These are
diagnostic facts about the emulator, not measured RF observations.

## 6. Python virtual edge gateway

The gateway is a process boundary between the virtual channel and the
existing backend. It owns:

- channel receive loop;
- packet-envelope validation;
- node allowlisting and gateway identity;
- retry identifiers and idempotency keys;
- forwarding to `/api/stations/{node_id}/readings`;
- handling of HTTP 409, 429, timeout, and unavailable responses;
- gateway health and channel diagnostics.

The gateway does not own the canonical risk decision, station history, or
backend sequence authority. It may cache delivery state, but it must not
rewrite an accepted device sequence or fabricate a successful delivery.

## 7. Existing backend

`StationManager` remains the source of truth for accepted station state,
station-local sequence protection, bounded history, and software reliability
operations. `schema.validate_reading()` remains the canonical input
validator. `risk.assess_risk()` remains authoritative for backend risk.

API v1 continues to support the current legacy routes and aliases. Proposed
radio, gateway, and power endpoints are additive under `/api/v2`.

## 8. Frontend

The frontend is a vanilla HTML/CSS/JavaScript client with three explicit
modes:

- standalone browser simulation with local synthetic state;
- same-origin local backend mode;
- same-origin cloud mode with public ingestion/read-only state and protected
  administrative operations.

The frontend renders backend assessments as authoritative. It may render local
ESP32 status and emulator diagnostics in separate labelled sections. It must
not present browser-generated values as cloud telemetry when the backend is
unavailable.

## 9. Offline operation and recovery

Offline behavior is layered:

1. ESP32 continues local sampling, local alerts, and bounded queueing.
2. The virtual channel may be disconnected or delay delivery.
3. The gateway retries with a stable transmission identity.
4. The backend rejects duplicate or stale device sequences without replacing
   accepted state.
5. The frontend shows unavailable/stale state and does not synthesize cloud
   history.

Recovery is successful only after an accepted backend response or an explicit
idempotent confirmation. Ambiguous failures remain queued and visible.

## 10. Physical hardware boundary

The system currently contains no SX1262 hardware integration, physical LoRa
driver, real RF measurement, or radio-range test. Any future physical
hardware adapter must be a separate transport implementation behind the same
packet contract and must not be inferred from the virtual channel.
