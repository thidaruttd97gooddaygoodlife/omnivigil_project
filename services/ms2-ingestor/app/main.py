from __future__ import annotations

import json
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Deque, List, Optional
from uuid import uuid4

import httpx
import paho.mqtt.client as mqtt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from pydantic import BaseModel, Field, ValidationError

from app.sensor_standards import evaluate_sensor_value, standards_as_dict

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="MS2 IoT Ingestor", version="0.2.0")
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
    temperature_c: float
    vibration_rms: float
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


class BatchRequest(BaseModel):
    device_id: str
    count: int = Field(ge=1, le=200, default=10)


class QualityRecord(BaseModel):
    device_id: str
    timestamp: datetime
    quality_score: float
    warning_count: int
    critical_count: int
    jump_count: int
    status_by_sensor: dict[str, str]


_ai_engine_url = os.getenv("AI_ENGINE_URL", "").strip()
_mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
_mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
_mqtt_topic = os.getenv("MQTT_TOPIC", "omnivigil/telemetry")
_mqtt_username = os.getenv("MQTT_USERNAME")
_mqtt_password = os.getenv("MQTT_PASSWORD")
_mqtt_qos = int(os.getenv("MQTT_QOS", "1"))

_influx_url = os.getenv("INFLUXDB_URL")
_influx_token = os.getenv("INFLUXDB_TOKEN")
_influx_org = os.getenv("INFLUXDB_ORG")
_influx_bucket = os.getenv("INFLUXDB_BUCKET")
_influx_client: Optional[InfluxDBClient] = None
_write_api = None

_max_readings = int(os.getenv("MAX_IN_MEMORY_READINGS", "5000"))
_max_pending_writes = int(os.getenv("MAX_PENDING_INFLUX_WRITES", "10000"))
_readings: Deque[TelemetryReading] = deque(maxlen=_max_readings)
_pending_writes: Deque[TelemetryReading] = deque(maxlen=_max_pending_writes)
_quality_records: Deque[QualityRecord] = deque(maxlen=_max_readings)
_last_by_device: dict[str, TelemetryReading] = {}
_state_lock = threading.Lock()
_stats: dict[str, object] = {
    "mqtt_messages_total": 0,
    "mqtt_parse_errors_total": 0,
    "influx_write_success_total": 0,
    "influx_write_error_total": 0,
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


def _build_quality_record(cleaned: TelemetryReading, previous: Optional[TelemetryReading]) -> QualityRecord:
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

    penalty = warning_count * 6.0 + critical_count * 20.0 + jump_count * 4.0
    quality_score = max(0.0, min(100.0, 100.0 - penalty))

    return QualityRecord(
        device_id=cleaned.device_id,
        timestamp=cleaned.timestamp,
        quality_score=round(quality_score, 2),
        warning_count=warning_count,
        critical_count=critical_count,
        jump_count=jump_count,
        status_by_sensor=status_by_sensor,
    )


def _clean_reading(reading: TelemetryReading) -> TelemetryReading:
    temp = max(-20.0, min(200.0, reading.temperature_c))
    vib = max(0.0, min(50.0, reading.vibration_rms))
    rpm = None if reading.rpm is None else max(0.0, reading.rpm)
    pressure_bar = None if reading.pressure_bar is None else max(0.0, min(25.0, reading.pressure_bar))
    flow_lpm = None if reading.flow_lpm is None else max(0.0, min(5000.0, reading.flow_lpm))
    current_a = None if reading.current_a is None else max(0.0, min(1200.0, reading.current_a))
    oil_temp_c = None if reading.oil_temp_c is None else max(-20.0, min(220.0, reading.oil_temp_c))
    humidity_pct = None if reading.humidity_pct is None else max(0.0, min(100.0, reading.humidity_pct))
    power_kw = None if reading.power_kw is None else max(0.0, min(2500.0, reading.power_kw))

    return TelemetryReading(
        device_id=reading.device_id,
        machine_type=reading.machine_type,
        line=reading.line,
        zone=reading.zone,
        timestamp=reading.timestamp,
        temperature_c=temp,
        vibration_rms=vib,
        rpm=rpm,
        pressure_bar=pressure_bar,
        flow_lpm=flow_lpm,
        current_a=current_a,
        oil_temp_c=oil_temp_c,
        humidity_pct=humidity_pct,
        power_kw=power_kw,
    )


def _init_influx() -> None:
    global _influx_client, _write_api
    if not (_influx_url and _influx_token and _influx_org and _influx_bucket):
        logger.info("InfluxDB config missing. Skipping InfluxDB writer.")
        return

    _influx_client = InfluxDBClient(url=_influx_url, token=_influx_token, org=_influx_org)
    _write_api = _influx_client.write_api(write_options=SYNCHRONOUS)
    logger.info("InfluxDB writer initialized bucket=%s org=%s", _influx_bucket, _influx_org)


def _write_influx(reading: TelemetryReading, quality: Optional[QualityRecord] = None) -> bool:
    if not _write_api:
        return False

    point = Point("telemetry").tag("device_id", reading.device_id)
    if reading.machine_type:
        point = point.tag("machine_type", reading.machine_type)
    if reading.line:
        point = point.tag("line", reading.line)
    if reading.zone:
        point = point.tag("zone", reading.zone)

    point = (
        point.field("temperature_c", reading.temperature_c)
        .field("vibration_rms", reading.vibration_rms)
        .field("rpm", reading.rpm if reading.rpm is not None else 0.0)
    )

    if reading.pressure_bar is not None:
        point = point.field("pressure_bar", reading.pressure_bar)
    if reading.flow_lpm is not None:
        point = point.field("flow_lpm", reading.flow_lpm)
    if reading.current_a is not None:
        point = point.field("current_a", reading.current_a)
    if reading.oil_temp_c is not None:
        point = point.field("oil_temp_c", reading.oil_temp_c)
    if reading.humidity_pct is not None:
        point = point.field("humidity_pct", reading.humidity_pct)
    if reading.power_kw is not None:
        point = point.field("power_kw", reading.power_kw)

    if quality is not None:
        point = (
            point.field("quality_score", quality.quality_score)
            .field("quality_warning_count", float(quality.warning_count))
            .field("quality_critical_count", float(quality.critical_count))
            .field("quality_jump_count", float(quality.jump_count))
        )

    point = point.time(reading.timestamp, WritePrecision.NS)
    _write_api.write(bucket=_influx_bucket, org=_influx_org, record=point)
    return True


def _store_reading(cleaned: TelemetryReading) -> None:
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


def _call_ai_engine(telemetry: List[TelemetryReading]) -> tuple[Optional[dict], Optional[str]]:
    if not _ai_engine_url:
        return None, "AI_ENGINE_URL is not configured"

    payload = {"telemetry": [item.model_dump(mode="json") for item in telemetry]}
    try:
        response = httpx.post(f"{_ai_engine_url}/analyze", json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json(), None
    except httpx.HTTPError as exc:
        return None, str(exc)


def _on_connect(client, userdata, flags, rc) -> None:
    if rc == 0:
        client.subscribe(_mqtt_topic, qos=_mqtt_qos)
        logger.info("MQTT connected broker=%s:%s topic=%s qos=%s", _mqtt_broker, _mqtt_port, _mqtt_topic, _mqtt_qos)
    else:
        logger.warning("MQTT connect failed: %s", rc)


def _on_disconnect(client, userdata, rc) -> None:
    if rc != 0:
        logger.warning("MQTT disconnected unexpectedly rc=%s", rc)


def _on_message(client, userdata, message) -> None:
    with _state_lock:
        _stats["mqtt_messages_total"] = int(_stats["mqtt_messages_total"]) + 1

    try:
        payload = json.loads(message.payload.decode("utf-8"))
        reading = TelemetryReading(**payload)
        cleaned = _clean_reading(reading)
        _store_reading(cleaned)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        with _state_lock:
            _stats["mqtt_parse_errors_total"] = int(_stats["mqtt_parse_errors_total"]) + 1
            _stats["last_error"] = f"MQTT payload error: {exc}"
        logger.warning("MQTT payload error: %s", exc)
    except Exception as exc:
        with _state_lock:
            _stats["last_error"] = f"MQTT message error: {exc}"
        logger.exception("Unexpected MQTT message error")


def _start_mqtt() -> None:
    try:
        client = mqtt.Client(client_id=f"ms2-ingestor-{uuid4()}")
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        if _mqtt_username and _mqtt_password:
            client.username_pw_set(_mqtt_username, _mqtt_password)
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
def health() -> dict:
    with _state_lock:
        queued = len(_pending_writes)
    return {
        "status": "ok",
        "service": "ms2-ingestor",
        "influx_enabled": bool(_write_api),
        "pending_influx_writes": queued,
        "mqtt_topic": _mqtt_topic,
    }


@app.get("/stats")
def stats() -> dict:
    with _state_lock:
        snapshot = dict(_stats)
        snapshot["in_memory_readings"] = len(_readings)
        snapshot["pending_influx_writes"] = len(_pending_writes)
        snapshot["quality_records"] = len(_quality_records)
    return snapshot


@app.get("/quality/reference")
def quality_reference() -> dict:
    return {
        "version": "1.0",
        "standards": standards_as_dict(),
        "disclaimer": "Thresholds are engineering defaults and must be validated against plant OEM/manual/SOP before production alerting.",
    }


@app.get("/quality/readings", response_model=List[QualityRecord])
def quality_readings(limit: int = 100) -> List[QualityRecord]:
    with _state_lock:
        data = list(_quality_records)[-limit:]
    return data


@app.on_event("startup")
def startup() -> None:
    _init_influx()
    _start_mqtt()


@app.on_event("shutdown")
def shutdown() -> None:
    client = getattr(app.state, "mqtt_client", None)
    if client:
        client.loop_stop()
        client.disconnect()
    if _influx_client:
        _influx_client.close()


@app.post("/ingest", response_model=IngestResponse)
def ingest(reading: TelemetryReading) -> IngestResponse:
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
def ingest_analyze(reading: TelemetryReading) -> IngestAnalyzeResponse:
    cleaned = _clean_reading(reading)
    _store_reading(cleaned)
    analysis, error = _call_ai_engine([cleaned])
    with _state_lock:
        stored_count = len(_readings)

    return IngestAnalyzeResponse(
        ingest=IngestResponse(
            accepted=True,
            cleaned=cleaned,
            stored_count=stored_count,
            ingest_id=str(uuid4()),
        ),
        analysis=analysis,
        error=error,
    )


@app.post("/simulate/batch")
def simulate_batch(request: BatchRequest) -> dict:
    import random

    now = datetime.now(timezone.utc)
    generated = [
        TelemetryReading(
            device_id=request.device_id,
            timestamp=now,
            temperature_c=round(random.uniform(40, 110), 2),
            vibration_rms=round(random.uniform(0.1, 12.0), 3),
            rpm=round(random.uniform(900, 1600), 1),
        )
        for _ in range(request.count)
    ]

    for item in generated:
        _store_reading(_clean_reading(item))

    with _state_lock:
        stored_count = len(_readings)
    return {"count": len(generated), "stored_count": stored_count}


@app.post("/simulate/fail", response_model=IngestAnalyzeResponse)
def simulate_fail(device_id: str = "motor-001") -> IngestAnalyzeResponse:
    critical = TelemetryReading(
        device_id=device_id,
        temperature_c=118.5,
        vibration_rms=10.9,
        rpm=1580.0,
    )
    cleaned = _clean_reading(critical)
    _store_reading(cleaned)
    analysis, error = _call_ai_engine([cleaned])
    with _state_lock:
        stored_count = len(_readings)

    return IngestAnalyzeResponse(
        ingest=IngestResponse(
            accepted=True,
            cleaned=cleaned,
            stored_count=stored_count,
            ingest_id=str(uuid4()),
        ),
        analysis=analysis,
        error=error,
    )


@app.get("/readings", response_model=List[TelemetryReading])
def readings(limit: int = 100) -> List[TelemetryReading]:
    with _state_lock:
        data = list(_readings)[-limit:]
    return data
