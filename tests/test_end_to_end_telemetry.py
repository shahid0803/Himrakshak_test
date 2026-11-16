import json
import unittest

from himrakshak.gateway import VirtualEdgeGateway
from himrakshak.lora_simulator import ChannelConditions, LoRaPacket, VirtualLoRaChannel
from himrakshak.risk import assess_risk
from himrakshak.stations import StationManager


def telemetry(sequence, **extra):
    payload = {
        "node_id": "HR-01",
        "sequence": sequence,
        "timestamp": "2026-11-16T18:30:00Z",
        "soil_moisture_pct": 32.0,
        "tilt_deg": 1.0,
        "vibration_level": 10.0,
        "battery_pct": 82.0,
        "transport": "WOKWI_SOFTWARE_SIMULATION",
        "scenario": "normal",
    }
    payload.update(extra)
    return payload


def packet(sequence, packet_id=None, attempt_id=None, payload=None, attempt=1):
    packet_id = packet_id or f"HR-01-{sequence}"
    attempt_id = attempt_id or f"{packet_id}-a{attempt}"
    body = payload or telemetry(sequence)
    return LoRaPacket(
        packet_id=packet_id,
        attempt_id=attempt_id,
        node_id="HR-01",
        sequence=sequence,
        attempt_number=attempt,
        payload=json.dumps(body, separators=(",", ":")).encode("utf-8"),
    )


class EndToEndTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.channel = VirtualLoRaChannel(seed=11)
        self.manager = StationManager(seed=11)
        self.gateway = VirtualEdgeGateway(self.channel, self.manager)

    def test_firmware_like_payload_survives_channel_gateway_and_backend(self):
        original = telemetry(3, soil_moisture_pct=68.4, tilt_deg=4.2)
        submitted = packet(3, payload=original)
        self.gateway.submit_packet(submitted, idempotency_key="HR-01-3")
        result = self.gateway.advance_simulation(5000)[0]
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["reading"], original)
        self.assertEqual(result["assessment"], assess_risk(original))
        self.assertEqual(
            self.manager.station_details("HR-01")["latest"]["reading"],
            original,
        )

    def test_retry_attempt_changes_attempt_identity_not_logical_identity(self):
        first = packet(0, packet_id="logical-0", attempt_id="logical-0-a1", attempt=1)
        retry = packet(0, packet_id="logical-0", attempt_id="logical-0-a2", attempt=2)
        self.gateway.submit_packet(first, idempotency_key="logical-0-a1")
        self.gateway.advance_simulation(5000)
        self.gateway.submit_packet(retry, idempotency_key="logical-0-a2")
        result = self.gateway.advance_simulation(5000)[0]
        self.assertEqual(result["status"], "duplicate")
        history = self.gateway.get_history()
        attempts = [item["attempt_id"] for item in history if item.get("attempt_id")]
        self.assertIn("logical-0-a1", attempts)
        self.assertIn("logical-0-a2", attempts)
        self.assertEqual(self.manager.station_details("HR-01")["event_count"], 1)

    def test_duplicate_radio_copies_ingest_logical_packet_once(self):
        self.gateway.submit_packet(
            packet(0), ChannelConditions(duplicate_probability=1.0)
        )
        results = self.gateway.advance_simulation(5000)
        self.assertEqual([item["status"] for item in results], ["accepted", "duplicate"])
        self.assertEqual(self.manager.station_details("HR-01")["event_count"], 1)

    def test_out_of_order_and_stale_sequences_are_reconciled_by_station_manager(self):
        self.gateway.submit_packet(packet(2))
        self.gateway.advance_simulation(5000)
        self.gateway.submit_packet(packet(1))
        result = self.gateway.advance_simulation(5000)[0]
        self.assertEqual(result["status"], "stale")
        self.assertEqual(
            self.manager.station_details("HR-01")["latest"]["reading"]["sequence"],
            2,
        )

    def test_client_risk_fields_are_not_forwarded_as_authority(self):
        payload = telemetry(
            0,
            risk_level="CRITICAL",
            demo_score=100,
            # Keep the forged fields within the simulated 255-byte PHY limit.
        )
        self.gateway.submit_packet(packet(0, payload=payload))
        result = self.gateway.advance_simulation(5000)[0]
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["assessment"], assess_risk(payload))
        self.assertEqual(result["assessment"]["risk_level"], "NORMAL")
        self.assertEqual(
            result["assessment"]["model_id"], "himrakshak-demo-risk-engine-v1"
        )

    def test_timestamp_and_metadata_are_preserved_separately_from_event_time(self):
        payload = telemetry(
            0,
            timestamp="2026-11-16T18:30:00.123456Z",
            transport="WOKWI_SOFTWARE_SIMULATION",
            acquisition_id="sensor-read-0",
        )
        self.gateway.submit_packet(packet(0, payload=payload))
        result = self.gateway.advance_simulation(5000)[0]
        self.assertEqual(result["reading"]["timestamp"], payload["timestamp"])
        self.assertEqual(result["reading"]["acquisition_id"], "sensor-read-0")
        event = self.manager.station_details("HR-01")["events"][0]
        self.assertNotEqual(event["timestamp"], payload["timestamp"])
        self.assertEqual(event["reading"]["timestamp"], payload["timestamp"])
        self.assertTrue(event["timestamp"].endswith("Z"))

    def test_invalid_schema_payload_is_rejected_before_station_ingestion(self):
        invalid = telemetry(0, battery_pct=101)
        self.gateway.submit_packet(packet(0, payload=invalid))
        result = self.gateway.advance_simulation(5000)[0]
        self.assertEqual(result["status"], "invalid")
        self.assertIsNone(self.manager.station_details("HR-01")["latest"])


if __name__ == "__main__":
    unittest.main()
