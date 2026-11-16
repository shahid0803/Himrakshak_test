import json
import unittest

from himrakshak.gateway import VirtualEdgeGateway
from himrakshak.lora_simulator import LoRaPacket, VirtualLoRaChannel
from himrakshak.stations import StationDisconnectedError, StationManager


def payload(sequence):
    return {
        "node_id": "HR-01",
        "sequence": sequence,
        "timestamp": "2026-11-16T18:30:00Z",
        "soil_moisture_pct": 32,
        "tilt_deg": 1,
        "vibration_level": 10,
        "battery_pct": 82,
        "transport": "VIRTUAL_LORA_SIMULATION",
    }


def packet(sequence, packet_id=None, attempt_id=None):
    packet_id = packet_id or f"logical-{sequence}"
    return LoRaPacket(
        packet_id=packet_id,
        attempt_id=attempt_id or packet_id + "-a1",
        node_id="HR-01",
        sequence=sequence,
        attempt_number=1,
        payload=json.dumps(payload(sequence), separators=(",", ":")).encode(),
    )


class OfflineReliabilityTests(unittest.TestCase):
    def test_station_monitoring_stops_ingestion_but_preserves_local_fault_state(self):
        manager = StationManager(seed=1)
        station = manager.get("HR-01")
        station.receiver_connected = False
        with self.assertRaises(StationDisconnectedError):
            manager.simulate("HR-01", "normal")
        status = manager.station_details("HR-01")["communication"]
        self.assertEqual(status["connection_state"], "disconnected")
        self.assertEqual(status["ingestion_state"], "backend_unavailable")
        self.assertEqual(status["device_state"], "local_only")
        self.assertIsNone(manager.station_details("HR-01")["latest"])

    def test_pending_queue_is_bounded_and_overflow_is_explicit(self):
        manager = StationManager(seed=1)
        for sequence in range(10):
            result = manager.delay_packet("HR-01", payload(sequence))
            self.assertEqual(result["outcome"], "pending")
        with self.assertRaises(Exception) as context:
            manager.delay_packet("HR-01", payload(10))
        self.assertIn("queue is full", str(context.exception))
        self.assertEqual(
            manager.station_details("HR-01")["communication"]["pending_packets"], 10
        )

    def test_gateway_outage_does_not_drain_channel_and_recovery_delivers_once(self):
        channel = VirtualLoRaChannel(seed=4)
        manager = StationManager(seed=4)
        gateway = VirtualEdgeGateway(channel, manager)
        self.assertEqual(gateway.submit_packet(packet(0)).status, "queued")
        gateway.set_gateway_available(False)
        self.assertEqual(gateway.advance_simulation(5000), [])
        self.assertEqual(gateway.get_status()["queued_packets"], 1)
        self.assertEqual(gateway.get_status()["gateway_state"], "unavailable")
        gateway.set_gateway_available(True)
        self.assertEqual(gateway.get_status()["gateway_state"], "recovering")
        results = gateway.advance_simulation(1000)
        self.assertEqual(results[0]["status"], "accepted")
        self.assertEqual(gateway.get_status()["gateway_state"], "available")
        self.assertEqual(manager.station_details("HR-01")["event_count"], 1)

    def test_gateway_status_distinguishes_channel_and_ingestion_states(self):
        channel = VirtualLoRaChannel(seed=5)
        manager = StationManager(seed=5)
        gateway = VirtualEdgeGateway(channel, manager)
        gateway.submit_packet(packet(0))
        queued = gateway.get_status()
        self.assertEqual(queued["channel_state"], "queued")
        self.assertEqual(queued["ingestion_state"], "pending")
        gateway.advance_simulation(5000)
        accepted = gateway.get_status()
        self.assertEqual(accepted["channel_state"], "delivered")
        self.assertEqual(accepted["ingestion_state"], "accepted")

    def test_gateway_reset_restores_available_state(self):
        gateway = VirtualEdgeGateway(VirtualLoRaChannel(seed=6), StationManager(seed=6))
        gateway.set_gateway_available(False)
        gateway.reset()
        status = gateway.get_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["gateway_state"], "available")
        self.assertEqual(status["channel_state"], "idle")
        self.assertEqual(status["ingestion_state"], "pending")


if __name__ == "__main__":
    unittest.main()
