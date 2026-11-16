# Known limitations

- The virtual LoRa channel and gateway are deterministic software simulations;
  they do not prove physical radio range, interference behavior, or hardware
  delivery.
- The station device-token mapping is a deployment secret mechanism, not a
  device provisioning, rotation, revocation, or certificate-management system.
- GitHub Pages cannot perform protected API operations and falls back to local
  browser simulation when the backend is unavailable.
- Render and GitHub Pages status depends on repository/provider configuration;
  source configuration and a successful local test do not prove a live deploy.
- Arduino CLI, PlatformIO, live Wokwi execution, physical ESP32-S3 hardware,
  certificate-chain runtime validation, and production observability were not
  available in this verification environment.
- Backend risk assessment remains authoritative. Firmware-local indicators and
  browser simulations are illustrative and must not be used as safety
  decisions.
- API v1 is preserved. Proposed v2 radio, gateway, power, solar, and firmware
  upgrade endpoints are intentionally outside this phase.
