import unittest

from himrakshak.risk import assess_risk


class FirmwareRiskParityTests(unittest.TestCase):
    def test_representative_vectors_match_documented_backend_authority(self):
        cases = (
            ({"soil_moisture_pct": 20, "tilt_deg": 1, "vibration_level": 10},
             "NORMAL", 0),
            ({"soil_moisture_pct": 70, "tilt_deg": 2, "vibration_level": 10},
             "WARNING", 16),
            ({"soil_moisture_pct": 80, "tilt_deg": 5, "vibration_level": 20},
             "CRITICAL", 36),
            ({"soil_moisture_pct": 20, "tilt_deg": 9, "vibration_level": 10},
             "CRITICAL", 31),
            ({"soil_moisture_pct": 20, "tilt_deg": 1, "vibration_level": 80},
             "WARNING", 15),
        )
        for reading, level, score in cases:
            reading = {
                "node_id": "HR-01",
                "sequence": 1,
                "timestamp": "SIMULATED",
                "transport": "WOKWI_SOFTWARE_SIMULATION",
                "battery_pct": 80,
                **reading,
            }
            result = assess_risk(reading)
            self.assertEqual(result["risk_level"], level)
            self.assertEqual(result["demo_score"], score)
            self.assertEqual(result["model_id"], "himrakshak-demo-risk-engine-v1")

    def test_firmware_source_contains_backend_thresholds(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] /
                  "wokwi_esp32_demo" / "sketch.ino").read_text(encoding="utf-8")
        for marker in ("45.0f", "55.0f", "60.0f", "75.0f", "8.0f",
                       "65.0f", '\"CRITICAL\"', '\"WARNING\"'):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
