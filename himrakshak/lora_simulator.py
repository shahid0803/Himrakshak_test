"""Software-only virtual LoRa channel for deterministic HimRakshak experiments.

This module models a configurable radio link.  It does not transmit RF, ingest
station readings, reconcile sequences, or calculate landslide risk.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import hashlib
import heapq
import math
import random
from typing import Any, Deque


NODE_IDS = frozenset({"HR-01", "HR-02", "HR-03"})
SUPPORTED_BANDWIDTHS_HZ = frozenset({7_800, 10_400, 15_600, 20_800, 31_250, 41_700, 62_500, 125_000, 250_000, 500_000})
SUPPORTED_SPREADING_FACTORS = frozenset(range(7, 13))
CODING_RATE_FACTORS = {"4/5": 1, "4/6": 2, "4/7": 3, "4/8": 4}
TERRAIN_OBSTRUCTION_DB = {"clear": 0.0, "moderate": 8.0, "heavy": 18.0}
REQUIRED_SNR_DB = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}
SPEED_OF_LIGHT_M_S = 299_792_458.0


def _finite(value: Any, name: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return result


def _probability(value: Any, name: str) -> float:
    result = _finite(value, name)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return result


@dataclass(frozen=True)
class Airtime:
    symbol_duration_ms: float
    preamble_duration_ms: float
    payload_symbols: int
    payload_duration_ms: float
    total_ms: float


@dataclass(frozen=True)
class RadioProfile:
    """Validated software radio profile; defaults are the proposed HimRakshak profile."""

    frequency_mhz: float = 868.0
    bandwidth_hz: int = 125_000
    spreading_factor: int = 9
    coding_rate: str = "4/5"
    transmission_power_dbm: float = 14.0
    preamble_length: int = 8
    header_mode: str = "explicit"
    crc_enabled: bool = True
    noise_figure_db: float = 6.0
    tx_antenna_gain_dbi: float = 0.0
    rx_antenna_gain_dbi: float = 0.0
    max_payload_size: int = 255
    low_data_rate_optimization: bool | None = None

    def __post_init__(self) -> None:
        frequency = _finite(self.frequency_mhz, "frequency_mhz", 0.0)
        if frequency <= 0.0:
            raise ValueError("frequency_mhz must be greater than 0")
        if self.bandwidth_hz not in SUPPORTED_BANDWIDTHS_HZ:
            raise ValueError(f"unsupported bandwidth_hz: {self.bandwidth_hz}")
        if self.spreading_factor not in SUPPORTED_SPREADING_FACTORS:
            raise ValueError("spreading_factor must be between SF7 and SF12")
        if self.coding_rate not in CODING_RATE_FACTORS:
            raise ValueError("coding_rate must be one of 4/5, 4/6, 4/7, or 4/8")
        _finite(self.transmission_power_dbm, "transmission_power_dbm")
        if self.preamble_length < 1:
            raise ValueError("preamble_length must be positive")
        if self.header_mode not in {"explicit", "implicit"}:
            raise ValueError("header_mode must be explicit or implicit")
        if not isinstance(self.crc_enabled, bool):
            raise ValueError("crc_enabled must be boolean")
        _finite(self.noise_figure_db, "noise_figure_db", 0.0)
        _finite(self.tx_antenna_gain_dbi, "tx_antenna_gain_dbi")
        _finite(self.rx_antenna_gain_dbi, "rx_antenna_gain_dbi")
        if isinstance(self.max_payload_size, bool) or not isinstance(self.max_payload_size, int) or not 1 <= self.max_payload_size <= 255:
            raise ValueError("max_payload_size must be an integer between 1 and 255")
        if self.low_data_rate_optimization is not None and not isinstance(self.low_data_rate_optimization, bool):
            raise ValueError("low_data_rate_optimization must be boolean or None")

    @property
    def coding_rate_factor(self) -> int:
        return CODING_RATE_FACTORS[self.coding_rate]

    @property
    def bandwidth_mhz(self) -> float:
        return self.bandwidth_hz / 1_000_000.0

    @property
    def wavelength_m(self) -> float:
        return SPEED_OF_LIGHT_M_S / (self.frequency_mhz * 1_000_000.0)

    @property
    def low_data_rate_enabled(self) -> bool:
        if self.low_data_rate_optimization is not None:
            return self.low_data_rate_optimization
        return (2**self.spreading_factor / self.bandwidth_hz) >= 0.016

    def airtime(self, payload_length: int) -> Airtime:
        if isinstance(payload_length, bool) or not isinstance(payload_length, int):
            raise ValueError("payload_length must be an integer")
        if not 0 <= payload_length <= self.max_payload_size:
            raise ValueError(f"payload_length must be between 0 and {self.max_payload_size}")
        symbol_seconds = (2**self.spreading_factor) / self.bandwidth_hz
        crc = 1 if self.crc_enabled else 0
        implicit_header = 1 if self.header_mode == "implicit" else 0
        data_optimization = 1 if self.low_data_rate_enabled else 0
        numerator = 8 * payload_length - 4 * self.spreading_factor + 28 + 16 * crc - 20 * implicit_header
        denominator = 4 * (self.spreading_factor - 2 * data_optimization)
        payload_symbols = 8 + max(math.ceil(numerator / denominator) * (self.coding_rate_factor + 4), 0)
        preamble_seconds = (self.preamble_length + 4.25) * symbol_seconds
        payload_seconds = payload_symbols * symbol_seconds
        return Airtime(
            symbol_duration_ms=symbol_seconds * 1000,
            preamble_duration_ms=preamble_seconds * 1000,
            payload_symbols=payload_symbols,
            payload_duration_ms=payload_seconds * 1000,
            total_ms=(preamble_seconds + payload_seconds) * 1000,
        )


@dataclass(frozen=True)
class ChannelConditions:
    """Validated link and fault conditions for one transmission."""

    distance_m: float = 100.0
    terrain: str = "clear"
    obstruction_loss_db: float | None = None
    path_loss_exponent: float = 2.0
    reference_distance_m: float = 1.0
    shadowing_stddev_db: float = 0.0
    packet_loss_probability: float = 0.0
    base_delay_ms: float = 0.0
    jitter_ms: float = 0.0
    duplicate_probability: float = 0.0
    reorder_probability: float = 0.0
    reorder_delay_ms: float = 0.0
    gateway_available: bool = True

    def __post_init__(self) -> None:
        _finite(self.distance_m, "distance_m", 0.001)
        if self.terrain not in TERRAIN_OBSTRUCTION_DB:
            raise ValueError("terrain must be clear, moderate, or heavy")
        if self.obstruction_loss_db is not None:
            _finite(self.obstruction_loss_db, "obstruction_loss_db", 0.0)
        _finite(self.path_loss_exponent, "path_loss_exponent", 0.0)
        if self.path_loss_exponent == 0:
            raise ValueError("path_loss_exponent must be greater than 0")
        _finite(self.reference_distance_m, "reference_distance_m", 0.001)
        _finite(self.shadowing_stddev_db, "shadowing_stddev_db", 0.0)
        _probability(self.packet_loss_probability, "packet_loss_probability")
        _finite(self.base_delay_ms, "base_delay_ms", 0.0)
        _finite(self.jitter_ms, "jitter_ms", 0.0)
        _probability(self.duplicate_probability, "duplicate_probability")
        _probability(self.reorder_probability, "reorder_probability")
        _finite(self.reorder_delay_ms, "reorder_delay_ms", 0.0)
        if not isinstance(self.gateway_available, bool):
            raise ValueError("gateway_available must be boolean")

    @property
    def terrain_loss_db(self) -> float:
        return self.obstruction_loss_db if self.obstruction_loss_db is not None else TERRAIN_OBSTRUCTION_DB[self.terrain]


@dataclass(frozen=True)
class LoRaPacket:
    packet_id: str
    attempt_id: str
    node_id: str
    sequence: int
    attempt_number: int
    payload: bytes

    def __post_init__(self) -> None:
        for field_name in ("packet_id", "attempt_id", "node_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.node_id not in NODE_IDS:
            raise ValueError(f"node_id must be one of {sorted(NODE_IDS)}")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if isinstance(self.attempt_number, bool) or not isinstance(self.attempt_number, int) or self.attempt_number < 1:
            raise ValueError("attempt_number must be a positive integer")
        if not isinstance(self.payload, (bytes, bytearray)):
            raise ValueError("payload must be bytes")
        if len(self.payload) > 255:
            raise ValueError("payload exceeds the 255-byte PHY limit")
        object.__setattr__(self, "payload", bytes(self.payload))

    @property
    def payload_size(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class RadioMetrics:
    airtime_ms: float
    rssi_dbm: float
    noise_floor_dbm: float
    snr_db: float
    sensitivity_dbm: float
    link_margin_db: float
    delivery_probability: float
    path_loss_db: float
    shadowing_db: float


@dataclass(frozen=True)
class ReceivedPacket:
    packet: LoRaPacket
    copy_index: int
    duplicate: bool
    send_time_ms: float
    receive_time_ms: float
    metrics: RadioMetrics


@dataclass(frozen=True)
class TransmissionResult:
    status: str
    reason_code: str
    packet_id: str
    attempt_id: str
    metrics: RadioMetrics | None = None
    scheduled_copies: int = 0
    duplicate_rejected: bool = False


@dataclass
class _NodeStats:
    transmission_attempts: int = 0
    packets_queued: int = 0
    packets_lost: int = 0
    gateway_unavailable: int = 0
    queue_rejections: int = 0
    primary_deliveries: int = 0
    duplicate_copies_queued: int = 0
    duplicate_deliveries: int = 0
    airtime_ms: float = 0.0
    rssi_total_dbm: float = 0.0
    snr_total_db: float = 0.0

    def as_dict(self, pending: int, total_attempts: int) -> dict[str, Any]:
        primary = self.primary_deliveries
        return {
            "transmission_attempts": self.transmission_attempts,
            "packets_queued": self.packets_queued,
            "packets_lost": self.packets_lost,
            "gateway_unavailable": self.gateway_unavailable,
            "queue_rejections": self.queue_rejections,
            "primary_deliveries": primary,
            "duplicate_copies_queued": self.duplicate_copies_queued,
            "duplicate_deliveries": self.duplicate_deliveries,
            "pending_queue_depth": pending,
            "simulated_airtime_ms": self.airtime_ms,
            "simulated_average_rssi_dbm": self.rssi_total_dbm / self.transmission_attempts if self.transmission_attempts else None,
            "simulated_average_snr_db": self.snr_total_db / self.transmission_attempts if self.transmission_attempts else None,
            "simulated_channel_delivery_ratio": primary / total_attempts if total_attempts else 0.0,
        }


class VirtualLoRaChannel:
    """Deterministic virtual radio transport with a bounded simulated-time queue."""

    SOFTWARE_SIMULATION = True

    def __init__(
        self,
        profile: RadioProfile | None = None,
        seed: int | None = None,
        queue_capacity: int = 256,
        history_capacity: int = 256,
    ) -> None:
        self.profile = profile or RadioProfile()
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise ValueError("seed must be an integer when supplied")
        if isinstance(queue_capacity, bool) or not isinstance(queue_capacity, int) or queue_capacity < 1:
            raise ValueError("queue_capacity must be a positive integer")
        if isinstance(history_capacity, bool) or not isinstance(history_capacity, int) or history_capacity < 1:
            raise ValueError("history_capacity must be a positive integer")
        self.seed = seed
        self.queue_capacity = queue_capacity
        self.history_capacity = history_capacity
        self.reset()

    @property
    def time_ms(self) -> float:
        return self._time_ms

    def reset(self) -> None:
        self._time_ms = 0.0
        self._order = 0
        self._queue: list[tuple[float, int, ReceivedPacket]] = []
        self._history: Deque[dict[str, Any]] = deque(maxlen=self.history_capacity)
        self._stats = _NodeStats()
        self._node_stats: dict[str, _NodeStats] = defaultdict(_NodeStats)

    def _rng(self, packet: LoRaPacket, label: str) -> random.Random:
        material = f"{self.seed!r}|{packet.packet_id}|{packet.attempt_id}|{packet.attempt_number}|{label}".encode()
        digest = hashlib.sha256(material).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def _metrics(self, packet: LoRaPacket, conditions: ChannelConditions) -> RadioMetrics:
        airtime = self.profile.airtime(packet.payload_size)
        distance = max(conditions.distance_m, conditions.reference_distance_m)
        free_space_loss = 20 * math.log10(4 * math.pi * distance / self.profile.wavelength_m)
        reference_loss = 20 * math.log10(4 * math.pi * conditions.reference_distance_m / self.profile.wavelength_m)
        distance_loss = reference_loss + 10 * conditions.path_loss_exponent * math.log10(distance / conditions.reference_distance_m)
        path_loss = max(free_space_loss, distance_loss) + conditions.terrain_loss_db
        shadowing = 0.0
        if conditions.shadowing_stddev_db:
            shadowing = self._rng(packet, "shadowing").gauss(0.0, conditions.shadowing_stddev_db)
        rssi = self.profile.transmission_power_dbm + self.profile.tx_antenna_gain_dbi + self.profile.rx_antenna_gain_dbi - path_loss + shadowing
        noise_floor = -174.0 + 10 * math.log10(self.profile.bandwidth_hz) + self.profile.noise_figure_db
        snr = rssi - noise_floor
        sensitivity = noise_floor + REQUIRED_SNR_DB[self.profile.spreading_factor]
        margin = snr - REQUIRED_SNR_DB[self.profile.spreading_factor]
        link_probability = max(0.0, min(1.0, (margin + 10.0) / 20.0))
        delivery_probability = link_probability * (1.0 - conditions.packet_loss_probability)
        return RadioMetrics(
            airtime_ms=airtime.total_ms,
            rssi_dbm=rssi,
            noise_floor_dbm=noise_floor,
            snr_db=snr,
            sensitivity_dbm=sensitivity,
            link_margin_db=margin,
            delivery_probability=delivery_probability,
            path_loss_db=path_loss,
            shadowing_db=shadowing,
        )

    def transmit(self, packet: LoRaPacket, conditions: ChannelConditions | None = None) -> TransmissionResult:
        if not isinstance(packet, LoRaPacket):
            raise TypeError("packet must be a LoRaPacket")
        conditions = conditions or ChannelConditions()
        if packet.payload_size > self.profile.max_payload_size:
            raise ValueError(f"payload exceeds profile max_payload_size of {self.profile.max_payload_size}")
        metrics = self._metrics(packet, conditions)
        self._stats.transmission_attempts += 1
        node_stats = self._node_stats[packet.node_id]
        node_stats.transmission_attempts += 1
        for stats in (self._stats, node_stats):
            stats.airtime_ms += metrics.airtime_ms
            stats.rssi_total_dbm += metrics.rssi_dbm
            stats.snr_total_db += metrics.snr_db
        self._record(packet, "attempt", metrics)
        if not conditions.gateway_available:
            self._stats.gateway_unavailable += 1
            node_stats.gateway_unavailable += 1
            return TransmissionResult("gateway_unavailable", "gateway_unavailable", packet.packet_id, packet.attempt_id, metrics)
        if self._rng(packet, "loss").random() >= metrics.delivery_probability:
            self._stats.packets_lost += 1
            node_stats.packets_lost += 1
            return TransmissionResult("lost", "channel_loss", packet.packet_id, packet.attempt_id, metrics)
        jitter = self._rng(packet, "jitter").uniform(-conditions.jitter_ms, conditions.jitter_ms)
        delay = max(0.0, conditions.base_delay_ms + metrics.airtime_ms + jitter)
        if self._rng(packet, "reorder").random() < conditions.reorder_probability:
            delay += conditions.reorder_delay_ms
        primary = self._schedule(packet, metrics, delay, 0, False, node_stats)
        if not primary:
            return TransmissionResult("queue_full", "queue_full_primary", packet.packet_id, packet.attempt_id, metrics)
        duplicate_rejected = False
        scheduled = 1
        if self._rng(packet, "duplicate").random() < conditions.duplicate_probability:
            duplicate_delay = delay + max(0.0, conditions.reorder_delay_ms)
            if self._schedule(packet, metrics, duplicate_delay, 1, True, node_stats):
                scheduled += 1
                self._stats.duplicate_copies_queued += 1
                node_stats.duplicate_copies_queued += 1
            else:
                duplicate_rejected = True
                self._stats.queue_rejections += 1
                node_stats.queue_rejections += 1
        self._stats.packets_queued += 1
        node_stats.packets_queued += 1
        return TransmissionResult("queued", "queued", packet.packet_id, packet.attempt_id, metrics, scheduled, duplicate_rejected)

    def _schedule(self, packet: LoRaPacket, metrics: RadioMetrics, delay: float, copy_index: int, duplicate: bool, node_stats: _NodeStats) -> bool:
        if len(self._queue) >= self.queue_capacity:
            return False
        self._order += 1
        receive_time = self._time_ms + delay
        received = ReceivedPacket(packet, copy_index, duplicate, self._time_ms, receive_time, metrics)
        heapq.heappush(self._queue, (receive_time, self._order, received))
        self._record(packet, "duplicate_queued" if duplicate else "primary_queued", metrics)
        return True

    def advance_time(self, delta_ms: float) -> float:
        delta = _finite(delta_ms, "delta_ms", 0.0)
        self._time_ms += delta
        return self._time_ms

    def receive_ready(self, max_items: int | None = None) -> list[ReceivedPacket]:
        if max_items is not None and (isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 1):
            raise ValueError("max_items must be a positive integer or None")
        ready: list[ReceivedPacket] = []
        while self._queue and self._queue[0][0] <= self._time_ms and (max_items is None or len(ready) < max_items):
            received = heapq.heappop(self._queue)[2]
            ready.append(received)
            stats = self._node_stats[received.packet.node_id]
            if received.duplicate:
                self._stats.duplicate_deliveries += 1
                stats.duplicate_deliveries += 1
            else:
                self._stats.primary_deliveries += 1
                stats.primary_deliveries += 1
            self._record(received.packet, "duplicate_delivered" if received.duplicate else "primary_delivered", received.metrics)
        return ready

    def get_statistics(self) -> dict[str, Any]:
        return self._stats.as_dict(len(self._queue), self._stats.transmission_attempts) | {
            "software_simulation": True,
            "simulated_time_ms": self._time_ms,
            "queue_capacity": self.queue_capacity,
            "history_depth": len(self._history),
        }

    def get_node_statistics(self, node_id: str) -> dict[str, Any]:
        if node_id not in NODE_IDS:
            raise ValueError(f"node_id must be one of {sorted(NODE_IDS)}")
        return self._node_stats[node_id].as_dict(len([item for item in self._queue if item[2].packet.node_id == node_id]), self._node_stats[node_id].transmission_attempts)

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def _record(self, packet: LoRaPacket, outcome: str, metrics: RadioMetrics) -> None:
        self._history.append({
            "packet_id": packet.packet_id,
            "attempt_id": packet.attempt_id,
            "node_id": packet.node_id,
            "sequence": packet.sequence,
            "outcome": outcome,
            "simulated_time_ms": self._time_ms,
            "rssi_dbm": metrics.rssi_dbm,
            "snr_db": metrics.snr_db,
            "software_simulation": True,
        })


def free_space_path_loss_db(frequency_mhz: float, distance_m: float) -> float:
    profile = RadioProfile(frequency_mhz=frequency_mhz)
    distance = _finite(distance_m, "distance_m", 0.001)
    return 20 * math.log10(4 * math.pi * distance / profile.wavelength_m)


__all__ = [
    "Airtime",
    "ChannelConditions",
    "LoRaPacket",
    "RadioMetrics",
    "RadioProfile",
    "ReceivedPacket",
    "TransmissionResult",
    "VirtualLoRaChannel",
    "free_space_path_loss_db",
]
