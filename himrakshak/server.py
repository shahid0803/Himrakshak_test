"""Local-only and cloud-ready HTTP API and dashboard server for HimRakshak."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hmac
import json
import math
import mimetypes
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit

from .gateway import (
    GatewayIdempotencyConflictError,
    VirtualEdgeGateway,
)
from .lora_simulator import LoRaPacket, VirtualLoRaChannel
from .risk import MODEL_ID
from .schema import SchemaValidationError
from .stations import (
    PendingQueueEmptyError,
    PendingQueueFullError,
    StationDisconnectedError,
    StationManager,
    StationSequenceConflictError,
    STATION_ROSTER,
)


API_VERSION = 1
MAX_BODY_BYTES = 64 * 1024
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ROOT = (PROJECT_ROOT / "frontend").resolve()
FRONTEND_MIME_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}


@dataclass(frozen=True)
class ServerConfig:
    """Resolved startup configuration for HimRakshak server."""

    host: str
    port: int
    allow_remote: bool
    admin_key: str | None
    rate_limit_interval: float
    device_tokens: Mapping[str, str] = field(default_factory=dict)


def resolve_server_config(
    host_arg: str | None = None,
    port_arg: int | None = None,
    allow_remote_arg: bool = False,
    environ: Mapping[str, str] | None = None,
) -> ServerConfig:
    """Resolve and validate server host, port, remote mode, and security settings."""
    env = os.environ if environ is None else environ
    allow_remote = bool(allow_remote_arg)

    admin_key_raw = env.get("HIMRAKSHAK_ADMIN_KEY")
    admin_key = (
        admin_key_raw.strip() if admin_key_raw and admin_key_raw.strip() else None
    )
    device_tokens_raw = env.get("HIMRAKSHAK_DEVICE_TOKENS")
    device_tokens: dict[str, str] = {}
    if device_tokens_raw and device_tokens_raw.strip():
        try:
            parsed_tokens = json.loads(device_tokens_raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "HIMRAKSHAK_DEVICE_TOKENS must be a JSON object mapping station IDs to tokens"
            ) from exc
        if not isinstance(parsed_tokens, dict):
            raise ValueError(
                "HIMRAKSHAK_DEVICE_TOKENS must be a JSON object mapping station IDs to tokens"
            )
        valid_stations = {node_id for node_id, _ in STATION_ROSTER}
        for station_id, token in parsed_tokens.items():
            if (
                not isinstance(station_id, str)
                or station_id not in valid_stations
                or not isinstance(token, str)
                or not token.strip()
            ):
                raise ValueError(
                    "HIMRAKSHAK_DEVICE_TOKENS may contain only registered station IDs and non-empty string tokens"
                )
            device_tokens[station_id] = token.strip()

    rate_limit_raw = env.get("HIMRAKSHAK_INGEST_MIN_INTERVAL_SECONDS")
    if rate_limit_raw is not None and rate_limit_raw.strip():
        try:
            rate_limit_interval = float(rate_limit_raw)
            if rate_limit_interval < 0 or not math.isfinite(rate_limit_interval):
                raise ValueError()
        except ValueError:
            raise ValueError(
                "HIMRAKSHAK_INGEST_MIN_INTERVAL_SECONDS must be a non-negative number"
            )
    else:
        rate_limit_interval = 3.0 if allow_remote else 0.0

    if allow_remote:
        if host_arg is not None and host_arg not in {"0.0.0.0", "127.0.0.1"}:
            raise ValueError(
                f"Invalid host {host_arg!r} for remote mode; use 0.0.0.0"
            )
        host = host_arg if host_arg is not None else "0.0.0.0"

        port_env = env.get("PORT")
        if port_env is not None and port_env.strip():
            try:
                port = int(port_env)
            except ValueError:
                raise ValueError("PORT environment variable must be an integer")
        elif port_arg is not None:
            port = port_arg
        else:
            port = 10000
    else:
        if host_arg is not None and host_arg != "127.0.0.1":
            raise ValueError("--host must remain 127.0.0.1 for local-only service")
        host = "127.0.0.1"
        port = port_arg if port_arg is not None else 8765

    if not (1 <= port <= 65535):
        raise ValueError(f"Port must be between 1 and 65535 (got {port})")

    return ServerConfig(
        host=host,
        port=port,
        allow_remote=allow_remote,
        admin_key=admin_key,
        rate_limit_interval=rate_limit_interval,
        device_tokens=device_tokens,
    )


class IngestionRateLimiter:
    """Thread-safe in-memory rate limiter for station reading ingestion."""

    def __init__(self, min_interval_seconds: float):
        self.min_interval = float(min_interval_seconds)
        self.lock = threading.Lock()
        self._last_ingest_time: dict[str, float] = {}

    def check_and_record(self, station_id: str) -> float | None:
        """Check if ingestion is permitted for station_id.

        Returns retry_after seconds if rate-limited, or None if allowed.
        """
        if self.min_interval <= 0:
            return None
        valid_stations = {node_id for node_id, _ in STATION_ROSTER}
        if station_id not in valid_stations:
            return None

        now = time.monotonic()
        with self.lock:
            last_time = self._last_ingest_time.get(station_id)
            if last_time is not None:
                elapsed = now - last_time
                if elapsed < self.min_interval:
                    retry_after = round(self.min_interval - elapsed, 2)
                    return max(0.01, retry_after)
            self._last_ingest_time[station_id] = now
            return None


class HimRakshakHandler(BaseHTTPRequestHandler):
    """Serve the dashboard and station-aware JSON API."""

    server_version = "HimRakshak/1"

    def __init__(self, *args: Any, **kwargs: Any):
        self._body_read = False
        super().__init__(*args, **kwargs)

    @property
    def manager(self) -> StationManager:
        return self.server.station_manager  # type: ignore[attr-defined]

    @property
    def server_config(self) -> ServerConfig:
        return self.server.config  # type: ignore[attr-defined]

    @property
    def rate_limiter(self) -> IngestionRateLimiter:
        return self.server.rate_limiter  # type: ignore[attr-defined]

    @property
    def gateway(self) -> VirtualEdgeGateway:
        return self.server.gateway  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(
        self, status: int, message: str, details: Mapping[str, Any] | None = None
    ) -> None:
        self._discard_request_body()
        error: dict[str, Any] = {"status": status, "message": message}
        if details:
            error.update(details)
        self._send_json(status, {"error": error})

    def _send_rate_limit_error(self, station_id: str, retry_after: float) -> None:
        seconds = int(math.ceil(retry_after))
        body = json.dumps(
            {
                "error": {
                    "status": HTTPStatus.TOO_MANY_REQUESTS,
                    "message": (
                        f"Rate limit exceeded for station {station_id!r}. "
                        f"Retry after {seconds} seconds."
                    ),
                }
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(HTTPStatus.TOO_MANY_REQUESTS)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Retry-After", str(seconds))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _check_admin_auth(self) -> bool:
        """Verify administrative authorization for mutation routes."""
        config = self.server_config
        if not config.allow_remote and not config.admin_key:
            return True
        if not config.admin_key:
            self._discard_request_body()
            self._send_error(
                HTTPStatus.FORBIDDEN,
                "Administrative mutation endpoints are disabled in remote mode when HIMRAKSHAK_ADMIN_KEY is not configured",
            )
            return False

        provided = self.headers.get("X-HimRakshak-Admin")
        if not provided:
            self._discard_request_body()
            self._send_error(
                HTTPStatus.UNAUTHORIZED,
                "Missing administrative authorization header (X-HimRakshak-Admin)",
            )
            return False

        if not hmac.compare_digest(provided, config.admin_key):
            self._discard_request_body()
            self._send_error(
                HTTPStatus.FORBIDDEN,
                "Invalid administrative credentials",
            )
            return False

        return True

    def _valid_admin_auth(self) -> bool:
        config = self.server_config
        provided = self.headers.get("X-HimRakshak-Admin")
        return bool(
            config.admin_key
            and provided
            and hmac.compare_digest(provided, config.admin_key)
        )

    def _check_device_auth(self, station_id: str) -> bool:
        """Require a station-scoped device token for remote telemetry."""
        if not self.server_config.allow_remote:
            return True
        expected = self.server_config.device_tokens.get(station_id)
        if not expected:
            self._discard_request_body()
            self._send_error(
                HTTPStatus.FORBIDDEN,
                f"Device telemetry ingestion is disabled for station {station_id!r}",
            )
            return False
        provided = self.headers.get("X-HimRakshak-Device-Token")
        if not provided:
            self._discard_request_body()
            self._send_error(
                HTTPStatus.UNAUTHORIZED,
                "Missing device authorization header (X-HimRakshak-Device-Token)",
            )
            return False
        if not hmac.compare_digest(provided, expected):
            self._discard_request_body()
            self._send_error(
                HTTPStatus.FORBIDDEN,
                "Invalid device credentials",
            )
            return False
        return True

    def _check_transmission_auth(self, station_id: str) -> bool:
        """Allow admin emulator calls or station-scoped device telemetry."""
        if not self.server_config.allow_remote or self._valid_admin_auth():
            return True
        return self._check_device_auth(station_id)

    def _read_json(self) -> dict[str, Any] | None:
        length_text = self.headers.get("Content-Length")
        try:
            length = int(length_text) if length_text is not None else -1
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "Content-Length must be an integer")
            return None
        if length < 0:
            self._send_error(HTTPStatus.BAD_REQUEST, "Request body length is required")
            return None
        if length > MAX_BODY_BYTES:
            self._body_read = True
            self.rfile.read(min(length, MAX_BODY_BYTES + 1))
            self._send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large")
            return None
        self._body_read = True
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_error(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON")
            return None
        if not isinstance(payload, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "Request body must be a JSON object")
            return None
        return payload

    def _read_optional_json(self) -> dict[str, Any] | None:
        length_text = self.headers.get("Content-Length")
        if length_text in (None, "", "0"):
            return {}
        return self._read_json()

    def _api_path(self) -> str:
        return urlsplit(self.path).path

    def _discard_request_body(self) -> None:
        if getattr(self, "_body_read", False):
            return
        length_text = self.headers.get("Content-Length")
        if not length_text:
            return
        try:
            length = int(length_text)
        except ValueError:
            return
        if 0 < length <= MAX_BODY_BYTES:
            try:
                self._body_read = True
                self.rfile.read(length)
            except Exception:
                pass

    @staticmethod
    def _station_id(path: str, suffix: str) -> str | None:
        prefix = "/api/stations/"
        if not path.startswith(prefix) or not path.endswith(suffix):
            return None
        value = path[len(prefix) : -len(suffix)] if suffix else path[len(prefix) :]
        return unquote(value).strip("/") or None

    @staticmethod
    def _fault_action(path: str) -> tuple[str, str] | None:
        prefix = "/api/stations/"
        marker = "/faults/"
        if not path.startswith(prefix) or marker not in path:
            return None
        station, action = path[len(prefix) :].split(marker, 1)
        station = unquote(station).strip("/")
        action = unquote(action).strip("/")
        if not station or not action or "/" in action:
            return None
        return station, action

    def _v2_json(self, data: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "api_version": 2,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": dict(data),
        }

    def _handle_v2_get(self, path: str) -> bool:
        if path == "/api/v2/radio/config":
            self._send_json(HTTPStatus.OK, self._v2_json(self.gateway.get_radio_config()))
            return True
        if path == "/api/v2/radio/status":
            self._send_json(HTTPStatus.OK, self._v2_json(self.gateway.get_status()))
            return True
        if path == "/api/v2/gateway/health":
            status = self.gateway.get_status()
            self._send_json(
                HTTPStatus.OK,
                self._v2_json(
                    {
                        "gateway_id": status["gateway_id"],
                        "status": status["status"],
                        "process_uptime_seconds": round(time.monotonic() - self.server.gateway_started_at, 3),
                        "channel_connected": status["channel_connected"],
                        "backend_reachable": True,
                        "queued_packets": status["queued_packets"],
                        "last_successful_forward_at": status["last_successful_forward_at"],
                        "last_error": status["last_error"],
                        "software_simulation": True,
                    }
                ),
            )
            return True
        prefix = "/api/v2/stations/"
        suffix = "/radio-diagnostics"
        if path.startswith(prefix) and path.endswith(suffix):
            node_id = unquote(path[len(prefix) : -len(suffix)]).strip("/")
            try:
                data = self.gateway.get_node_status(node_id)
            except (KeyError, ValueError):
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown station")
                return True
            self._send_json(HTTPStatus.OK, self._v2_json(data))
            return True
        return False

    def _handle_v2_post(self, path: str) -> bool:
        if path != "/api/v2/radio/transmissions":
            return False
        if (
            self.server_config.allow_remote
            and not self._valid_admin_auth()
            and not self.headers.get("X-HimRakshak-Device-Token")
        ):
            self._discard_request_body()
            self._send_error(
                HTTPStatus.UNAUTHORIZED,
                "Missing administrative authorization or device authorization header",
            )
            return True
        payload = self._read_json()
        if payload is None:
            return True
        try:
            transmission_id = payload.get("transmission_id")
            idempotency_key = payload.get("idempotency_key")
            node_id = payload.get("node_id")
            sequence = payload.get("device_sequence")
            reading = payload.get("payload")
            if not all(isinstance(value, str) and value.strip() for value in (transmission_id, idempotency_key, node_id)):
                raise ValueError("transmission_id, idempotency_key, and node_id are required strings")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
                raise ValueError("device_sequence must be a non-negative integer")
            if not isinstance(reading, dict):
                raise ValueError("payload must be a JSON object")
            if not self._check_transmission_auth(node_id):
                return True
            if payload.get("channel_profile", "baseline") != "baseline":
                raise ValueError("channel_profile must be baseline")
            if reading.get("node_id", reading.get("node")) != node_id:
                raise ValueError("payload node_id must match node_id")
            normalized = self.gateway.station_manager.get(node_id)
            del normalized
            reading_bytes = json.dumps(reading, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            packet = LoRaPacket(
                packet_id=idempotency_key,
                attempt_id=transmission_id,
                node_id=node_id,
                sequence=sequence,
                attempt_number=payload.get("attempt_number", 1),
                payload=reading_bytes,
            )
            result = self.gateway.submit_packet(packet, idempotency_key=idempotency_key)
            data = {
                "transmission_id": transmission_id,
                "idempotency_key": idempotency_key,
                "status": "scheduled" if result.status == "queued" else result.status,
                "attempt": packet.attempt_number,
                "channel": "virtual-lora",
                "reason_code": result.reason_code,
                "scheduled_copies": result.scheduled_copies,
            }
            self._send_json(HTTPStatus.OK, self._v2_json(data))
        except GatewayIdempotencyConflictError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (KeyError, ValueError, TypeError) as exc:
            self._send_error(
                HTTPStatus.NOT_FOUND if isinstance(exc, KeyError) else HTTPStatus.BAD_REQUEST,
                str(exc),
            )
        except Exception:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Transmission could not be processed")
        return True

    def do_GET(self) -> None:
        self._discard_request_body()
        path = self._api_path()
        if path.startswith("/api/v2/") and self._handle_v2_get(path):
            return
        if path == "/frontend" or path.startswith("/frontend/"):
            self._serve_frontend(path)
            return
        if path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "HimRakshak",
                    "api_version": API_VERSION,
                    "model_id": MODEL_ID,
                    "illustrative": True,
                    "station_count": len(STATION_ROSTER),
                },
            )
            return
        if path == "/api/state":
            self._send_json(HTTPStatus.OK, self.manager.legacy_state())
            return
        if path == "/api/stations":
            self._send_json(HTTPStatus.OK, self.manager.overview())
            return
        if self._fault_action(path) is not None:
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")
            return
        station_id = self._station_id(path, "")
        if station_id is not None:
            try:
                details = self.manager.station_details(station_id)
            except KeyError:
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown station")
                return
            self._send_json(HTTPStatus.OK, {"station": details})
            return
        if path in {"/api/readings", "/api/simulate", "/api/stations"}:
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")
            return
        if path.startswith("/api/"):
            self._send_error(HTTPStatus.NOT_FOUND, "Unknown API route")
            return
        if path in {"/", "/index.html"}:
            try:
                body = (PROJECT_ROOT / "index.html").read_bytes()
            except OSError:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Dashboard is unavailable")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Resource not found")

    def _serve_frontend(self, path: str) -> None:
        """Serve only regular files beneath the fixed frontend allowlist."""
        relative = unquote(path[len("/frontend") :]).lstrip("/")
        if not relative or "\\" in relative or "\x00" in relative:
            self._send_error(HTTPStatus.NOT_FOUND, "Resource not found")
            return
        candidate = (FRONTEND_ROOT / Path(relative)).resolve()
        try:
            candidate.relative_to(FRONTEND_ROOT)
        except ValueError:
            self._send_error(HTTPStatus.NOT_FOUND, "Resource not found")
            return
        if not candidate.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "Resource not found")
            return
        try:
            body = candidate.read_bytes()
        except OSError:
            self._send_error(HTTPStatus.NOT_FOUND, "Resource not found")
            return
        content_type = FRONTEND_MIME_TYPES.get(candidate.suffix.lower())
        if content_type is None:
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = self._api_path()
        if path.startswith("/api/v2/") and self._handle_v2_post(path):
            return
        fault = self._fault_action(path)
        if fault is not None:
            if not self._check_admin_auth():
                return
            self._handle_fault(*fault)
            return
        station_id = self._station_id(path, "/simulate")
        operation = "simulate"
        if station_id is None:
            station_id = self._station_id(path, "/readings")
            operation = "readings"
        if station_id is not None:
            self._handle_station_post(station_id, operation)
            return
        if path not in {"/api/readings", "/api/simulate"}:
            if path in {"/api/health", "/api/state", "/api/stations"}:
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")
            elif path.startswith("/api/"):
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown API route")
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Resource not found")
            return

        if path == "/api/simulate":
            if not self._check_admin_auth():
                return

        payload = self._read_json()
        if payload is None:
            return
        try:
            if path == "/api/simulate":
                station_id = payload.get("station", payload.get("node_id", "HR-01"))
                if not isinstance(station_id, str):
                    raise ValueError("station must be a string")
                result = self.manager.simulate(station_id, payload.get("scenario"))
            else:
                station_id = payload.get("node_id", payload.get("node", "HR-01"))
                if not isinstance(station_id, str):
                    raise ValueError("node_id must be a string")
                retry_after = self.rate_limiter.check_and_record(station_id)
                if retry_after is not None:
                    self._send_rate_limit_error(station_id, retry_after)
                    return
                result = self.manager.ingest(station_id, payload)
            self._send_json(HTTPStatus.OK, result)
        except StationSequenceConflictError as exc:
            self._send_error(
                HTTPStatus.CONFLICT,
                str(exc),
                {
                    "classification": exc.classification,
                    "sequence": exc.sequence,
                    "latest_sequence": exc.latest_sequence,
                },
            )
        except StationDisconnectedError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (KeyError, SchemaValidationError, ValueError) as exc:
            self._send_error(
                HTTPStatus.NOT_FOUND if isinstance(exc, KeyError) else HTTPStatus.BAD_REQUEST,
                str(exc),
            )
        except Exception:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Request could not be processed")

    def _handle_station_post(self, station_id: str, operation: str) -> None:
        try:
            self.manager.get(station_id)
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "Unknown station")
            return
        if operation == "simulate":
            if not self._check_admin_auth():
                return
        payload = self._read_json()
        if payload is None:
            return
        try:
            if operation == "simulate":
                result = self.manager.simulate(station_id, payload.get("scenario"))
            else:
                if not self._check_device_auth(station_id):
                    return
                retry_after = self.rate_limiter.check_and_record(station_id)
                if retry_after is not None:
                    self._send_rate_limit_error(station_id, retry_after)
                    return
                result = self.manager.ingest(station_id, payload, "api reading")
            self._send_json(HTTPStatus.OK, result)
        except StationSequenceConflictError as exc:
            self._send_error(
                HTTPStatus.CONFLICT,
                str(exc),
                {
                    "classification": exc.classification,
                    "sequence": exc.sequence,
                    "latest_sequence": exc.latest_sequence,
                },
            )
        except StationDisconnectedError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (SchemaValidationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "Unknown station")
        except Exception:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Request could not be processed")

    def _handle_fault(self, station_id: str, action: str) -> None:
        try:
            self.manager.get(station_id)
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "Unknown station")
            return
        payload = (
            self._read_optional_json()
            if action in {"release", "disconnect", "reconnect"}
            else self._read_json()
        )
        if payload is None:
            return
        try:
            if action in {"drop", "delay", "duplicate", "stale", "deliver"}:
                reading = payload.get("reading", payload)
                if not isinstance(reading, dict):
                    raise ValueError("reading must be a JSON object")
                if action == "drop":
                    result = self.manager.drop_packet(station_id, reading)
                elif action == "delay":
                    result = self.manager.delay_packet(station_id, reading)
                else:
                    if not self._check_device_auth(station_id):
                        return
                    result = self.manager.deliver_packet(
                        station_id, reading, f"reliability {action}"
                    )
            elif action == "release":
                result = self.manager.release_packet(station_id)
            elif action == "disconnect":
                result = self.manager.disconnect(station_id)
            elif action == "reconnect":
                result = self.manager.reconnect(station_id)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown reliability action")
                return
            self._send_json(HTTPStatus.OK, result)
        except PendingQueueFullError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (
            PendingQueueEmptyError,
            StationDisconnectedError,
            KeyError,
        ) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except SchemaValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception:
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Reliability request could not be processed",
            )

    def do_PUT(self) -> None:
        path = self._api_path()
        if path != "/api/v2/radio/config":
            self._method_not_allowed()
            return
        if not self._check_admin_auth():
            return
        payload = self._read_json()
        if payload is None:
            return
        try:
            expected_revision = payload.get("expected_revision")
            if expected_revision is not None and (
                isinstance(expected_revision, bool)
                or not isinstance(expected_revision, int)
            ):
                raise ValueError("expected_revision must be an integer")
            data = self.gateway.update_radio_config(payload, expected_revision)
            self._send_json(HTTPStatus.OK, self._v2_json(data))
        except ValueError as exc:
            status = (
                HTTPStatus.CONFLICT
                if "stale radio configuration revision" in str(exc)
                else HTTPStatus.BAD_REQUEST
            )
            self._send_error(status, str(exc))
        except Exception:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Radio configuration could not be updated")

    def _method_not_allowed(self) -> None:
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed")

    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed


class HimRakshakServer(ThreadingHTTPServer):
    """Threading HTTP server carrying station manager state."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address_or_config: tuple[str, int] | ServerConfig,
        seed: int | None = None,
    ):
        if isinstance(server_address_or_config, ServerConfig):
            self.config = server_address_or_config
        else:
            self.config = ServerConfig(
                host=server_address_or_config[0],
                port=server_address_or_config[1],
                allow_remote=False,
                admin_key=None,
                rate_limit_interval=0.0,
            )
        self.station_manager = StationManager(seed=seed)
        self.rate_limiter = IngestionRateLimiter(self.config.rate_limit_interval)
        self.channel = VirtualLoRaChannel(seed=seed)
        self.gateway = VirtualEdgeGateway(self.channel, self.station_manager)
        self.gateway_started_at = time.monotonic()
        super().__init__((self.config.host, self.config.port), HimRakshakHandler)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local HimRakshak API and dashboard."
    )
    parser.add_argument(
        "--host",
        default=None,
        help="bind address (default: 127.0.0.1; 0.0.0.0 with --allow-remote)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="HTTP port (default: 8765 local, 10000 or $PORT remote)",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="enable remote cloud binding (0.0.0.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="optional simulator seed",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = resolve_server_config(
            host_arg=args.host,
            port_arg=args.port,
            allow_remote_arg=args.allow_remote,
        )
        server = HimRakshakServer(config, seed=args.seed)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"HimRakshak server running on http://{config.host}:{server.server_address[1]}/"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
