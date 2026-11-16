import math
import unittest
from datetime import datetime, timezone

from himrakshak.lora_simulator import LoRaPacket
from himrakshak.schema import SchemaValidationError, validate_reading


def valid_reading(**overrides):
    payload = {
        "node_id": "HR-01",
        "sequence": 7,
        "timestamp": "2026-11-16T18:30:00Z",
        "soil_moisture_pct": 40.0,
        "tilt_deg": 1.5,
        "vibration_level": 12.0,
        "battery_pct": 82.0,
        "transport": "WOKWI_SOFTWARE_SIMULATION",
        "scenario": "normal",
    }
    payload.update(overrides)
    return payload


class TelemetryContractTests(unittest.TestCase):
    def test_numeric_boundaries_are_inclusive(self):
        normalized = validate_reading(
            valid_reading(
                soil_moisture_pct=0,
                tilt_deg=0,
                vibration_level=0,
                battery_pct=100,
            )
        )
        self.assertEqual(normalized["soil_moisture_pct"], 0)
        self.assertEqual(normalized["battery_pct"], 100)

    def test_negative_and_over_range_measurements_are_rejected(self):
        for field, value in (
            ("soil_moisture_pct", -0.01),
            ("soil_moisture_pct", 100.01),
            ("tilt_deg", -0.01),
            ("tilt_deg", 15.01),
            ("vibration_level", -0.01),
            ("vibration_level", 100.01),
            ("battery_pct", -0.01),
            ("battery_pct", 100.01),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(SchemaValidationError):
                    validate_reading(valid_reading(**{field: value}))

    def test_nan_infinity_booleans_and_wrong_types_are_rejected(self):
        for value in (math.nan, math.inf, -math.inf, True, "42"):
            with self.subTest(value=value):
                with self.assertRaises(SchemaValidationError):
                    validate_reading(valid_reading(tilt_deg=value))
        with self.assertRaises(SchemaValidationError):
            validate_reading(valid_reading(sequence=True))
        with self.assertRaises(SchemaValidationError):
            validate_reading(valid_reading(node_id=7))

    def test_required_fields_and_timestamp_rules_are_explicit(self):
        for field in (
            "node_id",
            "sequence",
            "timestamp",
            "soil_moisture_pct",
            "tilt_deg",
            "vibration_level",
            "battery_pct",
        ):
            payload = valid_reading()
            del payload[field]
            with self.subTest(field=field):
                with self.assertRaises(SchemaValidationError):
                    validate_reading(payload)

        for timestamp in ("", "not-a-date", "2026-11-16T18:30:00"):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(SchemaValidationError):
                    validate_reading(valid_reading(timestamp=timestamp))

        normalized = validate_reading(
            valid_reading(timestamp="2026-11-16T19:30:00+01:00")
        )
        self.assertEqual(normalized["timestamp"], "2026-11-16T18:30:00Z")

    def test_simulation_timestamp_requires_matching_marker(self):
        with self.assertRaises(SchemaValidationError):
            validate_reading(
                valid_reading(
                    timestamp="SIMULATED",
                    transport="VIRTUAL_LORA_SIMULATION",
                )
            )
        normalized = validate_reading(
            valid_reading(
                timestamp="SIMULATED",
                transport="WOKWI_SOFTWARE_SIMULATION",
            )
        )
        self.assertEqual(normalized["timestamp"], "SIMULATED")

    def test_aliases_are_preserved_for_v1_and_conflicts_are_rejected(self):
        payload = valid_reading()
        for canonical, alias in (
            ("node_id", "node"),
            ("soil_moisture_pct", "moisture"),
            ("tilt_deg", "tilt"),
            ("vibration_level", "vibration"),
        ):
            payload.pop(canonical)
            payload[alias] = valid_reading()[canonical]
        normalized = validate_reading(payload)
        self.assertEqual(normalized["node_id"], "HR-01")
        self.assertNotIn("node", normalized)
        self.assertNotIn("moisture", normalized)
        self.assertNotIn("tilt", normalized)
        self.assertNotIn("vibration", normalized)

        with self.assertRaises(SchemaValidationError):
            validate_reading(valid_reading(soil_moisture_pct=20, moisture=21))

    def test_additional_metadata_is_retained_but_not_authoritative(self):
        payload = valid_reading(
            risk_level="CRITICAL",
            demo_score=100,
            reasons=["client supplied"],
            private_note="diagnostic",
        )
        normalized = validate_reading(payload)
        self.assertEqual(normalized["private_note"], "diagnostic")
        self.assertEqual(normalized["risk_level"], "CRITICAL")

    def test_virtual_packet_requires_bounded_bytes_and_identity(self):
        body = str(valid_reading()).encode()
        packet = LoRaPacket(
            packet_id="HR-01-7",
            attempt_id="HR-01-7-a1",
            node_id="HR-01",
            sequence=7,
            attempt_number=1,
            payload=body,
        )
        self.assertEqual(packet.payload, body)
        with self.assertRaises(ValueError):
            LoRaPacket(
                packet_id="too-large",
                attempt_id="attempt",
                node_id="HR-01",
                sequence=0,
                attempt_number=1,
                payload=b"x" * 256,
            )

    def test_timestamp_is_not_replaced_by_server_time_in_schema(self):
        source_timestamp = "2026-11-16T18:30:00.123456Z"
        normalized = validate_reading(valid_reading(timestamp=source_timestamp))
        self.assertEqual(normalized["timestamp"], source_timestamp)
        self.assertNotEqual(
            normalized["timestamp"],
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )


if __name__ == "__main__":
    unittest.main()
