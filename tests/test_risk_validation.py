import unittest
from pathlib import Path

from himrakshak.risk import assess_risk
from himrakshak.schema import SchemaValidationError


ROOT = Path(__file__).resolve().parents[1]


def reading(
    moisture=32.0,
    tilt=1.0,
    vibration=10.0,
    soil_moisture_pct=None,
    tilt_deg=None,
    vibration_level=None,
    battery_pct=82.0,
):
    return {
        "node_id": "HR-01",
        "sequence": 1,
        "timestamp": "2026-11-16T18:30:00Z",
        "soil_moisture_pct": moisture if soil_moisture_pct is None else soil_moisture_pct,
        "tilt_deg": tilt if tilt_deg is None else tilt_deg,
        "vibration_level": vibration if vibration_level is None else vibration_level,
        "battery_pct": battery_pct,
        "transport": "VIRTUAL_LORA_SIMULATION",
    }


class RiskValidationTests(unittest.TestCase):
    def test_shared_risk_vectors_cover_normal_warning_and_critical_boundaries(self):
        vectors = (
            ("normal", reading(), "NORMAL", 0),
            ("moisture threshold", reading(moisture=60), "WARNING", 10),
            ("tilt threshold", reading(tilt=4), "WARNING", 9),
            ("vibration threshold", reading(vibration=65), "WARNING", 11),
            ("score warning threshold", reading(moisture=84), "WARNING", 25),
            ("critical tilt", reading(tilt=8), "CRITICAL", 27),
            ("critical combination", reading(moisture=75, tilt=4), "CRITICAL", 28),
            ("critical score", reading(tilt=14.2), "CRITICAL", 55),
        )
        for name, payload, level, score in vectors:
            with self.subTest(name=name):
                result = assess_risk(payload)
                self.assertEqual(result["risk_level"], level)
                self.assertEqual(result["demo_score"], score)
                self.assertEqual(result["model_id"], "himrakshak-demo-risk-engine-v1")
                self.assertTrue(result["illustrative"])

    def test_backend_risk_is_authoritative_over_client_metadata(self):
        payload = reading(moisture=32, tilt=1, vibration=10)
        payload.update(
            {
                "risk_level": "CRITICAL",
                "demo_score": 100,
                "reasons": ["client supplied"],
                "model_id": "client-model",
                "illustrative": False,
            }
        )
        result = assess_risk(payload)
        self.assertEqual(result["risk_level"], "NORMAL")
        self.assertEqual(result["demo_score"], 0)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["model_id"], "himrakshak-demo-risk-engine-v1")
        self.assertTrue(result["illustrative"])

    def test_invalid_sensor_state_never_becomes_a_safe_assessment(self):
        for field, value in (
            ("soil_moisture_pct", -1),
            ("tilt_deg", 16),
            ("vibration_level", float("nan")),
            ("battery_pct", float("inf")),
        ):
            with self.subTest(field=field):
                with self.assertRaises(SchemaValidationError):
                    assess_risk(reading(**{field: value}))

    def test_firmware_uses_the_same_formula_and_thresholds_at_source_level(self):
        source = (ROOT / "wokwi_esp32_demo" / "sketch.ino").read_text(
            encoding="utf-8"
        )
        for marker in (
            "roundedReading",
            "(reading.moisture - 45.0f) / 55.0f",
            "(reading.tilt - 2.0f) / 10.0f",
            "(reading.vibration - 25.0f) / 75.0f",
            "reading.tilt >= 8.0f",
            "reading.moisture >= 75.0f && reading.tilt >= 4.0f",
            "score >= 55",
            "reading.moisture >= 60.0f",
            "reading.vibration >= 65.0f",
        ):
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
