import unittest

from himrakshak.lora_simulator import (
    ChannelConditions,
    LoRaPacket,
    RadioProfile,
    VirtualLoRaChannel,
    free_space_path_loss_db,
)


def packet(packet_id="p1", attempt_id="a1", node_id="HR-01", sequence=0, attempt_number=1, payload=b"telemetry"):
    return LoRaPacket(packet_id, attempt_id, node_id, sequence, attempt_number, payload)


class RadioProfileTests(unittest.TestCase):
    def test_default_profile_and_airtime(self):
        profile = RadioProfile()
        airtime = profile.airtime(10)
        self.assertEqual((profile.frequency_mhz, profile.bandwidth_hz, profile.spreading_factor, profile.coding_rate), (868.0, 125000, 9, "4/5"))
        self.assertAlmostEqual(airtime.symbol_duration_ms, 4.096)
        self.assertEqual(airtime.payload_symbols, 23)
        self.assertAlmostEqual(airtime.total_ms, 144.384)

    def test_airtime_changes_with_phy_options(self):
        self.assertGreater(RadioProfile(spreading_factor=12).airtime(10).total_ms, RadioProfile(spreading_factor=7).airtime(10).total_ms)
        self.assertGreater(RadioProfile(bandwidth_hz=62_500).airtime(10).total_ms, RadioProfile(bandwidth_hz=250_000).airtime(10).total_ms)
        self.assertNotEqual(RadioProfile(crc_enabled=True).airtime(10).payload_symbols, RadioProfile(crc_enabled=False).airtime(10).payload_symbols)
        self.assertNotEqual(RadioProfile(header_mode="explicit").airtime(10).payload_symbols, RadioProfile(header_mode="implicit").airtime(10).payload_symbols)

    def test_invalid_profiles_are_rejected(self):
        for kwargs in (
            {"spreading_factor": 6}, {"bandwidth_hz": 123}, {"coding_rate": "4/9"},
            {"transmission_power_dbm": float("nan")}, {"frequency_mhz": 0},
            {"max_payload_size": 256}, {"preamble_length": 0},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    RadioProfile(**kwargs)


class PropagationTests(unittest.TestCase):
    def test_free_space_loss_and_link_metrics(self):
        self.assertAlmostEqual(free_space_path_loss_db(868.0, 100.0), 71.223, places=2)
        near = VirtualLoRaChannel(seed=1).transmit(packet(), ChannelConditions(distance_m=10))
        far = VirtualLoRaChannel(seed=1).transmit(packet(), ChannelConditions(distance_m=1000))
        self.assertGreater(near.metrics.rssi_dbm, far.metrics.rssi_dbm)
        heavy = VirtualLoRaChannel(seed=1).transmit(packet(), ChannelConditions(terrain="heavy"))
        clear = VirtualLoRaChannel(seed=1).transmit(packet(), ChannelConditions(terrain="clear"))
        self.assertGreater(clear.metrics.rssi_dbm, heavy.metrics.rssi_dbm)
        self.assertAlmostEqual(near.metrics.sensitivity_dbm, near.metrics.noise_floor_dbm - 12.5)

    def test_conditions_validate_distances_and_probabilities(self):
        for kwargs in ({"distance_m": 0}, {"packet_loss_probability": 2}, {"jitter_ms": -1}, {"terrain": "himalayan"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    ChannelConditions(**kwargs)


class ChannelTests(unittest.TestCase):
    def test_virtual_time_schedules_and_delivers(self):
        channel = VirtualLoRaChannel(seed=4)
        result = channel.transmit(packet(), ChannelConditions(base_delay_ms=20))
        self.assertEqual((result.status, result.reason_code), ("queued", "queued"))
        self.assertEqual(channel.receive_ready(), [])
        channel.advance_time(result.metrics.airtime_ms + 19)
        self.assertEqual(channel.receive_ready(), [])
        channel.advance_time(1)
        delivered = channel.receive_ready()
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0].packet.packet_id, "p1")

    def test_loss_gateway_duplicate_and_queue_overflow(self):
        lost = VirtualLoRaChannel(seed=1).transmit(packet(), ChannelConditions(packet_loss_probability=1.0))
        self.assertEqual(lost.status, "lost")
        unavailable = VirtualLoRaChannel(seed=1).transmit(packet(), ChannelConditions(gateway_available=False))
        self.assertEqual(unavailable.status, "gateway_unavailable")
        duplicate = VirtualLoRaChannel(seed=1).transmit(packet(), ChannelConditions(duplicate_probability=1.0))
        self.assertEqual(duplicate.scheduled_copies, 2)
        full = VirtualLoRaChannel(seed=1, queue_capacity=1).transmit(packet(), ChannelConditions(duplicate_probability=1.0))
        self.assertEqual((full.status, full.duplicate_rejected), ("queued", True))

    def test_reordering_and_identity(self):
        channel = VirtualLoRaChannel(seed=8)
        conditions = ChannelConditions(reorder_probability=1.0, reorder_delay_ms=100)
        first = packet("first", "attempt-first")
        second = packet("second", "attempt-second")
        channel.transmit(first, conditions)
        channel.transmit(second, ChannelConditions(base_delay_ms=50))
        channel.advance_time(500)
        received = channel.receive_ready()
        self.assertEqual([item.packet.packet_id for item in received], ["second", "first"])
        self.assertEqual(received[0].packet.attempt_id, "attempt-second")

    def test_determinism_is_independent_of_unrelated_order(self):
        conditions = ChannelConditions(shadowing_stddev_db=2.0, jitter_ms=10.0)
        a = packet("a", "a1")
        b = packet("b", "b1")
        left = VirtualLoRaChannel(seed=99)
        right = VirtualLoRaChannel(seed=99)
        left_a = left.transmit(a, conditions)
        right.transmit(b, conditions)
        right_a = right.transmit(a, conditions)
        self.assertEqual(left_a, right_a)

    def test_stats_and_bounded_history(self):
        channel = VirtualLoRaChannel(seed=2, history_capacity=3)
        for index in range(4):
            channel.transmit(packet(str(index), str(index), sequence=index), ChannelConditions())
        channel.advance_time(1000)
        channel.receive_ready()
        stats = channel.get_statistics()
        self.assertEqual(stats["transmission_attempts"], 4)
        self.assertEqual(stats["primary_deliveries"], 4)
        self.assertEqual(stats["simulated_channel_delivery_ratio"], 1.0)
        self.assertEqual(stats["pending_queue_depth"], 0)
        self.assertEqual(len(channel.get_history()), 3)
        self.assertEqual(channel.get_node_statistics("HR-01")["primary_deliveries"], 4)

    def test_packet_validation_and_phase5_contract(self):
        with self.assertRaises(ValueError):
            packet(node_id="HR-99")
        with self.assertRaises(ValueError):
            packet(sequence=-1)
        with self.assertRaises(ValueError):
            packet(attempt_number=0)
        channel = VirtualLoRaChannel()
        result = channel.transmit(packet(payload=b"future gateway bytes"))
        self.assertEqual(result.status, "queued")
        channel.advance_time(1000)
        received = channel.receive_ready()[0]
        self.assertEqual(received.packet.payload, b"future gateway bytes")
        self.assertEqual(received.packet.sequence, 0)


if __name__ == "__main__":
    unittest.main()
