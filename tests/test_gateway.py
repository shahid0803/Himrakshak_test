import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import unittest

from himrakshak.gateway import (
    GatewayIdempotencyConflictError,
    VirtualEdgeGateway,
)
from himrakshak.lora_simulator import ChannelConditions, LoRaPacket, VirtualLoRaChannel
from himrakshak.stations import StationManager


def reading(node_id="HR-01", sequence=0, **extra):
    payload = {
        "node_id": node_id,
        "sequence": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "soil_moisture_pct": 32.0,
        "tilt_deg": 1.0,
        "vibration_level": 10.0,
        "battery_pct": 82.0,
        "transport": "VIRTUAL_LORA_SIMULATION",
    }
    payload.update(extra)
    return payload


def packet(packet_id="logical-0", attempt_id="attempt-0", node_id="HR-01", sequence=0, payload=None):
    body = payload or reading(node_id, sequence)
    return LoRaPacket(
        packet_id=packet_id,
        attempt_id=attempt_id,
        node_id=node_id,
        sequence=sequence,
        attempt_number=1,
        payload=json.dumps(body, separators=(",", ":")).encode(),
    )


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.channel = VirtualLoRaChannel(seed=42)
        self.manager = StationManager(seed=42)
        self.gateway = VirtualEdgeGateway(self.channel, self.manager)

    def deliver(self, gateway=None):
        gateway = gateway or self.gateway
        gateway.advance_simulation(1000)

    def test_end_to_end_delivery_and_backend_risk_authority(self):
        result = self.gateway.submit_packet(packet())
        self.assertEqual(result.status, "queued")
        deliveries = self.gateway.advance_simulation(1000)
        self.assertEqual(deliveries[0]["status"], "accepted")
        self.assertEqual(deliveries[0]["assessment"]["model_id"], "himrakshak-demo-risk-engine-v1")
        self.assertEqual(self.manager.station_details("HR-01")["event_count"], 1)
        stats = self.gateway.get_statistics()
        self.assertEqual(stats["accepted_by_gateway"], 1)
        self.assertEqual(stats["accepted_by_backend"], 1)
        self.assertEqual(stats["channel_primary_deliveries"], 1)

    def test_duplicate_radio_copy_and_retry_are_idempotent(self):
        result = self.gateway.submit_packet(
            packet(), ChannelConditions(duplicate_probability=1.0)
        )
        self.assertEqual(result.scheduled_copies, 2)
        deliveries = self.gateway.advance_simulation(1000)
        self.assertEqual([item["status"] for item in deliveries], ["accepted", "duplicate"])
        retry = self.gateway.submit_packet(
            packet(attempt_id="attempt-1"), idempotency_key="retry-key"
        )
        self.assertEqual(retry.status, "queued")
        deliveries = self.gateway.advance_simulation(1000)
        self.assertEqual(deliveries[0]["status"], "duplicate")
        self.assertEqual(self.manager.station_details("HR-01")["event_count"], 1)

    def test_idempotency_reuse_requires_same_content(self):
        original = packet()
        self.gateway.submit_packet(original, idempotency_key="same")
        cached = self.gateway.submit_packet(original, idempotency_key="same")
        self.assertEqual(cached.status, "queued")
        with self.assertRaises(GatewayIdempotencyConflictError):
            self.gateway.submit_packet(
                packet(sequence=1, packet_id="other"), idempotency_key="same"
            )

    def test_loss_disconnect_recovery_and_stale_sequence(self):
        lost = self.gateway.submit_packet(
            packet(), ChannelConditions(packet_loss_probability=1.0)
        )
        self.assertEqual(lost.status, "lost")
        self.gateway.set_gateway_available(False)
        unavailable = self.gateway.submit_packet(packet("lost", "lost-attempt"))
        self.assertEqual(unavailable.status, "gateway_unavailable")
        self.gateway.set_gateway_available(True)
        self.gateway.submit_packet(packet("accepted", "accepted-attempt", sequence=2))
        self.deliver()
        stale = self.gateway.submit_packet(packet("stale", "stale-attempt", sequence=1))
        self.assertEqual(stale.status, "queued")
        result = self.gateway.advance_simulation(1000)[0]
        self.assertEqual(result["status"], "stale")
        self.assertEqual(self.gateway.get_statistics()["stale_rejections"], 1)

    def test_invalid_payload_does_not_update_station(self):
        invalid = packet(payload={"node_id": "HR-01", "sequence": 0})
        self.gateway.submit_packet(invalid)
        result = self.gateway.advance_simulation(1000)[0]
        self.assertEqual(result["status"], "invalid")
        self.assertIsNone(self.manager.station_details("HR-01")["latest"])

    def test_queue_and_history_are_bounded(self):
        channel = VirtualLoRaChannel(seed=1, queue_capacity=1)
        gateway = VirtualEdgeGateway(channel, self.manager)
        self.assertEqual(gateway.submit_packet(packet()).status, "queued")
        self.assertEqual(gateway.submit_packet(packet("second", "second-attempt")).status, "queue_full")
        self.assertLessEqual(gateway.get_statistics()["pending_deliveries"], 1)
        for index in range(300):
            gateway._record("test", packet(str(index), str(index), sequence=index))
        self.assertLessEqual(len(gateway.get_history()), 256)

    def test_concurrent_submission_is_thread_safe(self):
        def submit(index):
            return self.gateway.submit_packet(
                packet(f"packet-{index}", f"attempt-{index}", sequence=index),
                idempotency_key=f"key-{index}",
            ).status

        with ThreadPoolExecutor(max_workers=8) as executor:
            statuses = list(executor.map(submit, range(20)))
        self.assertTrue(all(status in {"queued", "lost", "queue_full"} for status in statuses))
        self.gateway.advance_simulation(1000)
        self.assertEqual(self.gateway.get_statistics()["transmission_attempts"], 20)

    def test_per_node_diagnostics_and_reset(self):
        self.gateway.submit_packet(packet(node_id="HR-02", packet_id="node2", attempt_id="node2-a"))
        self.gateway.advance_simulation(1000)
        status = self.gateway.get_node_status("HR-02")
        self.assertEqual(status["accepted_by_backend"], 1)
        self.assertEqual(status["last_backend_sequence"], 0)
        self.gateway.reset()
        self.assertEqual(self.gateway.get_statistics()["accepted_by_backend"], 0)


if __name__ == "__main__":
    unittest.main()
