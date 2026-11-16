"""Virtual edge gateway connecting the software LoRa channel to stations."""

from __future__ import annotations

from collections import OrderedDict, deque
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import threading
import time
from typing import Any, Mapping

from .lora_simulator import (
    ChannelConditions,
    LoRaPacket,
    RadioProfile,
    ReceivedPacket,
    TransmissionResult,
    VirtualLoRaChannel,
)
from .schema import SchemaValidationError, validate_reading
from .stations import StationManager, StationSequenceConflictError


MAX_GATEWAY_HISTORY = 256
MAX_IDEMPOTENCY_ENTRIES = 256


class GatewayIdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for different content."""


@dataclass(frozen=True)
class GatewayConfig:
    gateway_id: str = "GW-01"
    profile_name: str = "baseline"
    default_conditions: ChannelConditions = ChannelConditions()
    idempotency_capacity: int = MAX_IDEMPOTENCY_ENTRIES
    history_capacity: int = MAX_GATEWAY_HISTORY

    def __post_init__(self) -> None:
        if not self.gateway_id.strip():
            raise ValueError("gateway_id must not be empty")
        if self.idempotency_capacity < 1 or self.history_capacity < 1:
            raise ValueError("gateway capacities must be positive")


class VirtualEdgeGateway:
    """Thread-safe gateway adapter with bounded idempotency and event history."""

    SOFTWARE_SIMULATION = True

    def __init__(
        self,
        channel: VirtualLoRaChannel,
        station_manager: StationManager,
        profile: RadioProfile | None = None,
        config: GatewayConfig | None = None,
    ) -> None:
        self.channel = channel
        self.station_manager = station_manager
        self.config = config or GatewayConfig()
        if profile is not None:
            self.channel.profile = profile
        self._lock = threading.RLock()
        self._available = True
        self._gateway_state = "available"
        self._started_at = time.monotonic()
        self._last_transition_at = self._now()
        self._last_recovery_at: str | None = None
        self._last_received_at: str | None = None
        self._last_successful_forward_at: str | None = None
        self._last_error: str | None = None
        self._last_channel_state = "idle"
        self._last_ingestion_state = "pending"
        self._revision = 1
        self._idempotency: OrderedDict[str, tuple[str, TransmissionResult]] = OrderedDict()
        self._accepted_packet_ids: OrderedDict[str, None] = OrderedDict()
        self._history: deque[dict[str, Any]] = deque(maxlen=self.config.history_capacity)
        self._stats: dict[str, int] = {
            "transmission_attempts": 0,
            "channel_queued": 0,
            "channel_primary_deliveries": 0,
            "lost_packets": 0,
            "gateway_unavailable": 0,
            "duplicate_copies": 0,
            "duplicate_logical_packets_rejected": 0,
            "invalid_packets": 0,
            "stale_rejections": 0,
            "accepted_by_gateway": 0,
            "accepted_by_backend": 0,
        }
        self._node_stats: dict[str, dict[str, int]] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _node(self, node_id: str) -> dict[str, int]:
        return self._node_stats.setdefault(
            node_id,
            {
                "attempts": 0,
                "accepted_by_gateway": 0,
                "accepted_by_backend": 0,
                "duplicate": 0,
                "stale": 0,
                "invalid": 0,
                "lost": 0,
            },
        )

    @staticmethod
    def _fingerprint(packet: LoRaPacket) -> str:
        return hashlib.sha256(
            packet.node_id.encode()
            + b"\0"
            + str(packet.sequence).encode()
            + b"\0"
            + packet.payload
        ).hexdigest()

    def _remember(self, collection: OrderedDict[str, None], key: str) -> None:
        collection[key] = None
        collection.move_to_end(key)
        while len(collection) > self.config.idempotency_capacity:
            collection.popitem(last=False)

    def _record(self, outcome: str, packet: LoRaPacket | None = None, **extra: Any) -> None:
        event: dict[str, Any] = {
            "timestamp": self._now(),
            "outcome": outcome,
            "software_simulation": True,
        }
        if packet is not None:
            event.update(
                {
                    "packet_id": packet.packet_id,
                    "attempt_id": packet.attempt_id,
                    "node_id": packet.node_id,
                    "sequence": packet.sequence,
                }
            )
        event.update(extra)
        self._history.append(event)

    def submit_packet(
        self,
        packet: LoRaPacket,
        conditions: ChannelConditions | None = None,
        idempotency_key: str | None = None,
    ) -> TransmissionResult:
        if not isinstance(packet, LoRaPacket):
            raise TypeError("packet must be a LoRaPacket")
        key = idempotency_key or packet.attempt_id
        fingerprint = self._fingerprint(packet)
        with self._lock:
            cached = self._idempotency.get(key)
            if cached is not None:
                if cached[0] != fingerprint:
                    raise GatewayIdempotencyConflictError(
                        f"idempotency key {key!r} was reused with different packet content"
                    )
                self._idempotency.move_to_end(key)
                return cached[1]
            node = self._node(packet.node_id)
            self._stats["transmission_attempts"] += 1
            node["attempts"] += 1
            if not self._available:
                result = TransmissionResult(
                    "gateway_unavailable",
                    "gateway_unavailable",
                    packet.packet_id,
                    packet.attempt_id,
                )
            else:
                effective = conditions or self.config.default_conditions
                result = self.channel.transmit(packet, effective)
            if result.status == "queued":
                self._last_channel_state = "queued"
                self._stats["channel_queued"] += 1
            elif result.status == "lost":
                self._last_channel_state = "lost"
                self._stats["lost_packets"] += 1
                node["lost"] += 1
            elif result.status == "gateway_unavailable":
                self._last_channel_state = "channel_unavailable"
                self._stats["gateway_unavailable"] += 1
            self._idempotency[key] = (fingerprint, result)
            self._idempotency.move_to_end(key)
            while len(self._idempotency) > self.config.idempotency_capacity:
                self._idempotency.popitem(last=False)
            self._record("transmission_" + result.status, packet, reason_code=result.reason_code)
            return result

    def process_delivery(self, received: ReceivedPacket) -> dict[str, Any]:
        if not isinstance(received, ReceivedPacket):
            raise TypeError("received must be a ReceivedPacket")
        packet = received.packet
        with self._lock:
            self._last_received_at = self._now()
            if not self._available:
                self._stats["gateway_unavailable"] += 1
                self._last_channel_state = "channel_unavailable"
                self._last_ingestion_state = "backend_unavailable"
                self._last_error = "gateway unavailable while processing delivery"
                self._record("delivery_gateway_unavailable", packet)
                return {"status": "gateway_unavailable", "packet_id": packet.packet_id}
            if packet.packet_id in self._accepted_packet_ids:
                self._last_ingestion_state = "duplicate"
                self._stats["duplicate_logical_packets_rejected"] += 1
                self._node(packet.node_id)["duplicate"] += 1
                self._record("duplicate_logical_packet", packet)
                return {"status": "duplicate", "packet_id": packet.packet_id}
            try:
                payload = json.loads(packet.payload.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise SchemaValidationError("payload: must be a dictionary-like object")
                reading = validate_reading(payload)
                if reading["node_id"] != packet.node_id:
                    raise SchemaValidationError(
                        f"node_id: must match packet node {packet.node_id!r}"
                    )
            except (UnicodeDecodeError, json.JSONDecodeError, SchemaValidationError, ValueError) as exc:
                self._stats["invalid_packets"] += 1
                self._last_ingestion_state = "schema_rejected"
                self._node(packet.node_id)["invalid"] += 1
                self._last_error = str(exc)
                self._record("invalid_packet", packet, error=str(exc))
                return {"status": "invalid", "packet_id": packet.packet_id, "error": str(exc)}
            self._stats["accepted_by_gateway"] += 1
            self._last_channel_state = "delivered"
            self._node(packet.node_id)["accepted_by_gateway"] += 1
            try:
                result = self.station_manager.ingest(
                    packet.node_id, reading, "virtual gateway"
                )
            except StationSequenceConflictError as exc:
                classification = exc.classification
                self._node(packet.node_id)[classification] += 1
                if classification == "stale":
                    self._stats["stale_rejections"] += 1
                self._last_ingestion_state = classification
                self._last_error = str(exc)
                self._record("backend_" + classification, packet, error=str(exc))
                return {
                    "status": classification,
                    "packet_id": packet.packet_id,
                    "error": str(exc),
                    "classification": classification,
                }
            except Exception as exc:
                self._last_ingestion_state = "backend_unavailable"
                self._last_error = str(exc)
                self._record("backend_rejected", packet, error=str(exc))
                return {"status": "backend_rejected", "packet_id": packet.packet_id, "error": str(exc)}
            self._remember(self._accepted_packet_ids, packet.packet_id)
            self._stats["accepted_by_backend"] += 1
            self._node(packet.node_id)["accepted_by_backend"] += 1
            self._last_successful_forward_at = self._now()
            self._last_error = None
            self._last_ingestion_state = "accepted"
            self._gateway_state = "available"
            self._record("backend_accepted", packet)
            return {
                "status": "accepted",
                "packet_id": packet.packet_id,
                "attempt_id": packet.attempt_id,
                "reading": result["reading"],
                "assessment": result["assessment"],
                "radio": {
                    "rssi_dbm": received.metrics.rssi_dbm,
                    "snr_db": received.metrics.snr_db,
                    "send_time_ms": received.send_time_ms,
                    "receive_time_ms": received.receive_time_ms,
                    "duplicate": received.duplicate,
                },
            }

    def receive_ready(self, max_items: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if not self._available:
                # Leave due channel packets queued so recovery can process them.
                self._last_channel_state = "channel_unavailable"
                self._last_ingestion_state = "backend_unavailable"
                self._stats["gateway_unavailable"] += 1
                return []
            deliveries = self.channel.receive_ready(max_items)
            self._stats["channel_primary_deliveries"] += sum(
                1 for delivery in deliveries if not delivery.duplicate
            )
            self._stats["duplicate_copies"] += sum(
                1 for delivery in deliveries if delivery.duplicate
            )
            return [self.process_delivery(delivery) for delivery in deliveries]

    def advance_simulation(self, delta_ms: float) -> list[dict[str, Any]]:
        self.channel.advance_time(delta_ms)
        return self.receive_ready()

    def set_gateway_available(self, available: bool) -> None:
        if not isinstance(available, bool):
            raise ValueError("available must be boolean")
        with self._lock:
            if self._available != available:
                self._available = available
                self._last_transition_at = self._now()
                if available:
                    self._gateway_state = "recovering"
                    self._last_recovery_at = self._last_transition_at
                else:
                    self._gateway_state = "unavailable"
            self._record("gateway_available" if available else "gateway_unavailable")

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            channel_stats = self.channel.get_statistics()
            return {
                "gateway_id": self.config.gateway_id,
                "status": "healthy" if self._available else "unavailable",
                "available": self._available,
                "gateway_state": self._gateway_state,
                "channel_connected": self._available,
                "channel_state": self._last_channel_state,
                "ingestion_state": self._last_ingestion_state,
                "queued_packets": len(self.channel._queue),
                "delivered_transmissions": channel_stats["primary_deliveries"],
                "dropped_transmissions": channel_stats["packets_lost"],
                "duplicated_transmissions": channel_stats["duplicate_deliveries"],
                "last_transition_at": self._last_transition_at,
                "last_received_packet_at": self._last_received_at,
                "last_successful_forward_at": self._last_successful_forward_at,
                "last_recovery_at": self._last_recovery_at,
                "last_error": self._last_error,
                "software_simulation": True,
            }

    def get_node_status(self, node_id: str) -> dict[str, Any]:
        with self._lock:
            stats = self._node(node_id)
            station = self.station_manager.station_details(node_id)
            return {
                "node_id": node_id,
                "connection_state": "connected" if self._available else "disconnected",
                "gateway_state": self._gateway_state,
                "channel_state": self._last_channel_state,
                "ingestion_state": self._last_ingestion_state,
                "pending_transmissions": sum(
                    1 for item in self.channel._queue if item[2].packet.node_id == node_id
                ),
                "attempts": stats["attempts"],
                "accepted_by_gateway": stats["accepted_by_gateway"],
                "accepted_by_backend": stats["accepted_by_backend"],
                "duplicate": stats["duplicate"],
                "stale": stats["stale"],
                "last_transmission_id": self._last_transmission_for(node_id),
                "last_backend_sequence": (
                    station["latest"]["reading"]["sequence"] if station["latest"] else None
                ),
                "model": {"name": "virtual-lora", "is_physical_radio": False},
            }

    def _last_transmission_for(self, node_id: str) -> str | None:
        for event in reversed(self._history):
            if event.get("node_id") == node_id and event.get("attempt_id"):
                return event["attempt_id"]
        return None

    def get_statistics(self) -> dict[str, Any]:
        with self._lock:
            channel = self.channel.get_statistics()
            return {
                **deepcopy(self._stats),
                "pending_deliveries": len(self.channel._queue),
                "queue_depth": len(self.channel._queue),
                "channel_delivery_ratio": channel["simulated_channel_delivery_ratio"],
                "per_node": deepcopy(self._node_stats),
                "history_depth": len(self._history),
                "idempotency_cache_depth": len(self._idempotency),
                "software_simulation": True,
            }

    def get_radio_config(self) -> dict[str, Any]:
        profile = self.channel.profile
        conditions = self.config.default_conditions
        return {
            "revision": self._revision,
            "profile": self.config.profile_name,
            "frequency_mhz": profile.frequency_mhz,
            "bandwidth_khz": profile.bandwidth_hz / 1000,
            "spreading_factor": profile.spreading_factor,
            "coding_rate": profile.coding_rate,
            "transmission_power_dbm": profile.transmission_power_dbm,
            "preamble_length": profile.preamble_length,
            "header_mode": profile.header_mode,
            "crc_enabled": profile.crc_enabled,
            "configured_loss_pct": conditions.packet_loss_probability * 100,
            "configured_latency_ms": conditions.base_delay_ms,
            "seed": self.channel.seed,
            "is_physical_radio": False,
        }

    def update_radio_config(self, values: Mapping[str, Any], expected_revision: int | None = None) -> dict[str, Any]:
        with self._lock:
            if expected_revision is not None and expected_revision != self._revision:
                raise ValueError("stale radio configuration revision")
            current = self.channel.profile
            allowed = {
                "frequency_mhz", "bandwidth_khz", "spreading_factor", "coding_rate",
                "transmission_power_dbm", "preamble_length", "header_mode",
                "crc_enabled", "noise_figure_db", "tx_antenna_gain_dbi",
                "rx_antenna_gain_dbi", "max_payload_size",
            }
            unknown = set(values) - allowed - {"expected_revision", "profile"}
            if unknown:
                raise ValueError("unsupported radio configuration field(s): " + ", ".join(sorted(unknown)))
            kwargs = {
                "frequency_mhz": values.get("frequency_mhz", current.frequency_mhz),
                "bandwidth_hz": int(values.get("bandwidth_khz", current.bandwidth_hz / 1000) * 1000),
                "spreading_factor": values.get("spreading_factor", current.spreading_factor),
                "coding_rate": values.get("coding_rate", current.coding_rate),
                "transmission_power_dbm": values.get("transmission_power_dbm", current.transmission_power_dbm),
                "preamble_length": values.get("preamble_length", current.preamble_length),
                "header_mode": values.get("header_mode", current.header_mode),
                "crc_enabled": values.get("crc_enabled", current.crc_enabled),
                "noise_figure_db": values.get("noise_figure_db", current.noise_figure_db),
                "tx_antenna_gain_dbi": values.get("tx_antenna_gain_dbi", current.tx_antenna_gain_dbi),
                "rx_antenna_gain_dbi": values.get("rx_antenna_gain_dbi", current.rx_antenna_gain_dbi),
                "max_payload_size": values.get("max_payload_size", current.max_payload_size),
                "low_data_rate_optimization": current.low_data_rate_optimization,
            }
            self.channel.profile = RadioProfile(**kwargs)
            self._revision += 1
            return self.get_radio_config()

    def get_history(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(list(self._history))

    def reset(self) -> None:
        with self._lock:
            self.channel.reset()
            self._idempotency.clear()
            self._accepted_packet_ids.clear()
            self._history.clear()
            self._stats = {key: 0 for key in self._stats}
            self._node_stats.clear()
            self._available = True
            self._last_transition_at = self._now()
            self._last_received_at = None
            self._last_successful_forward_at = None
            self._last_error = None
            self._gateway_state = "available"
            self._last_recovery_at = None
            self._last_channel_state = "idle"
            self._last_ingestion_state = "pending"
