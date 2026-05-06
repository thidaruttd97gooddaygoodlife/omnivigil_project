from __future__ import annotations

"""
MS2 Ingestor (FastAPI)
======================

This service is the ingress gateway for machine telemetry and acts as a
stateful-to-stateless transformer for downstream services.

Core responsibilities:
1. Consume MQTT messages from omnivigil/telemetry (QoS 1).
2. Buffer incoming messages in an internal queue so MQTT callback threads stay
    lightweight and non-blocking.
3. Normalize payloads (legacy flat shape and nested metrics shape).
4. Validate payload completeness (reject if more than 30% sensor fields missing).
5. Clamp sensor values to engineering-safe bounds.
6. Compute a quality score for monitoring telemetry health.
7. Dual-write:
    - InfluxDB for durable time-series storage (batched writes).
    - Redis List for hot-path reads with rolling window retention.

Design notes:
- The service keeps a small in-memory cache only as a fallback.
- Redis is treated as the real-time source for API reads when available.
- Influx write failures are buffered and retried from an internal deque.
"""

import json
import logging
import os
import queue
import threading
from collections import deque
import ssl
from datetime import datetime, timezone
from typing import Deque, List, Optional
from uuid import uuid4

import httpx
import paho.mqtt.client as mqtt
import redis
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions
from pydantic import BaseModel, Field, ValidationError

from app.sensor_standards import evaluate_sensor_value, standards_as_dict

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="MS2 IoT Ingestor", version="0.3.0")
logger = logging.getLogger("ms2-ingestor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TelemetryReading(BaseModel):
    device_id: str
    machine_type: Optional[str] = None
    line: Optional[str] = None
    zone: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    temperature_c: Optional[float] = None
    vibration_rms: Optional[float] = None
    rpm: Optional[float] = None
    pressure_bar: Optional[float] = None
    flow_lpm: Optional[float] = None
    current_a: Optional[float] = None
    oil_temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    power_kw: Optional[float] = None


class IngestResponse(BaseModel):
    accepted: bool
    cleaned: TelemetryReading
    stored_count: int
    ingest_id: str


class IngestAnalyzeResponse(BaseModel):
    ingest: IngestResponse
    analysis: Optional[dict] = None
    error: Optional[str] = None


class QualityRecord(BaseModel):
    device_id: str
    timestamp: datetime
    quality_score: float
    completeness_pct: float
    warning_count: int
    critical_count: int
    jump_count: int
    status_by_sensor: dict[str, str]

# Configuration from environment variables with defaults and type parsing.
_ai_engine_url = os.getenv("AI_ENGINE_URL", "").strip()
_analyze_window_size = int(os.getenv("ANALYZE_WINDOW_SIZE", "70"))
_ms1_auth_url = os.getenv("MS1_AUTH_URL", "http://localhost:8001")
_internal_service_key = os.getenv("INTERNAL_SERVICE_KEY", "").strip()

_bearer_scheme = HTTPBearer(auto_error=False)

_mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
_mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
_mqtt_topic = os.getenv("MQTT_TOPIC", "omnivigil/telemetry")
_mqtt_username = os.getenv("MQTT_USERNAME")
_mqtt_password = os.getenv("MQTT_PASSWORD")
_mqtt_qos = int(os.getenv("MQTT_QOS", "1"))
_mqtt_buffer_size = int(os.getenv("MQTT_BUFFER_SIZE", "20000"))

_influx_url = os.getenv("INFLUXDB_URL")
_influx_token = os.getenv("INFLUXDB_TOKEN")
_influx_org = os.getenv("INFLUXDB_ORG")
_influx_bucket = os.getenv("INFLUXDB_BUCKET")
_influx_batch_size = int(os.getenv("INFLUXDB_BATCH_SIZE", "200"))
_influx_flush_ms = int(os.getenv("INFLUXDB_FLUSH_INTERVAL_MS", "1500"))
_influx_client: Optional[InfluxDBClient] = None
_write_api = None

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis_key_prefix = os.getenv("REDIS_TELEMETRY_PREFIX", "telemetry:device")
_redis_max_points = int(os.getenv("REDIS_MAX_POINTS_PER_DEVICE", "5000"))
_redis_client: Optional[redis.Redis] = None

_max_readings = int(os.getenv("MAX_IN_MEMORY_READINGS", "5000"))
_max_pending_writes = int(os.getenv("MAX_PENDING_INFLUX_WRITES", "10000"))
_readings: Deque[TelemetryReading] = deque(maxlen=_max_readings)
_pending_writes: Deque[TelemetryReading] = deque(maxlen=_max_pending_writes)
_quality_records: Deque[QualityRecord] = deque(maxlen=_max_readings)
_last_by_device: dict[str, TelemetryReading] = {}

_mqtt_buffer: queue.Queue[bytes] = queue.Queue(maxsize=_mqtt_buffer_size)
_ingest_stop_event = threading.Event()
_state_lock = threading.Lock()
_stats: dict[str, object] = {
    "mqtt_messages_total": 0,
    "mqtt_buffer_overflow_total": 0,
    "mqtt_parse_errors_total": 0,
    "invalid_payload_total": 0,
    "influx_write_success_total": 0,
    "influx_write_error_total": 0,
    "redis_write_success_total": 0,
    "redis_write_error_total": 0,
    "stored_total": 0,
    "quality_warning_total": 0,
    "quality_critical_total": 0,
    "quality_jump_total": 0,
    "quality_avg_score": 100.0,
    "last_ingest_at": None,
    "last_device_id": None,
    "last_error": None,
}

_sensor_keys = [
    "temperature_c",
    "vibration_rms",
    "rpm",
    "pressure_bar",
    "flow_lpm",
    "current_a",
    "oil_temp_c",
    "humidity_pct",
    "power_kw",
]

_clamp_ranges: dict[str, tuple[float, float]] = {
    "temperature_c": (0.0, 150.0),
    "vibration_rms": (0.0, 50.0),
    "rpm": (0.0, 20000.0),
    "pressure_bar": (0.0, 25.0),
    "flow_lpm": (0.0, 5000.0),
    "current_a": (0.0, 1200.0),
    "oil_temp_c": (0.0, 220.0),
    "humidity_pct": (0.0, 100.0),
    "power_kw": (0.0, 2500.0),
}


def _verify_jwt_or_internal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    x_internal_key: Optional[str] = Header(default=None),
) -> dict:
    # This dependency is used by API routes that require authentication.
    # It accepts either:
    # - a real JWT token validated by MS1, or
    # - a shared internal key for trusted service-to-service calls.
    if _internal_service_key and x_internal_key == _internal_service_key:
        return {"role": "system", "username": "internal-service"}

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        response = httpx.get(
            f"{_ms1_auth_url}/auth/verify",
            headers={"Authorization": f"Bearer {credentials.credentials}"},
            timeout=3.0,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("valid"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return payload
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"JWT verification failed: {exc}") from exc


def _clamp(value: Optional[float], low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    return max(low, min(high, value))


def _normalize_payload(payload: dict) -> dict:
    """Normalize both telemetry formats into the internal flat schema.

    Supported input formats:
    1) Nested packet (preferred):
       {"device_id": "...", "ts": "...", "metrics": {...}}
    2) Legacy flat packet:
       {"device_id": "...", "timestamp": "...", "temperature_c": ...}
    """
    if "metrics" in payload and isinstance(payload["metrics"], dict):
        normalized = dict(payload["metrics"])
        normalized["device_id"] = payload.get("device_id")
        normalized["machine_type"] = payload.get("machine_type")
        normalized["line"] = payload.get("line")
        normalized["zone"] = payload.get("zone")
        ts = payload.get("ts") or payload.get("timestamp")
        if ts is not None:
            normalized["timestamp"] = ts
        return normalized

    normalized = dict(payload)
    if "ts" in normalized and "timestamp" not in normalized:
        normalized["timestamp"] = normalized["ts"]
    return normalized


def _metrics_completeness(payload: dict) -> float:
    """Return the percentage of expected sensor keys that are present."""
    present = sum(1 for key in _sensor_keys if payload.get(key) is not None)
    return (present / len(_sensor_keys)) * 100.0


def _validate_payload_completeness(payload: dict) -> None:
    """Raise ValueError when payload misses more than 30% of sensor fields."""
    completeness_pct = _metrics_completeness(payload)
    missing_ratio = 1.0 - (completeness_pct / 100.0)
    if missing_ratio > 0.30:
        raise ValueError(f"Telemetry payload missing too many metrics ({missing_ratio:.0%})")


def _build_quality_record(cleaned: TelemetryReading, previous: Optional[TelemetryReading]) -> QualityRecord:
    """Compute a telemetry quality record for observability and analytics.

    The score combines:
    - Sensor warning/critical status counts.
    - Sudden jumps compared to the previous reading for the same device.
    - Completeness penalty for missing sensor dimensions.
    """
    status_by_sensor: dict[str, str] = {}
    warning_count = 0
    critical_count = 0
    jump_count = 0

    for key in _sensor_keys:
        value = getattr(cleaned, key)
        status = evaluate_sensor_value(key, value)
        status_by_sensor[key] = status
        if status == "warning":
            warning_count += 1
        elif status == "critical":
            critical_count += 1

        if previous is not None and value is not None:
            prev = getattr(previous, key)
            if prev is not None:
                delta = abs(value - prev)
                baseline = max(abs(prev), 1.0)
                if delta / baseline > 0.5:
                    jump_count += 1

    completeness_pct = round(_metrics_completeness(cleaned.model_dump(mode="python")), 2)
    penalty = warning_count * 6.0 + critical_count * 20.0 + jump_count * 4.0 + (100.0 - completeness_pct) * 0.4
    quality_score = max(0.0, min(100.0, 100.0 - penalty))

    return QualityRecord(
        device_id=cleaned.device_id,
        timestamp=cleaned.timestamp,
        quality_score=round(quality_score, 2),
        completeness_pct=completeness_pct,
        warning_count=warning_count,
        critical_count=critical_count,
        jump_count=jump_count,
        status_by_sensor=status_by_sensor,
    )


def _clean_reading(reading: TelemetryReading) -> TelemetryReading:
    """Clamp sensor values into configured engineering guardrails."""
    return TelemetryReading(
        device_id=reading.device_id,
        machine_type=reading.machine_type,
        line=reading.line,
        zone=reading.zone,
        timestamp=reading.timestamp,
        temperature_c=_clamp(reading.temperature_c, *_clamp_ranges["temperature_c"]),
        vibration_rms=_clamp(reading.vibration_rms, *_clamp_ranges["vibration_rms"]),
        rpm=_clamp(reading.rpm, *_clamp_ranges["rpm"]),
        pressure_bar=_clamp(reading.pressure_bar, *_clamp_ranges["pressure_bar"]),
        flow_lpm=_clamp(reading.flow_lpm, *_clamp_ranges["flow_lpm"]),
        current_a=_clamp(reading.current_a, *_clamp_ranges["current_a"]),
        oil_temp_c=_clamp(reading.oil_temp_c, *_clamp_ranges["oil_temp_c"]),
        humidity_pct=_clamp(reading.humidity_pct, *_clamp_ranges["humidity_pct"]),
        power_kw=_clamp(reading.power_kw, *_clamp_ranges["power_kw"]),
    )


def _init_redis() -> None:
    """Initialize Redis client for hot-path storage (best-effort)."""
    global _redis_client
    try:
        _redis_client = redis.from_url(_redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Redis hot-path initialized url=%s", _redis_url)
    except Exception as exc:
        _redis_client = None
        logger.warning("Redis disabled: %s", exc)


def _init_influx() -> None:
    """Initialize InfluxDB client with batching and retry options."""
    global _influx_client, _write_api
    if not (_influx_url and _influx_token and _influx_org and _influx_bucket):
        logger.info("InfluxDB config missing. Skipping InfluxDB writer.")
        return

    _influx_client = InfluxDBClient(url=_influx_url, token=_influx_token, org=_influx_org)
    _write_api = _influx_client.write_api(
        write_options=WriteOptions(
            batch_size=_influx_batch_size,
            flush_interval=_influx_flush_ms,
            jitter_interval=500,
            retry_interval=5000,
            max_retries=5,
            max_retry_delay=30000,
            exponential_base=2,
        )
    )
    logger.info(
        "InfluxDB writer initialized bucket=%s org=%s batch_size=%s flush_ms=%s",
        _influx_bucket,
        _influx_org,
        _influx_batch_size,
        _influx_flush_ms,
    )


def _write_influx(reading: TelemetryReading, quality: Optional[QualityRecord] = None) -> bool:
    """Write one telemetry point to InfluxDB (queued/batched by client)."""
    if not _write_api:
        return False

    point = Point("telemetry").tag("device_id", reading.device_id)
    if reading.machine_type:
        point = point.tag("machine_type", reading.machine_type)
    if reading.line:
        point = point.tag("line", reading.line)
    if reading.zone:
        point = point.tag("zone", reading.zone)

    for key in _sensor_keys:
        value = getattr(reading, key)
        if value is not None:
            point = point.field(key, float(value))

    if quality is not None:
        point = (
            point.field("quality_score", quality.quality_score)
            .field("quality_completeness_pct", quality.completeness_pct)
            .field("quality_warning_count", float(quality.warning_count))
            .field("quality_critical_count", float(quality.critical_count))
            .field("quality_jump_count", float(quality.jump_count))
        )

    point = point.time(reading.timestamp, WritePrecision.NS)
    _write_api.write(bucket=_influx_bucket, org=_influx_org, record=point)
    return True


def _hot_path_key(device_id: str) -> str:
    return f"{_redis_key_prefix}:{device_id}"


def _write_redis(reading: TelemetryReading, quality: QualityRecord) -> bool:
    """Append telemetry to per-device Redis list and trim to rolling window.

    Pattern:
    - RPUSH telemetry:device:<device_id> <json>
    - LTRIM telemetry:device:<device_id> -5000 -1

    This keeps a hot-path history per device for fast reads and AI windowing.
    """
    if _redis_client is None:
        return False

    key = _hot_path_key(reading.device_id)
    payload = reading.model_dump(mode="json")
    payload["ts"] = payload["timestamp"]
    payload["quality_score"] = quality.quality_score
    payload["quality_completeness_pct"] = quality.completeness_pct

    pipe = _redis_client.pipeline(transaction=False)
    pipe.rpush(key, json.dumps(payload))
    pipe.ltrim(key, -_redis_max_points, -1)
    pipe.execute()
    return True


def _load_readings_from_redis(device_id: str, limit: int) -> List[TelemetryReading]:
    """Fetch recent telemetry for one device from Redis hot-path list."""
    if _redis_client is None:
        return []

    raw_items = _redis_client.lrange(_hot_path_key(device_id), -limit, -1)
    readings: List[TelemetryReading] = []
    for item in raw_items:
        try:
            payload = _normalize_payload(json.loads(item))
            readings.append(TelemetryReading(**payload))
        except Exception:
            continue
    return readings


def _load_recent_readings(limit: int) -> List[TelemetryReading]:
    """Fetch recent telemetry across devices, preferring Redis over memory."""
    if _redis_client is None:
        with _state_lock:
            return list(_readings)[-limit:]

    collected: List[TelemetryReading] = []
    for key in _redis_client.scan_iter(match=f"{_redis_key_prefix}:*"):
        device_id = key.rsplit(":", 1)[-1]
        collected.extend(_load_readings_from_redis(device_id, limit))

    collected.sort(key=lambda item: item.timestamp)
    return collected[-limit:]


def _store_reading(cleaned: TelemetryReading) -> None:
    """Persist one cleaned reading through the dual-write pipeline."""
    with _state_lock:
        previous = _last_by_device.get(cleaned.device_id)
    quality = _build_quality_record(cleaned, previous)

    with _state_lock:
        _readings.append(cleaned)
        _quality_records.append(quality)
        _last_by_device[cleaned.device_id] = cleaned
        _stats["stored_total"] = int(_stats["stored_total"]) + 1
        _stats["quality_warning_total"] = int(_stats["quality_warning_total"]) + quality.warning_count
        _stats["quality_critical_total"] = int(_stats["quality_critical_total"]) + quality.critical_count
        _stats["quality_jump_total"] = int(_stats["quality_jump_total"]) + quality.jump_count
        prev_avg = float(_stats["quality_avg_score"])
        total = int(_stats["stored_total"])
        _stats["quality_avg_score"] = round(((prev_avg * (total - 1)) + quality.quality_score) / total, 2)
        _stats["last_ingest_at"] = cleaned.timestamp.isoformat()
        _stats["last_device_id"] = cleaned.device_id

    _flush_pending_writes(max_items=100)

    try:
        if _write_redis(cleaned, quality):
            with _state_lock:
                _stats["redis_write_success_total"] = int(_stats["redis_write_success_total"]) + 1
    except Exception as exc:
        with _state_lock:
            _stats["redis_write_error_total"] = int(_stats["redis_write_error_total"]) + 1
            _stats["last_error"] = f"Redis write failed: {exc}"
        logger.warning("Redis write failed: %s", exc)

    try:
        if _write_influx(cleaned, quality=quality):
            with _state_lock:
                _stats["influx_write_success_total"] = int(_stats["influx_write_success_total"]) + 1
    except Exception as exc:
        with _state_lock:
            if len(_pending_writes) < _pending_writes.maxlen:
                _pending_writes.append(cleaned)
            _stats["influx_write_error_total"] = int(_stats["influx_write_error_total"]) + 1
            _stats["last_error"] = f"Influx write failed: {exc}"
        logger.warning("InfluxDB write failed. buffered=%s error=%s", len(_pending_writes), exc)


def _flush_pending_writes(max_items: int = 200) -> None:
    """Retry buffered Influx writes after transient failures."""
    if not _write_api:
        return

    processed = 0
    while processed < max_items:
        with _state_lock:
            if not _pending_writes:
                return
            pending = _pending_writes.popleft()
            previous = _last_by_device.get(pending.device_id)

        quality = _build_quality_record(pending, previous)

        try:
            _write_influx(pending, quality=quality)
            with _state_lock:
                _stats["influx_write_success_total"] = int(_stats["influx_write_success_total"]) + 1
        except Exception as exc:
            with _state_lock:
                _pending_writes.appendleft(pending)
                _stats["influx_write_error_total"] = int(_stats["influx_write_error_total"]) + 1
                _stats["last_error"] = f"Influx retry failed: {exc}"
            logger.warning("InfluxDB retry failed: %s", exc)
            return
        processed += 1


def _slice_for_analysis(device_id: str, window_size: int) -> List[TelemetryReading]:
    """Get latest N points for a device (Redis-first, memory fallback)."""
    redis_readings = _load_readings_from_redis(device_id, window_size)
    if redis_readings:
        return redis_readings

    with _state_lock:
        fallback = [item for item in _readings if item.device_id == device_id]
    return fallback[-window_size:]


def _dispatch_ai_window(device_id: str, window_size: int) -> tuple[Optional[dict], Optional[str]]:
    """Send a windowed telemetry slice to MS3 for async-capable analysis."""
    if not _ai_engine_url:
        return None, "AI_ENGINE_URL is not configured"

    window = _slice_for_analysis(device_id, window_size)
    if not window:
        return None, f"No telemetry window available for device_id={device_id}"

    payload = {"telemetry": [item.model_dump(mode="json") for item in window]}
    try:
        response = httpx.post(f"{_ai_engine_url}/analyze", json=payload, timeout=2.5)
        if response.status_code not in (200, 202):
            return None, f"AI engine returned {response.status_code}: {response.text}"
        if not response.content:
            return {"status": "accepted", "status_code": response.status_code}, None
        return response.json(), None
    except httpx.HTTPError as exc:
        return None, str(exc)


def _process_payload_bytes(payload_bytes: bytes) -> None:
    """Full ingestion pipeline for one MQTT payload bytes blob."""
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        normalized = _normalize_payload(payload)
        _validate_payload_completeness(normalized)
        reading = TelemetryReading(**normalized)
        cleaned = _clean_reading(reading)
        _store_reading(cleaned)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        with _state_lock:
            _stats["mqtt_parse_errors_total"] = int(_stats["mqtt_parse_errors_total"]) + 1
            _stats["invalid_payload_total"] = int(_stats["invalid_payload_total"]) + 1
            _stats["last_error"] = f"MQTT payload error: {exc}"
        logger.warning("MQTT payload error: %s", exc)
    except Exception as exc:
        with _state_lock:
            _stats["last_error"] = f"MQTT message error: {exc}"
        logger.exception("Unexpected MQTT message error")


def _ingest_worker_loop() -> None:
    """Background worker that drains internal MQTT queue and processes payloads."""
    logger.info("Ingest worker started with queue_size=%s", _mqtt_buffer_size)
    while not _ingest_stop_event.is_set():
        try:
            payload_bytes = _mqtt_buffer.get(timeout=1.0)
        except queue.Empty:
            continue

        try:
            _process_payload_bytes(payload_bytes)
        finally:
            _mqtt_buffer.task_done()

    logger.info("Ingest worker stopped")


def _start_ingest_worker() -> None:
    """Start ingestion worker thread on service startup."""
    thread = threading.Thread(target=_ingest_worker_loop, daemon=True, name="ms2-ingest-worker")
    thread.start()
    app.state.ingest_worker = thread


def _on_connect(client, userdata, flags, reason_code, properties) -> None:
    if reason_code == 0:
        client.subscribe(_mqtt_topic, qos=_mqtt_qos)
        logger.info("MQTT connected broker=%s:%s topic=%s qos=%s", _mqtt_broker, _mqtt_port, _mqtt_topic, _mqtt_qos)
    else:
        logger.warning("MQTT connect failed: %s", reason_code)


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties) -> None:
    if reason_code != 0:
        logger.warning("MQTT disconnected unexpectedly rc=%s", reason_code)


def _on_message(client, userdata, message) -> None:
    """MQTT callback: enqueue payload only; heavy work is done by worker thread."""
    with _state_lock:
        _stats["mqtt_messages_total"] = int(_stats["mqtt_messages_total"]) + 1

    try:
        _mqtt_buffer.put_nowait(message.payload)
    except queue.Full:
        with _state_lock:
            _stats["mqtt_buffer_overflow_total"] = int(_stats["mqtt_buffer_overflow_total"]) + 1
            _stats["last_error"] = "MQTT internal buffer overflow"
        logger.warning("MQTT internal buffer overflow: dropping message")


def _start_mqtt() -> None:
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"ms2-ingestor-{uuid4()}"
        )
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        if _mqtt_username and _mqtt_password:
            client.username_pw_set(_mqtt_username, _mqtt_password)
            
        if _mqtt_port == 8883 or str(os.getenv("MQTT_USE_TLS", "")).lower() in ["true", "1", "yes"]:
            client.tls_set(tls_version=ssl.PROTOCOL_TLS)
            
        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect
        client.on_message = _on_message
        client.connect(_mqtt_broker, _mqtt_port, 60)
        client.loop_start()
        app.state.mqtt_client = client
    except Exception as exc:
        with _state_lock:
            _stats["last_error"] = f"MQTT connection skipped: {exc}"
        logger.warning("MQTT connection skipped: %s", exc)


@app.get("/health")
# Health endpoint for MS2 ingestor to report service status and integration state.
# Includes readiness details for InfluxDB, Redis, MQTT buffer, and pending writes.
def health() -> dict:
    with _state_lock:
        queued = len(_pending_writes)
        mqtt_buffer_depth = _mqtt_buffer.qsize()
    return {
        "status": "ok",
        "service": "ms2-ingestor",
        "influx_enabled": bool(_write_api),
        "redis_enabled": bool(_redis_client),
        "pending_influx_writes": queued,
        "mqtt_buffer_depth": mqtt_buffer_depth,
        "mqtt_topic": _mqtt_topic,
    }


@app.get("/stats")
# Protected statistics endpoint for internal monitoring and debugging.
# Returns runtime counters, buffer depths, and quality record counts.
def stats(_: dict = Depends(_verify_jwt_or_internal)) -> dict:
    with _state_lock:
        snapshot = dict(_stats)
        snapshot["in_memory_readings"] = len(_readings)
        snapshot["pending_influx_writes"] = len(_pending_writes)
        snapshot["quality_records"] = len(_quality_records)
        snapshot["mqtt_buffer_depth"] = _mqtt_buffer.qsize()
    return snapshot


@app.get("/quality/reference")
# Public reference endpoint exposing quality standards and thresholds.
# Clients can use this to display validation rules and engineering disclaimers.
def quality_reference() -> dict:
    return {
        "version": "1.1",
        "standards": standards_as_dict(),
        "disclaimer": "Thresholds are engineering defaults and must be validated against plant OEM/manual/SOP before production alerting.",
    }


@app.get("/quality/readings", response_model=List[QualityRecord])
# Protected endpoint returning recent quality assessment records.
# Useful for audit, debugging, and dashboards that surface validation status.
def quality_readings(limit: int = 100, _: dict = Depends(_verify_jwt_or_internal)) -> List[QualityRecord]:
    with _state_lock:
        data = list(_quality_records)[-limit:]
    return data


@app.on_event("startup")
def startup() -> None:
    _init_influx()
    _init_redis()
    _start_ingest_worker()
    _start_mqtt()


@app.on_event("shutdown")
def shutdown() -> None:
    _ingest_stop_event.set()
    worker = getattr(app.state, "ingest_worker", None)
    if worker and worker.is_alive():
        worker.join(timeout=3.0)

    client = getattr(app.state, "mqtt_client", None)
    if client:
        client.loop_stop()
        client.disconnect()

    if _write_api:
        _write_api.flush()
    if _influx_client:
        _influx_client.close()
    if _redis_client:
        _redis_client.close()


@app.post("/ingest", response_model=IngestResponse)
# HTTP ingestion endpoint for telemetry posted directly to MS2.
# Validates completeness, cleans the reading, stores it, and returns accepted metadata.
def ingest(reading: TelemetryReading, _: dict = Depends(_verify_jwt_or_internal)) -> IngestResponse:
    """HTTP ingestion entrypoint with the same validation/cleaning as MQTT path."""
    try:
        _validate_payload_completeness(reading.model_dump(mode="python"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cleaned = _clean_reading(reading)
    _store_reading(cleaned)
    with _state_lock:
        stored_count = len(_readings)

    return IngestResponse(
        accepted=True,
        cleaned=cleaned,
        stored_count=stored_count,
        ingest_id=str(uuid4()),
    )


@app.post("/ingest/analyze", response_model=IngestAnalyzeResponse)
# Batch ingestion plus AI analysis trigger.
# Accepts multiple telemetry readings, stores them, and uses latest device window to call MS3.
def ingest_analyze(reading: List[TelemetryReading], _: dict = Depends(_verify_jwt_or_internal)) -> IngestAnalyzeResponse:
    """Ingest a batch and trigger AI analysis using latest Redis window per device."""
    if not reading:
        raise HTTPException(status_code=400, detail="reading list cannot be empty")

    cleaned: List[TelemetryReading] = []
    for item in reading:
        try:
            _validate_payload_completeness(item.model_dump(mode="python"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        normalized = _clean_reading(item)
        _store_reading(normalized)
        cleaned.append(normalized)

    target_device_id = cleaned[-1].device_id
    analysis, error = _dispatch_ai_window(target_device_id, _analyze_window_size)

    with _state_lock:
        stored_count = len(_readings)

    return IngestAnalyzeResponse(
        ingest=IngestResponse(
            accepted=True,
            cleaned=cleaned[-1],
            stored_count=stored_count,
            ingest_id=str(uuid4()),
        ),
        analysis=analysis,
        error=error,
    )


@app.get("/readings", response_model=List[TelemetryReading])
# Data retrieval endpoint for dashboards and client UIs.
# Returns latest telemetry from Redis when available, otherwise falls back to in-memory storage.
def readings(
    limit: int = 100,
    device_id: Optional[str] = None,
    _: dict = Depends(_verify_jwt_or_internal),
) -> List[TelemetryReading]:
    """Read telemetry for dashboard use; Redis is source-of-truth when available."""
    if device_id:
        redis_data = _load_readings_from_redis(device_id, limit)
        if redis_data:
            return redis_data

        with _state_lock:
            fallback = [item for item in _readings if item.device_id == device_id]
        return fallback[-limit:]

    return _load_recent_readings(limit)
