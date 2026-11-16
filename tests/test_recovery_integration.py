import json
import unittest

from himrakshak.gateway import VirtualEdgeGateway
from himrakshak.lora_simulator import ChannelConditions, LoRaPacket, VirtualLoRaChannel
from himrakshak.stations import StationManager


def packet(sequence, packet_id=None, attempt=1):
    packet_id = packet_id or f"reading-{sequence}"
    body = {
        "node_id": "HR-01",
        "sequence": sequence,
        "timestamp": "2026-11-16T18:30:00Z",
        "soil_moisture_pct": 32,
        "tilt_deg": 1,
        "vibration_level": 10,
        "battery_pct": 82,
        "transport": "VIRTUAL_LORA_SIMULATION",
    }
    return LoRaPacket(
        packet_id=packet_id,
        attempt_id=f"{packet_id}-a{attempt}",
        node_id="HR-01",
        sequence=sequence,
        attempt_number=attempt,
        payload=json.dumps(body, separators=(",", ":")).encode(),
    )


class RecoveryIntegrationTests(unittest.TestCase):
    def test_repeated_outage_recovery_preserves_order_and_bounds_history(self):
        channel = VirtualLoRaChannel(seed=8, history_capacity=32)
        manager = StationManager(seed=8)
        gateway = VirtualEdgeGateway(channel, manager)

        for sequence in range(3):
            gateway.submit_packet(packet(sequence))
        gateway.set_gateway_available(False)
        self.assertEqual(gateway.advance_simulation(10000), [])
        gateway.set_gateway_available(True)
        results = gateway.advance_simulation(1000)
        self.assertEqual([item["status"] for item in results], ["accepted"] * 3)
        self.assertEqual(manager.station_details("HR-01")["event_count"], 3)

        for sequence in range(3, 300):
            gateway.submit_packet(packet(sequence))
            gateway.advance_simulation(1000)
        self.assertLessEqual(len(gateway.get_history()), 256)
        self.assertLessEqual(gateway.get_statistics()["queue_depth"], 256)

    def test_loss_then_retry_uses_new_attempt_and_does_not_fabricate_ingestion(self):
        channel = VirtualLoRaChannel(seed=9)
        manager = StationManager(seed=9)
        gateway = VirtualEdgeGateway(channel, manager)
        lost = gateway.submit_packet(
            packet(0, packet_id="logical-0"),
            ChannelConditions(packet_loss_probability=1.0),
        )
        self.assertEqual(lost.status, "lost")
        self.assertIsNone(manager.station_details("HR-01")["latest"])
        retry = gateway.submit_packet(
            packet(0, packet_id="logical-0", attempt=2),
            ChannelConditions(packet_loss_probability=0.0),
        )
        self.assertEqual(retry.status, "queued")
        result = gateway.advance_simulation(5000)[0]
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["attempt_id"], "logical-0-a2")
        self.assertEqual(manager.station_details("HR-01")["event_count"], 1)

    def test_duplicate_and_stale_recovery_paths_remain_distinct(self):
        channel = VirtualLoRaChannel(seed=10)
        manager = StationManager(seed=10)
        gateway = VirtualEdgeGateway(channel, manager)
        gateway.submit_packet(packet(2))
        self.assertEqual(gateway.advance_simulation(5000)[0]["status"], "accepted")
        gateway.submit_packet(packet(1, packet_id="retry-1", attempt=2))
        self.assertEqual(gateway.advance_simulation(5000)[0]["status"], "stale")
        gateway.submit_packet(packet(2, packet_id="logical-2"))
        self.assertEqual(gateway.advance_simulation(5000)[0]["status"], "duplicate")
        self.assertEqual(manager.station_details("HR-01")["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
