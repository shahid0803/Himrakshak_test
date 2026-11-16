# ESP32-S3 Wokwi sender

This companion project demonstrates the software path from simulated
ESP32-S3 inputs to the HimRakshak Phase 5 virtual-radio API. It simulates
Wi-Fi, HTTPS, sensors, local alerts, and the software transmission envelope;
it does not simulate physical LoRa, SX1262 hardware, field calibration, or
radio range.

## Open it in Wokwi

1. Create an ESP32 project at https://wokwi.com/esp32.
2. Replace the sketch with `sketch.ino`, the circuit with `diagram.json`, and
   add the libraries listed in `libraries.txt`.
3. Copy one sender profile over `station_config.h`.
4. Start the simulation and open Serial Monitor at 115200 baud.
5. Turn the three potentiometers and press the blue vibration button.

The circuit uses `wokwi-esp32-s3-devkitc-1`, an MPU6050 on I2C (SDA 8, SCL
9), ADC inputs 4/5/6, vibration input 7, indicators 15/16/17, and buzzer 18.
The firmware initializes sensors and local indicators before any network
operation. Local LEDs and the critical buzzer continue to work when Wi-Fi or
the backend is unavailable.

## Independent station profiles

Copy one profile before each independent run:

```powershell
Copy-Item sender_profiles\hr01.h station_config.h
# or sender_profiles\hr02.h / sender_profiles\hr03.h
```

`HR-01`, `HR-02`, and `HR-03` remain independent identities with the existing
normal, heavy-rain, and slope-shift demonstrations. Do not run two senders
with the same station ID.

## Virtual-radio contract

Each queued reading contains canonical telemetry fields and the honest
`WOKWI_SOFTWARE_SIMULATION` transport marker. The sender posts an envelope to
`/api/v2/radio/transmissions` with:

- stable `idempotency_key` and packet identity per device sequence;
- changing `transmission_id`/attempt ID for each retry;
- incrementing `attempt_number`;
- `device_sequence`, `created_at`, `node_id`, `payload`, and
  `channel_profile: "baseline"`.

The bounded queue has ten entries. Network failures, timeouts, 429 responses,
and 5xx responses retry with capped exponential backoff. Permanent 400/401/403/
404/409 responses are removed from the retry queue and reported to Serial.
There is no infinite retry loop. The queue is RAM-only and is lost on reset.

The firmware never embeds an admin key. The current Phase 5 server protects
the v2 transmission endpoint with the existing admin boundary in remote mode,
and it does not yet expose a device-scoped credential. Consequently, a public
Wokwi run can demonstrate the envelope and local behavior but cannot
successfully submit to a protected remote deployment without a future
least-privilege device-authentication design. `secrets.example.h` is a
non-secret placeholder only; never commit `secrets.h`.

TLS uses the checked-in Google Trust Services Root R4 certificate. The
firmware never calls `setInsecure()`. Timestamps remain `SIMULATED` because
the payload uses `WOKWI_SOFTWARE_SIMULATION`; NTP is not required for local
alerts or packet identity.

## Local checks

If Wokwi or Arduino CLI is unavailable, validate the contract locally:

```powershell
python -B -m unittest tests.test_firmware_contract tests.test_firmware_risk_parity -v
python -B -m json.tool wokwi_esp32_demo\diagram.json
```

These checks do not claim a live Wokwi compile, Wi-Fi connection, TLS session,
or cloud delivery.
