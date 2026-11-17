# HimRakshak

**An offline-first, software-only landslide-monitoring and early-warning prototype for mountainous regions.**

HimRakshak demonstrates a virtual sensor-to-dashboard workflow for three stations (`HR-01`, `HR-02`, and `HR-03`). The project combines a Python backend, an explainable demonstration risk model, a software-emulated LoRa channel, a virtual edge-gateway component, a browser dashboard, and an ESP32-S3/Wokwi firmware prototype.

> **Important:** HimRakshak is an academic and hackathon software prototype. Sensor values, radio behaviour, and hardware interactions are simulated. The project is not a certified landslide-warning system and must not be used for real-world evacuation, road-closure, or public-safety decisions.

---

## Start the website locally

The simplest way to run the complete local website and Python API is to start the backend from the repository root. The backend serves the dashboard and API from the same local address.

### 1. Prerequisites

- Python **3.10 or newer**.
- A modern browser such as Chrome, Edge, or Firefox.
- Git, if you are cloning the repository.

The Python application uses the standard library. **No `pip install` step is required** for the current backend.

Check your Python version:

```bash
python --version
```

On Windows, you can also use:

```powershell
py -3 --version
```

### 2. Download the repository

```bash
git clone https://github.com/shahid0803/Himrakshak_test.git
cd Himrakshak_test
```

If you already downloaded the ZIP, extract it and open a terminal in the extracted `Himrakshak_test-main` project folder. The folder you run the command from must contain `himrakshak/`, `frontend/`, and `index.html`.

### 3. Start the backend and website

Run this command from the project root:

```bash
python -m himrakshak.server
```

On Windows, this alternative may be used if `python` is not on your PATH:

```powershell
py -3 -m himrakshak.server
```

You should see a message similar to:

```text
HimRakshak server running on http://127.0.0.1:8765/
```

### 4. Open HimRakshak in your browser

Visit:

**http://127.0.0.1:8765/**

The local server provides both the frontend and its API. In this mode, the dashboard can read backend station state and assessments, and local development simulation endpoints are available.

To stop the server, return to the terminal and press **Ctrl+C**.

### 5. Use a different port (optional)

If port `8765` is already in use, choose another local port:

```bash
python -m himrakshak.server --port 9000
```

Then open:

```text
http://127.0.0.1:9000/
```

The local server binds to `127.0.0.1` by default. It is intended for local development and should not be exposed directly to the public internet.

---

## Run the browser-only demonstration

You can open the root `index.html` file directly in a browser by double-clicking it or using **Open with browser**.

This uses `file://` standalone mode:

- It does not start the Python backend.
- It does not send API requests.
- Scenario results and event history are browser-local demonstration data.
- Backend-only diagnostics and reliability operations are unavailable.

For the complete local website/API experience, use the Python startup instructions above instead.

**GitHub Pages is a static host and does not run the Python backend.** A Pages workflow can publish the HTML/CSS/JavaScript assets, but that alone does not provide the API. With the current frontend origin detection, a Pages site without a same-origin API can show a cloud-backend-unavailable state; do not assume that the hosted page provides the same interactive standalone mode as opening `index.html` through `file://`. Check the repository's **Actions** tab and **Settings → Pages** before sharing a public URL.

---

## What is included

### Browser dashboard

The frontend is built with HTML, CSS, and classic JavaScript scripts. It contains these screens:

1. Overview
2. Sensor stations
3. Live monitoring
4. Virtual LoRa laboratory
5. Simulation lab
6. Alerts and events
7. Diagnostics

The dashboard reads backend state when connected and distinguishes backend data from unavailable or simulated states. The website is a monitoring interface for the prototype; it is not a certified operational command system.

### Python backend

The `himrakshak/` package includes:

- `server.py` — standard-library HTTP server, API routing, local/remote configuration, and static frontend asset serving.
- `schema.py` — canonical sensor-reading validation and normalization.
- `risk.py` — backend-authoritative, explainable demonstration risk assessment.
- `stations.py` — independent in-memory station state, sequence handling, and event history.
- `simulator.py` — reproducible synthetic sensor scenarios.
- `reliability.py` — software-level communication fault simulation.
- `lora_simulator.py` — software-emulated LoRa airtime, propagation/link metrics, packet scheduling, and channel fault simulation.
- `gateway.py` — virtual gateway adapter that validates received packets and forwards readings to the existing station manager.

Station state and event history are held in process memory. There is no database or durable storage in this version; state can be lost when the server restarts or the hosting process is recycled.

### Virtual stations and scenarios

The three configured virtual station identifiers are:

- `HR-01`
- `HR-02`
- `HR-03`

The Python simulator supports these scenarios:

- `normal`
- `heavy_rain`
- `slope_shift`
- `vibration_burst`

Generated readings are synthetic. The backend validates submitted readings and calculates its own assessment; client-supplied risk fields are not authoritative.

### Virtual LoRa channel and gateway

The Python LoRa module models a configurable radio profile and software outcomes such as airtime, path loss, RSSI, SNR, packet loss, delay, jitter, duplication, reordering, and gateway availability.

These values are **calculated or simulated**. The project does not transmit actual LoRa RF signals, use a physical SX1262 module, implement a physical gateway, or establish field range or regulatory compliance.

### ESP32-S3 / Wokwi prototype

The `wokwi_esp32_demo/` folder contains an ESP32-S3 Wokwi circuit and firmware source with:

- MPU6050 acquisition over I²C.
- Potentiometer-based simulated moisture, tilt-assist, and battery inputs.
- A button-based vibration input.
- Local risk indication using green/yellow/red LEDs and a buzzer.
- Wi-Fi/HTTPS transmission-envelope code and a bounded RAM retry queue.

Wokwi simulates the board and inputs. It is not physical sensor or LoRa hardware. See [`wokwi_esp32_demo/README.md`](wokwi_esp32_demo/README.md) for the circuit setup and current limitations.

---

## Run a sensor scenario from the command line

Generate one normal synthetic reading:

```bash
python -m himrakshak.simulator --scenario normal
```

Generate three reproducible heavy-rain readings:

```bash
python -m himrakshak.simulator --scenario heavy_rain --count 3 --seed 42
```

The simulator prints JSON Lines. Its generated values and risk assessments are for demonstration and testing only.

---

## Run the test suite

Run all project tests from the repository root:

```bash
python -B -m unittest discover -s tests -v
```

Run selected test groups if you are working on a specific component:

```bash
python -B -m unittest tests.test_risk tests.test_schema tests.test_stations -v
python -B -m unittest tests.test_lora_simulator tests.test_gateway -v
python -B -m unittest tests.test_end_to_end_telemetry tests.test_recovery_integration -v
```

Useful static checks:

```bash
python -m compileall -q himrakshak tests
python -m json.tool wokwi_esp32_demo/diagram.json
```

If Node.js is installed, check the frontend scripts:

```bash
node --check frontend/js/api-client.js
node --check frontend/js/app.js
node --check frontend/js/controls.js
node --check frontend/js/data-mappers.js
node --check frontend/js/router.js
node --check frontend/js/shell.js
node --check frontend/js/state-store.js
```

The uploaded archive's test suite passed **193 tests** during this review. Re-run the commands above on the current checkout; test totals can change as the repository evolves.

---

## Local API quick reference

Start the local server first:

```bash
python -m himrakshak.server
```

The main read-only endpoints are:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Service health and model metadata |
| `GET` | `/api/state` | Latest accepted result and bounded event history |
| `GET` | `/api/stations` | Roster and summaries for the three stations |
| `GET` | `/api/stations/HR-01` | Details and history for one station |
| `GET` | `/api/v2/radio/config` | Virtual radio configuration |
| `GET` | `/api/v2/radio/status` | Virtual channel/gateway status |
| `GET` | `/api/v2/gateway/health` | Virtual gateway health information |
| `GET` | `/api/v2/stations/HR-01/radio-diagnostics` | Per-station radio diagnostics |

The API also includes reading submission, station scenario simulation, station-specific reliability operations, radio transmission scheduling, and protected radio configuration updates. See [`docs/api-contract.md`](docs/api-contract.md) for request formats, response structures, authentication requirements, and error codes.

### Important: a scheduled radio transmission is not an accepted station reading

`POST /api/v2/radio/transmissions` currently returns a scheduling result such as `scheduled`. That response means the packet was placed into the virtual channel; it does **not** prove that the gateway processed it or that `StationManager` accepted the reading. In the uploaded server implementation, scheduled deliveries are advanced through the gateway's simulation methods, but there is no automatic HTTP-server background consumer invoking those methods. Do not interpret HTTP 200 or `scheduled` as end-to-end telemetry acceptance.

---

## Configure remote deployment (Render)

The repository includes a Render Blueprint in [`render.yaml`](render.yaml). It specifies a Python web service with the start command:

```bash
python -m himrakshak.server --allow-remote
```

In remote mode, the server binds to `0.0.0.0` and uses the hosting platform's `PORT` environment variable. The included Blueprint configures `/api/health` as the health-check path.

Configure secrets in the Render service's **Environment** settings, not in the repository:

| Environment variable | Purpose |
|---|---|
| `HIMRAKSHAK_ADMIN_KEY` | Protects administrative simulation, fault-injection, and radio-configuration mutation operations. |
| `HIMRAKSHAK_DEVICE_TOKENS` | JSON object mapping each enabled station ID to its own device token. Required for remote station telemetry. |
| `HIMRAKSHAK_INGEST_MIN_INTERVAL_SECONDS` | Minimum interval between accepted readings per station; the Blueprint sets it to `3`. |
| `PORT` | Assigned by the hosting platform. |
| `PYTHONUNBUFFERED` | The Blueprint sets this to `1` for immediate logs. |

The device-token value is a JSON mapping, for example:

```json
{"HR-01":"<secret-for-HR-01>","HR-02":"<secret-for-HR-02>","HR-03":"<secret-for-HR-03>"}
```

Use real secrets only in the hosting provider's secret/environment manager. Do not paste them into this README, source files, Wokwi diagrams, browser JavaScript, screenshots, or Git commits. Do not reuse an admin key as a device token.

Remote station reading and radio transmission requests require the matching `X-HimRakshak-Device-Token`. Administrative operations use the separate `X-HimRakshak-Admin` header. Local mode does not require these remote credentials.

After deployment, check the actual service URL and deployment status in the Render dashboard. A valid `render.yaml` or a passing local test does not prove that a particular commit has been deployed.

---

## Open the ESP32-S3 project in Wokwi

The Wokwi project files are in [`wokwi_esp32_demo/`](wokwi_esp32_demo/).

1. Open [Wokwi ESP32](https://wokwi.com/esp32).
2. Create an ESP32-S3 project compatible with the `wokwi-esp32-s3-devkitc-1` board.
3. Copy `wokwi_esp32_demo/sketch.ino` into the sketch editor.
4. Recreate/import the circuit using `wokwi_esp32_demo/diagram.json`.
5. Add the libraries listed in `wokwi_esp32_demo/libraries.txt`.
6. Select a station profile before running the simulation. For example, copy `sender_profiles/hr01.h` over `station_config.h` to use `HR-01`; use `hr02.h` or `hr03.h` for the other station profiles.
7. Start the simulation and open the Serial Monitor at **115200 baud**.
8. Adjust the moisture, tilt-assist, and battery potentiometers. Press the vibration button to trigger a vibration event.
9. Observe the local LEDs, buzzer, sensor readings, connection attempts, and queue messages.

The documented pin assignment is: MPU6050 I²C SDA/SCL on GPIO 8/9; simulated ADC inputs on GPIO 4/5/6; vibration input on GPIO 7; green/yellow/red LEDs on GPIO 15/16/17; and buzzer on GPIO 18.

### Wokwi cloud-telemetry limitation in this archive

The firmware posts to the configured Render `/api/v2/radio/transmissions` URL. Remote submission requires a station-scoped device token. The current `radio_config.h` defines `HIMRAKSHAK_DEVICE_TOKEN` as an empty string by default, and the current sketch does not include a private `secrets.h` file or a complete secure Wokwi secret-injection mechanism. Therefore, do not expect remote Wokwi telemetry to authenticate until a safe token-provisioning method is implemented and the matching station token is configured in Render.

There is also an integration gap after submission: the API response `scheduled` is currently treated by the firmware as delivered, while the server has no automatic scheduled-delivery consumer. Consequently, a successful HTTP response does not prove that the gateway ingested the reading. The local sensor and alert demonstration can still be explored, but do not present cloud end-to-end delivery as verified from this archive.

Never put `HIMRAKSHAK_ADMIN_KEY` or a real device token into a tracked firmware file. The checked-in `secrets.example.h` is only an empty placeholder; it is not automatically included by the current sketch.

---

## Deployment options

### Render

- Blueprint configuration: [`render.yaml`](render.yaml)
- Start command: `python -m himrakshak.server --allow-remote`
- Health check: `/api/health`
- The Python API and dashboard are intended to be served from the same origin.

### GitHub Pages

The workflow at [`.github/workflows/pages.yml`](.github/workflows/pages.yml) creates a static artifact containing `index.html` and `frontend/`. It does not run the Python application or create an API service. Enable GitHub Pages with **Settings → Pages → Build and deployment → GitHub Actions**, then verify that the workflow succeeds and use the published URL shown by GitHub. The static Pages host should not be represented as the complete Python-backed application.

---

## Known limitations

1. This is a software-only prototype; there are no physical slope sensors, ESP32-S3 board, SX1262 module, physical LoRa signals, or field gateway.
2. The risk engine is a rule-based illustrative model. It is not an ML model, calibrated geotechnical model, or scientifically validated landslide predictor.
3. RSSI, SNR, path loss, airtime, packet delivery, terrain attenuation, and radio range-related outputs are software calculations/simulations, not measurements from a physical radio link.
4. Station state, gateway state, idempotency entries, queues, and histories are in memory and can be lost when the process restarts.
5. The v2 transmission API currently schedules virtual packets but the uploaded HTTP server does not run an automatic delivery consumer. A `scheduled` response is not backend ingestion acceptance.
6. Gateway idempotency currently caches transmission results by idempotency key. Since firmware retries preserve the logical packet key while changing the attempt ID, the retry/idempotency boundary needs further correction before loss-and-retry delivery can be relied upon end to end.
7. Wokwi's device-token macro is empty by default and the current firmware does not provide a complete secure secret-injection path. Remote Wokwi telemetry therefore requires additional secure configuration before it can authenticate.
8. Firmware contains synchronous HTTP calls with a timeout; this is not proof of fully non-blocking communication during every outage condition.
9. Arduino CLI, PlatformIO compilation, and live Wokwi execution must be verified separately. A valid JSON diagram or passing Python contract tests do not prove a successful firmware compile or live simulation.
10. GitHub Pages is static-only and does not host the Python backend. A published HTML artifact does not prove API functionality.
11. No database, durable offline queue, field calibration, formal safety certification, production observability, or regulatory validation is included.

See [`docs/known-limitations.md`](docs/known-limitations.md), [`docs/final-validation-report.md`](docs/final-validation-report.md), and [`docs/final-demo-runbook.md`](docs/final-demo-runbook.md) for additional validation boundaries and demonstration guidance.

---

## Project documentation

- [`docs/final-system-architecture.md`](docs/final-system-architecture.md) — system architecture and trust boundaries.
- [`docs/api-contract.md`](docs/api-contract.md) — API routes, request/response formats, and authentication.
- [`docs/data-contract.md`](docs/data-contract.md) — canonical telemetry schema.
- [`docs/risk-model.md`](docs/risk-model.md) — demonstration scoring formula and thresholds.
- [`docs/virtual-lora-simulator.md`](docs/virtual-lora-simulator.md) — software LoRa model and assumptions.
- [`docs/virtual-gateway.md`](docs/virtual-gateway.md) — gateway lifecycle, packet identity, and ingestion.
- [`docs/esp32-wokwi-integration.md`](docs/esp32-wokwi-integration.md) — ESP32-S3/Wokwi firmware integration.
- [`docs/telemetry-validation.md`](docs/telemetry-validation.md) — telemetry and risk validation.
- [`docs/offline-reliability.md`](docs/offline-reliability.md) — offline states, retry policy, and recovery.
- [`docs/final-demo-runbook.md`](docs/final-demo-runbook.md) — final demonstration steps.
- [`docs/release-checklist.md`](docs/release-checklist.md) — release validation checklist.
- [`docs/known-limitations.md`](docs/known-limitations.md) — known technical and deployment limitations.

---

## Safety statement

HimRakshak is an experimental academic and hackathon prototype. It is not certified, geotechnically validated, or suitable for real-world hazard decisions. Always rely on qualified geotechnical professionals and official emergency-warning authorities for real slope-risk assessment and public-safety decisions.
