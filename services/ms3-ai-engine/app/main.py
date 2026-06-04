from __future__ import annotations

import logging
import os
import json
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import anyio
import httpx
import pandas as pd
try:
    import redis
except ImportError:  # pragma: no cover - dependency is present in the service image
    redis = None
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import Event
from app.celery_app import celery_app
from app.sensors import ALL_SENSORS, score_sensor_value

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="MS3 AI Engine (Web Server)", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        logging.info("MS3 event table initialized.")
    except Exception as exc:
        logging.error(f"MS3 database initialization failed: {exc}")
    _auto_start_predict_pipeline()

_alert_url = os.getenv("ALERT_URL", "http://localhost:8004")
_maintenance_url = os.getenv("MAINTENANCE_URL", "http://localhost:8005")
_machine_service_url = os.getenv("MACHINE_SERVICE_URL", "http://ms6-machine:8006").strip().rstrip("/")
_worker_result_timeout_seconds = float(os.getenv("AI_WORKER_RESULT_TIMEOUT_SECONDS", "2.0"))
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_predict_stream_name = os.getenv("AI_PREDICT_STREAM", "ms3:predict:events")
_predict_stream_maxlen = int(os.getenv("AI_PREDICT_STREAM_MAXLEN", "1000"))
_predict_stream_client = None
_ms2_ingestor_url = os.getenv("MS2_INGESTOR_URL", "http://localhost:8002").strip().rstrip("/")
_pipeline_default_limit = int(os.getenv("AI_PIPELINE_MS2_READINGS_LIMIT", "500"))
_pipeline_default_interval_seconds = float(os.getenv("AI_PIPELINE_INTERVAL_SECONDS", "30"))
_pipeline_http_timeout_seconds = float(os.getenv("AI_PIPELINE_HTTP_TIMEOUT_SECONDS", "5.0"))
_pipeline_auto_start = os.getenv("AI_PIPELINE_AUTO_START", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
_pipeline_stop_event = threading.Event()
_pipeline_thread: Optional[threading.Thread] = None
_pipeline_lock = threading.Lock()
_pipeline_status: dict[str, Any] = {
    "running": False,
    "last_run_at": None,
    "last_error": None,
    "last_result": None,
}
_enable_worker_inference = os.getenv("AI_ENABLE_WORKER_INFERENCE", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
_require_registered_machine = os.getenv("REQUIRE_REGISTERED_MACHINE", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


# ── Pydantic models ──────────────────────────────────────────────────────────

class TelemetryReading(BaseModel):
    """One sensor snapshot from one device. Extra fields (e.g. from future sensors) are ignored."""
    model_config = ConfigDict(extra="ignore")

    device_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # All 9 monitored sensors — all Optional so partial payloads are accepted
    temperature_c: Optional[float] = None
    vibration_rms: Optional[float] = None
    rpm:           Optional[float] = None
    pressure_bar:  Optional[float] = None
    flow_lpm:      Optional[float] = None
    current_a:     Optional[float] = None
    oil_temp_c:    Optional[float] = None
    humidity_pct:  Optional[float] = None
    power_kw:      Optional[float] = None


class AnalyzeRequest(BaseModel):
    telemetry: List[TelemetryReading]


class DeviceResult(BaseModel):
    """Per-device inference results, broken down by sensor."""
    anomaly_score: float
    per_sensor: Dict[str, float]


class AnalyzeResponse(BaseModel):
    anomaly_score: float          # worst score across all devices
    risk_level: str
    model: str
    per_device: Optional[Dict[str, DeviceResult]] = None   # detailed breakdown
    event_id: Optional[str] = None
    alert_id: Optional[str] = None
    work_order_id: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _decode_redis_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _get_predict_stream_client():
    global _predict_stream_client
    if redis is None:
        raise RuntimeError("redis package is not installed")
    if _predict_stream_client is None:
        _predict_stream_client = redis.Redis.from_url(_redis_url, decode_responses=True)
    return _predict_stream_client


def _prediction_event_payload(response: AnalyzeResponse) -> dict:
    payload = response.model_dump(mode="json")
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    return payload


def _publish_prediction_event(response: AnalyzeResponse) -> Optional[str]:
    payload = _prediction_event_payload(response)
    per_device = payload.get("per_device") or {}
    device_id = None
    if per_device:
        device_id = max(
            per_device,
            key=lambda key: float(per_device[key].get("anomaly_score", 0.0)),
        )

    fields = {
        "payload": json.dumps(payload, separators=(",", ":")),
        "anomaly_score": str(payload.get("anomaly_score", 0.0)),
        "risk_level": str(payload.get("risk_level", "low")),
        "model": str(payload.get("model", "")),
    }
    if device_id is not None:
        fields["device_id"] = str(device_id)

    try:
        return _get_predict_stream_client().xadd(
            _predict_stream_name,
            fields,
            maxlen=_predict_stream_maxlen,
            approximate=True,
        )
    except Exception as exc:
        logging.warning("Failed to publish MS3 prediction event to Redis Stream: %s", exc)
        return None


def _stream_entry_to_prediction_event(entry_id: Any, fields: Dict[Any, Any]) -> dict:
    stream_id = _decode_redis_value(entry_id)
    decoded_fields = {
        str(_decode_redis_value(key)): _decode_redis_value(value)
        for key, value in fields.items()
    }

    payload_raw = decoded_fields.get("payload")
    if payload_raw:
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    if not payload:
        payload = {
            "anomaly_score": float(decoded_fields.get("anomaly_score", 0.0)),
            "risk_level": decoded_fields.get("risk_level", "low"),
            "model": decoded_fields.get("model", ""),
            "device_id": decoded_fields.get("device_id"),
            "timestamp": decoded_fields.get("timestamp"),
        }

    return {"stream_id": stream_id, **payload}


def _queue_device_prediction(device_id: str, records: List[dict]) -> dict:
    task = celery_app.send_task(
        "app.tasks.run_device_prediction",
        args=[device_id, records],
    )
    return {
        "device_id": device_id,
        "task_id": task.id,
        "records": len(records),
    }


def _run_predict_pipeline_once(limit: int = _pipeline_default_limit) -> dict:
    count = max(1, min(limit, 5000))
    response = httpx.get(
        f"{_ms2_ingestor_url}/readings",
        params={"limit": count},
        timeout=_pipeline_http_timeout_seconds,
    )
    response.raise_for_status()

    readings = response.json()
    device_groups: Dict[str, List[dict]] = defaultdict(list)
    for reading in readings:
        device_id = str(reading.get("device_id", "")).strip()
        if device_id:
            device_groups[device_id].append(reading)

    queued = [
        _queue_device_prediction(device_id, records)
        for device_id, records in device_groups.items()
    ]
    result = {
        "source": f"{_ms2_ingestor_url}/readings",
        "source_readings": len(readings),
        "queued_devices": len(queued),
        "jobs": queued,
    }

    with _pipeline_lock:
        _pipeline_status["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _pipeline_status["last_error"] = None
        _pipeline_status["last_result"] = result
    return result


def _predict_pipeline_loop(limit: int, interval_seconds: float) -> None:
    while not _pipeline_stop_event.is_set():
        try:
            _run_predict_pipeline_once(limit=limit)
        except Exception as exc:
            logging.warning("MS3 predict pipeline run failed: %s", exc)
            with _pipeline_lock:
                _pipeline_status["last_run_at"] = datetime.now(timezone.utc).isoformat()
                _pipeline_status["last_error"] = str(exc)
        _pipeline_stop_event.wait(interval_seconds)

    with _pipeline_lock:
        _pipeline_status["running"] = False


def _start_predict_pipeline(
    limit: int = _pipeline_default_limit,
    interval_seconds: float = _pipeline_default_interval_seconds,
) -> dict:
    global _pipeline_thread
    count = max(1, min(limit, 5000))
    interval = max(1.0, interval_seconds)

    with _pipeline_lock:
        if _pipeline_thread and _pipeline_thread.is_alive():
            return {
                **_pipeline_status,
                "message": "predict pipeline already running",
            }

        _pipeline_stop_event.clear()
        _pipeline_status["running"] = True
        _pipeline_status["last_error"] = None
        _pipeline_thread = threading.Thread(
            target=_predict_pipeline_loop,
            args=(count, interval),
            name="ms3-predict-pipeline",
            daemon=True,
        )
        _pipeline_thread.start()
        return {
            **_pipeline_status,
            "message": "predict pipeline started",
            "limit": count,
            "interval_seconds": interval,
        }


def _auto_start_predict_pipeline() -> dict:
    if not _pipeline_auto_start:
        logging.info("MS3 predict pipeline auto-start disabled.")
        return {
            **_get_predict_pipeline_status(),
            "running": False,
            "message": "predict pipeline auto-start disabled",
        }

    result = _start_predict_pipeline(
        limit=_pipeline_default_limit,
        interval_seconds=_pipeline_default_interval_seconds,
    )
    logging.info("MS3 predict pipeline auto-start result: %s", result.get("message"))
    return result


def _stop_predict_pipeline() -> dict:
    global _pipeline_thread
    _pipeline_stop_event.set()
    thread = _pipeline_thread
    if thread and thread.is_alive():
        thread.join(timeout=2.0)

    with _pipeline_lock:
        _pipeline_status["running"] = bool(_pipeline_thread and _pipeline_thread.is_alive())
        if not _pipeline_status["running"]:
            _pipeline_thread = None
        return {
            **_pipeline_status,
            "message": "predict pipeline stopped",
        }


def _get_predict_pipeline_status() -> dict:
    with _pipeline_lock:
        return dict(_pipeline_status)


def _legacy_score_unused(reading: TelemetryReading) -> float:
    """
    Fast threshold-based score for the CURRENT reading (no ML).
    Used for immediate alerting while ML inference runs asynchronously.
    """
    score = 0.0
    if reading.temperature_c is not None:
        score += max(0.0, (reading.temperature_c - 70.0) / 40.0)
    if reading.vibration_rms is not None:
        score += max(0.0, (reading.vibration_rms - 4.0) / 6.0)
    if reading.rpm is not None and reading.rpm > 1500:
        score += 0.1
    if reading.pressure_bar is not None:
        score += max(0.0, (reading.pressure_bar - 8.0) / 4.0)
    if reading.current_a is not None:
        score += max(0.0, (reading.current_a - 20.0) / 10.0)
    if reading.power_kw is not None:
        score += max(0.0, (reading.power_kw - 15.0) / 5.0)
    # Normalise (6 sensors contributing → divide by 6)
    return max(0.0, min(1.0, score / 10.0))


def _score(reading: TelemetryReading) -> float:
    scores = []
    for sensor_name in ALL_SENSORS:
        value = getattr(reading, sensor_name, None)
        if value is not None:
            scores.append(score_sensor_value(float(value), sensor_name))
    return round(max(scores, default=0.0), 4)


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.50:
        return "high"
    if score >= 0.30:
        return "medium"
    return "low"


def _immediate_result(
    telemetry: List[TelemetryReading],
) -> tuple[Optional[str], float, str, Dict[str, DeviceResult]]:
    scores_by_device: Dict[str, float] = {}

    for reading in telemetry:
        score = _score(reading)
        current = scores_by_device.get(reading.device_id, 0.0)
        scores_by_device[reading.device_id] = max(current, score)

    if not scores_by_device:
        return None, 0.0, "low", {}

    worst_device = max(scores_by_device, key=scores_by_device.get)
    worst_score = scores_by_device[worst_device]
    per_device = {
        device_id: DeviceResult(
            anomaly_score=round(score, 4),
            per_sensor={"threshold": round(score, 4)},
        )
        for device_id, score in scores_by_device.items()
    }
    return worst_device, worst_score, _risk_level(worst_score), per_device


def _dispatch_alert(device_id: str, level: str, score: float) -> Optional[str]:
    payload = {
        "machine_id": device_id,
        "risk_level": level,
        "anomaly_score": round(score, 4),
        "message": "Auto alert from AI engine",
        "channels": ["line", "toast", "sound"],
    }
    try:
        r = httpx.post(f"{_alert_url}/alerts", json=payload, timeout=5.0)
        r.raise_for_status()
        return r.json().get("alert_id")
    except httpx.HTTPError:
        return None


def _create_work_order(
    device_id: str, level: str, alert_id: Optional[str]
) -> Optional[str]:
    payload = {
        "machine_id": device_id,
        "issue": f"Investigate {level} anomaly",
        "priority": "high" if level in {"high", "critical"} else "medium",
        "source_alert_id": alert_id,
    }
    try:
        r = httpx.post(f"{_maintenance_url}/work-orders", json=payload, timeout=5.0)
        r.raise_for_status()
        return r.json().get("work_order_id")
    except httpx.HTTPError:
        return None


# ── Routes ───────────────────────────────────────────────────────────────────

def _machine_is_registered(device_id: str) -> bool:
    if not _require_registered_machine:
        return True

    normalized = device_id.strip()
    if not normalized or not _machine_service_url:
        return False

    try:
        response = httpx.get(f"{_machine_service_url}/machines/{normalized}", timeout=3.0)
    except httpx.HTTPError as exc:
        logging.warning("Machine registry lookup failed for %s: %s", normalized, exc)
        return False

    if response.status_code == 404:
        logging.info("Skipping auto maintenance for unregistered machine %s", normalized)
        return False

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logging.warning("Machine registry returned %s for %s: %s", response.status_code, normalized, exc)
        return False

    return True


SEVERITY_HEALTH_POLICY = {
    "low": {"health_drop": 0, "health_cap": 100, "ceiling_drop": 0},
    "medium": {"health_drop": 8, "health_cap": 75, "ceiling_drop": 1},
    "high": {"health_drop": 20, "health_cap": 55, "ceiling_drop": 3},
    "critical": {"health_drop": 40, "health_cap": 25, "ceiling_drop": 5},
}


def _status_for_health(health_score: int) -> str:
    if health_score >= 80:
        return "normal"
    if health_score >= 50:
        return "warning"
    return "critical"


def _health_update_for_risk(level: str, machine: dict) -> dict:
    policy = SEVERITY_HEALTH_POLICY.get(level, SEVERITY_HEALTH_POLICY["low"])
    current_health = int(machine.get("healthScore", 100))
    current_ceiling = int(machine.get("healthCeiling", 100))
    current_failures = int(machine.get("failureCount", 0))

    if level == "low":
        return {}

    next_health = max(
        5,
        min(
            current_health - int(policy["health_drop"]),
            int(policy["health_cap"]),
        ),
    )
    next_ceiling = max(50, current_ceiling - int(policy["ceiling_drop"]))
    return {
        "status": _status_for_health(next_health),
        "healthScore": next_health,
        "healthCeiling": next_ceiling,
        "failureCount": current_failures + 1,
    }


def _update_machine_health_from_risk(device_id: str, level: str, score: float) -> Optional[dict]:
    if not _machine_service_url:
        return None

    try:
        machine_response = httpx.get(f"{_machine_service_url}/machines/{device_id}", timeout=3.0)
        if machine_response.status_code == 404:
            logging.info("Machine %s disappeared before health update", device_id)
            return None
        machine_response.raise_for_status()
    except httpx.HTTPError as exc:
        logging.warning("Failed to read machine %s before health update: %s", device_id, exc)
        return None

    payload = _health_update_for_risk(level, machine_response.json())
    if not payload:
        return machine_response.json()

    try:
        response = httpx.put(f"{_machine_service_url}/machines/{device_id}", json=payload, timeout=3.0)
        if response.status_code == 404:
            logging.info("Machine %s disappeared before health update", device_id)
            return None
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        logging.warning("Failed to update health for machine %s: %s", device_id, exc)
        return None


def _record_high_risk_event(
    db: Session,
    device_id: Optional[str],
    level: str,
    score: float,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not device_id or level == "low":
        return None, None, None

    if not _machine_is_registered(device_id):
        return None, None, None

    _update_machine_health_from_risk(device_id, level, score)
    alert_id = None
    work_order_id = None
    if level in {"high", "critical"}:
        alert_id = _dispatch_alert(device_id, level, score)
    if level in {"medium", "high", "critical"}:
        work_order_id = _create_work_order(device_id, level, alert_id)
    event_id = None

    try:
        db_event = Event(
            device_id=device_id,
            risk_level=level,
            anomaly_score=score,
            alert_id=alert_id,
            work_order_id=work_order_id,
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        event_id = str(db_event.event_id)
    except Exception as exc:
        db.rollback()
        logging.error(f"Failed to persist MS3 high-risk event: {exc}")

    return event_id, alert_id, work_order_id


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "ms3-ai-engine",
        "mode": "web",
        "worker_inference_enabled": _enable_worker_inference,
        "worker_result_timeout_seconds": _worker_result_timeout_seconds,
    }


@app.get("/predict/event")
def predict_event(limit: int = 50) -> dict:
    count = max(1, min(limit, 500))
    try:
        entries = _get_predict_stream_client().xrevrange(
            _predict_stream_name,
            count=count,
        )
    except Exception as exc:
        logging.warning("Failed to read MS3 prediction events from Redis Stream: %s", exc)
        return {"items": []}

    return {
        "items": [
            _stream_entry_to_prediction_event(entry_id, fields)
            for entry_id, fields in entries
        ]
    }


@app.get("/predict/pipeline/status")
def predict_pipeline_status() -> dict:
    return _get_predict_pipeline_status()


@app.post("/predict/pipeline/run")
def predict_pipeline_run(limit: int = _pipeline_default_limit) -> dict:
    return _run_predict_pipeline_once(limit=limit)


@app.post("/predict/pipeline/start")
def predict_pipeline_start(
    limit: int = _pipeline_default_limit,
    interval_seconds: float = _pipeline_default_interval_seconds,
) -> dict:
    return _start_predict_pipeline(limit=limit, interval_seconds=interval_seconds)


@app.post("/predict/pipeline/stop")
def predict_pipeline_stop() -> dict:
    return _stop_predict_pipeline()


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    if not request.telemetry:
        return AnalyzeResponse(anomaly_score=0.0, risk_level="low", model="simulated")

    immediate_device, score_current, immediate_level, immediate_per_device = _immediate_result(
        request.telemetry
    )

    logging.info(f"Immediate analysis — device={immediate_device} score={score_current:.4f} risk={immediate_level}")

    # ── 1. Group telemetry by device_id ──────────────────────────────────────
    # This ensures ALL devices in the payload are processed,
    # not just the first one.
    device_groups: Dict[str, List[dict]] = defaultdict(list)
    for reading in request.telemetry:
        device_groups[reading.device_id].append(reading.model_dump(mode="json"))

    logging.info(
        f"Received telemetry for {len(device_groups)} device(s): "
        f"{list(device_groups.keys())}"
    )

    # ── 2. Dispatch one Celery task per device × per sensor ──────────────────
    # All tasks are sent to the queue immediately (non-blocking).
    # The worker processes them one at a time (concurrency=1 by default).
    # To run multiple sensors in true parallel, increase --concurrency in
    # docker-compose.yml (requires more RAM per worker).
    pending: List[tuple] = []   # (device_id, sensor_name, celery_async_result)

    if _enable_worker_inference:
        for device_id, records in device_groups.items():
            df_check = pd.DataFrame(records)
            available = [
                s for s in ALL_SENSORS
                if s in df_check.columns and df_check[s].notna().any()
            ]
            logging.info(f"[{device_id}] Dispatching tasks for: {available}")
            for sensor in available:
                try:
                    task = celery_app.send_task(
                        "app.tasks.run_inference_sensor",
                        args=[device_id, sensor, records],
                    )
                    pending.append((device_id, sensor, task))
                except Exception as exc:
                    logging.warning(f"[{device_id}/{sensor}] Task dispatch failed: {exc}")
    logging.info(f"pending tasks dispatched: {len(pending)}")
    if not pending:
        event_id, alert_id, work_order_id = _record_high_risk_event(
            db,
            immediate_device,
            immediate_level,
            score_current,
        )
        response = AnalyzeResponse(
            anomaly_score=round(score_current, 4),
            risk_level=immediate_level,
            model="threshold-fallback",
            per_device=immediate_per_device,
            event_id=event_id,
            alert_id=alert_id,
            work_order_id=work_order_id,
        )
        _publish_prediction_event(response)
        return response

    # ── 3. Collect results without blocking the event loop ───────────────────
    # anyio.to_thread.run_sync runs the blocking .get() calls in a thread pool.
    # Each task has a 120-second timeout. Failed tasks default to score=0.
    def _collect() -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = defaultdict(dict)
        for dev_id, sensor, async_result in pending:
            try:
                res = async_result.get(timeout=_worker_result_timeout_seconds)
                out[dev_id][sensor] = float(res.get("score", 0.0))
            except Exception as exc:
                logging.error(f"[{dev_id}/{sensor}] Task collection failed: {exc}")
                out[dev_id][sensor] = 0.0
        return dict(out)

    device_sensor_scores = await anyio.to_thread.run_sync(_collect)

    # ── 4. Aggregate per device, then overall ────────────────────────────────
    per_device: Dict[str, DeviceResult] = {}
    for dev_id, sensor_scores in device_sensor_scores.items():
        dev_score = max(sensor_scores.values(), default=0.0)
        per_device[dev_id] = DeviceResult(
            anomaly_score=round(dev_score, 4),
            per_sensor={s: round(v, 4) for s, v in sensor_scores.items()},
        )

    for dev_id, immediate_result_item in immediate_per_device.items():
        if dev_id not in per_device:
            per_device[dev_id] = immediate_result_item
            continue

        threshold_score = immediate_result_item.per_sensor["threshold"]
        per_device[dev_id].per_sensor["threshold"] = threshold_score
        per_device[dev_id].anomaly_score = round(
            max(per_device[dev_id].anomaly_score, threshold_score), 4
        )

    overall_score = max(
        (dr.anomaly_score for dr in per_device.values()), default=0.0
    )
    worst_device = max(per_device, key=lambda d: per_device[d].anomaly_score)
    risk_level = _risk_level(overall_score)

    # ── 5. Immediate threshold check & alerting ──────────────────────────────
    score_current = overall_score
    imm_level = risk_level

    event_id = alert_id = work_order_id = None
    if imm_level in {"medium", "high", "critical"}:
        event_id, alert_id, work_order_id = _record_high_risk_event(
            db,
            worst_device,
            imm_level,
            score_current,
        )

    logging.info(
        f"Analysis complete — overall_score={overall_score:.4f}  "
        f"risk={risk_level}  devices={list(per_device.keys())}"
    )

    response = AnalyzeResponse(
        anomaly_score=round(overall_score, 4),
        risk_level=risk_level,
        model="chronos-per-sensor+threshold",
        per_device=per_device,
        event_id=event_id,
        alert_id=alert_id,
        work_order_id=work_order_id,
    )
    _publish_prediction_event(response)
    return response


@app.get("/event")
@app.get("/events")
def events(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    db_events = db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()
    return {
        "items": [
            {
                "event_id": e.event_id,
                "device_id": e.device_id,
                "risk_level": e.risk_level,
                "anomaly_score": e.anomaly_score,
                "alert_id": e.alert_id,
                "work_order_id": e.work_order_id,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in db_events
        ]
    }


@app.post("/models/refresh")
def refresh_model() -> dict:
    return {"status": "queued", "message": "model refresh simulated"}
