from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FirmwareReliabilityContractTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "wokwi_esp32_demo" / "sketch.ino").read_text(
            encoding="utf-8"
        )
        self.radio = (ROOT / "wokwi_esp32_demo" / "virtual_lora.h").read_text(
            encoding="utf-8"
        )

    def test_local_monitoring_and_alerts_are_not_network_gated(self):
        for marker in (
            "DEVICE_OFFLINE_QUEUEING",
            "DEVICE_RETRYING",
            "DEVICE_QUEUE_FULL",
            "DEVICE_SENSOR_FAULT",
            "DEVICE_LOCAL_ONLY",
            "setIndicators(risk)",
            "roundedReading(readSensors())",
            "MAX_PENDING_PACKETS = 10",
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn("while (WiFi.status()", self.source)
        self.assertNotIn("setInsecure", self.source)

    def test_retry_policy_has_bounded_backoff_and_retry_after(self):
        for marker in (
            "RETRY_MAX_MS",
            "retryDelayMs * 2",
            "status == 429",
            'http.header("Retry-After")',
            "http.setTimeout(1500)",
            "SUBMIT_PERMANENT_FAILURE",
            "status == 400",
            "status == 401",
            "status == 403",
            "status == 404",
        ):
            self.assertIn(marker, self.source)

    def test_logical_identity_is_stable_and_attempt_identity_changes(self):
        self.assertIn("packet.packetId", self.source)
        self.assertIn("packet.sequence", self.source)
        self.assertIn("packet.attemptNumber++", self.source)
        self.assertIn("makeAttemptId(packet.packetId, packet.attemptNumber)", self.source)
        self.assertIn("idempotency_key", self.radio)
        self.assertIn("transmission_id", self.radio)

    def test_overflow_is_explicitly_observable(self):
        self.assertIn("Queue full; local alert preserved and packet dropped", self.source)
        self.assertIn("queue_capacity=%u", self.source)


if __name__ == "__main__":
    unittest.main()
