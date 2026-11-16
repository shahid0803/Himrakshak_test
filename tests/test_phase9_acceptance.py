import json
import unittest

from himrakshak.gateway import VirtualEdgeGateway
from himrakshak.lora_simulator import ChannelConditions, LoRaPacket, VirtualLoRaChannel
from himrakshak.risk import assess_risk
from himrakshak.stations import StationManager


def reading(node_id, sequence, **overrides):
    value = {
        "node_id": node_id,
        "sequence": sequence,
        "timestamp": "2026-11-16T18:30:00Z",
        "soil_moisture_pct": 32.0,
        "tilt_deg": 1.0,
        "vibration_level": 10.0,
        "battery_pct": 82.0,
        "transport": "WOKWI_SOFTWARE_SIMULATION",
    }
    value.update(overrides)
    return value


def packet(node_id, sequence, packet_id=None, attempt=1, **overrides):
    packet_id = packet_id or f"{node_id}-logical-{sequence}"
    return LoRaPacket(
        packet_id=packet_id,
        attempt_id=f"{packet_id}-attempt-{attempt}",
        node_id=node_id,
        sequence=sequence,
        attempt_number=attempt,
        payload=json.dumps(
            reading(node_id, sequence, **overrides),
            separators=(",", ":"),
        ).encode("utf-8"),
    )


class Phase9AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.channel = VirtualLoRaChannel(seed=42)
        self.manager = StationManager(seed=42)
        self.gateway = VirtualEdgeGateway(self.channel, self.manager)

    def deliver(self):
        return self.gateway.advance_simulation(5000)

    def test_normal_high_risk_loss_gateway_outage_and_recovery(self):
        for node_id in ("HR-01", "HR-02", "HR-03"):
            self.gateway.submit_packet(packet(node_id, 0))
        results = self.deliver()
        self.assertEqual([result["status"] for result in results], ["accepted"] * 3)
        for node_id in ("HR-01", "HR-02", "HR-03"):
            station = self.manager.station_details(node_id)
            self.assertEqual(station["latest"]["reading"]["sequence"], 0)
            self.assertEqual(
                station["latest"]["assessment"],
                assess_risk(station["latest"]["reading"]),
            )

        high_risk = packet(
            "HR-01",
            1,
            soil_moisture_pct=82.0,
            tilt_deg=8.5,
            vibration_level=85.0,
        )
        self.gateway.submit_packet(high_risk)
        self.assertEqual(self.deliver()[0]["assessment"]["risk_level"], "CRITICAL")

        lost = self.gateway.submit_packet(
            packet("HR-02", 1),
            ChannelConditions(packet_loss_probability=1.0),
        )
        self.assertEqual(lost.status, "lost")
        self.assertEqual(self.manager.station_details("HR-02")["event_count"], 1)

        self.gateway.submit_packet(packet("HR-03", 1))
        self.gateway.set_gateway_available(False)
        self.assertEqual(self.gateway.advance_simulation(5000), [])
        self.assertEqual(self.gateway.get_status()["queued_packets"], 1)
        self.gateway.set_gateway_available(True)
        self.assertEqual(self.deliver()[0]["status"], "accepted")
        self.assertEqual(self.gateway.get_status()["gateway_state"], "available")

    def test_duplicate_retry_and_stale_sequence_are_reconciled(self):
        first = packet("HR-01", 0, packet_id="logical-0")
        self.gateway.submit_packet(first)
        self.assertEqual(self.deliver()[0]["status"], "accepted")

        retry = packet("HR-01", 0, packet_id="logical-0", attempt=2)
        self.gateway.submit_packet(retry)
        self.assertEqual(self.deliver()[0]["status"], "duplicate")

        self.gateway.submit_packet(packet("HR-02", 2))
        self.assertEqual(self.deliver()[0]["status"], "accepted")
        stale = packet("HR-02", 1, packet_id="stale-copy", attempt=1)
        self.gateway.submit_packet(stale)
        self.assertEqual(self.deliver()[0]["status"], "stale")
        self.assertEqual(self.manager.station_details("HR-01")["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
