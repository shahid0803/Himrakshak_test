import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "wokwi_esp32_demo" / "sketch.ino"
DIAGRAM = ROOT / "wokwi_esp32_demo" / "diagram.json"
RADIO_CONFIG = ROOT / "wokwi_esp32_demo" / "radio_config.h"
VIRTUAL_LORA = ROOT / "wokwi_esp32_demo" / "virtual_lora.h"
PROFILES = ROOT / "wokwi_esp32_demo" / "sender_profiles"


class FirmwareContractTests(unittest.TestCase):
    def setUp(self):
        self.source = FIRMWARE.read_text(encoding="utf-8")

    def test_firmware_uses_secure_transport_and_v2_envelope(self):
        for marker in (
            "#include <WiFi.h>",
            "#include <WiFiClientSecure.h>",
            "#include <Adafruit_MPU6050.h>",
            "#include <ArduinoJson.h>",
            "setCACert(HIMRAKSHAK_ROOT_CA)",
            "WOKWI_SOFTWARE_SIMULATION",
            "/api/v2/radio/transmissions",
            "MAX_PENDING_PACKETS = 10",
            "RETRY_MAX_MS",
            "battery_pct",
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn("setInsecure", self.source)
        self.assertRegex(self.source, r"TELEMETRY_INTERVAL_MS\s*=\s*10000")
        self.assertIn("X-HimRakshak-Device-Token", self.source)
        self.assertNotIn("X-HimRakshak-Admin", self.source)
        virtual = VIRTUAL_LORA.read_text(encoding="utf-8")
        for marker in ("transmission_id", "idempotency_key", "device_sequence",
                       "attempt_number", "channel_profile"):
            self.assertIn(marker, virtual)

    def test_local_alerts_and_sensor_acquisition_are_independent_of_network(self):
        self.assertLess(self.source.index("Reading reading = readSensors()"),
                        self.source.index("serviceQueue();"))
        for marker in (
            "mpu.begin()",
            "filteredTilt",
            "analogRead(PIN_MOISTURE)",
            "digitalRead(PIN_VIBRATION)",
            "setIndicators(risk)",
            "WiFi.begin",
            "WiFi.setAutoReconnect",
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn("while (WiFi.status()", self.source)

    def test_retries_change_attempt_id_but_preserve_packet_identity(self):
        self.assertIn('makeAttemptId(packet.packetId, packet.attemptNumber)', self.source)
        self.assertIn('makeTransmissionEnvelope(', self.source)
        self.assertIn('packet.attemptNumber++', self.source)
        self.assertIn('packet.packetId', self.source)
        self.assertIn('packet.sequence', self.source)
        self.assertIn("SUBMIT_PERMANENT_FAILURE", self.source)
        for status in ("status == 400", "status == 401", "status == 403",
                       "status == 404", "status == 409"):
            self.assertIn(status, self.source)

    def test_three_sender_profiles_are_independent_and_allow_scenarios(self):
        expected = {
            "hr01.h": ("HR-01", "normal"),
            "hr02.h": ("HR-02", "heavy_rain"),
            "hr03.h": ("HR-03", "slope_shift"),
        }
        for filename, (station, scenario) in expected.items():
            source = (PROFILES / filename).read_text(encoding="utf-8")
            self.assertIn(f'"{station}"', source)
            self.assertIn(f'"{scenario}"', source)

    def test_diagram_is_s3_mpu6050_and_uses_declared_pins(self):
        diagram = json.loads(DIAGRAM.read_text(encoding="utf-8"))
        parts = {part["id"]: part["type"] for part in diagram["parts"]}
        self.assertEqual(parts["esp"], "wokwi-esp32-s3-devkitc-1")
        self.assertEqual(parts["mpu"], "wokwi-mpu6050")
        connections = {tuple(connection[:2]) for connection in diagram["connections"]}
        for connection in (
            ("potMoist:SIG", "esp:4"),
            ("potTilt:SIG", "esp:5"),
            ("potBattery:SIG", "esp:6"),
            ("vibButton:1.l", "esp:7"),
            ("mpu:SDA", "esp:8"),
            ("mpu:SCL", "esp:9"),
            ("esp:15", "rGreen:2"),
            ("esp:16", "rYellow:2"),
            ("esp:17", "rRed:2"),
            ("esp:18", "buzzer:1"),
        ):
            self.assertIn(connection, connections)

    def test_radio_headers_define_software_profile_without_credentials(self):
        radio = RADIO_CONFIG.read_text(encoding="utf-8")
        virtual = VIRTUAL_LORA.read_text(encoding="utf-8")
        for marker in (
            "868.0",
            "125",
            "SPREADING_FACTOR 9",
            '"/api/v2/radio/transmissions"',
            'HIMRAKSHAK_DEVICE_TOKEN ""',
        ):
            self.assertIn(marker, radio)
        self.assertIn("makeAttemptId", virtual)
        self.assertIn("created_at", virtual)
        self.assertIn("channel_profile", virtual)
        self.assertNotIn("X-HimRakshak-Admin", self.source + radio + virtual)


if __name__ == "__main__":
    unittest.main()
