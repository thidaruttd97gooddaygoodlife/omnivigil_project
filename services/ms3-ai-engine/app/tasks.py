"""
MS3 AI Engine — Celery Tasks
============================

Architecture (per-sensor, per-device parallelism):
  main.py (FastAPI server)
    └─ groups incoming telemetry by device_id
    └─ for each device, dispatches ONE Celery task per sensor
    └─ waits for all tasks in parallel, then aggregates scores

  run_inference_sensor  ← the only Celery task
    └─ receives: device_id, sensor_name, list of readings
    └─ resamples ONE column (no string-dtype crash)
    └─ runs Chronos forecast
    └─ returns anomaly score for that sensor

NOTE: ms3-worker runs with --concurrency=1 by default.
  Each task runs strictly one at a time on the worker.
  Increase --concurrency in docker-compose.yml to run multiple
  sensor tasks in true parallel (requires more RAM per worker).
"""

import os
import logging
import json
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime, timezone
import httpx
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Event
from app.sensors import ALL_SENSORS as SENSOR_NAMES, score_sensor_value

try:
    import redis
except ImportError:  # pragma: no cover - dependency is present in the service image
    redis = None

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("ms3-tasks")

# ── Sensor catalogue ────────────────────────────────────────────────────────
# All 9 sensors this system monitors. main.py uses this list to decide which
# sensor tasks to dispatch (only those actually present in the payload).
ALL_SENSORS = SENSOR_NAMES

# ── Per-sensor anomaly thresholds ────────────────────────────────────────────
# score = clamp((predicted_p90 − warn) / range, 0.0, 1.0)
# Tune these based on real operating conditions.
SENSOR_THRESHOLDS: Dict[str, Dict[str, float]] = {}

# ── Chronos model (lazy-loaded once per worker process) ──────────────────────
_pipeline = None
_redis_client = None
_alert_url = os.getenv("ALERT_URL", "http://localhost:8004")
_maintenance_url = os.getenv("MAINTENANCE_URL", "http://localhost:8005")
_machine_service_url = os.getenv("MACHINE_SERVICE_URL", "http://ms6-machine:8006").strip().rstrip("/")
_require_registered_machine = os.getenv("REQUIRE_REGISTERED_MACHINE", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

SEVERITY_HEALTH_POLICY = {
    "low": {"health_drop": 0, "health_cap": 100, "ceiling_drop": 0},
    "medium": {"health_drop": 8, "health_cap": 75, "ceiling_drop": 1},
    "high": {"health_drop": 20, "health_cap": 55, "ceiling_drop": 3},
    "critical": {"health_drop": 40, "health_cap": 25, "ceiling_drop": 5},
}


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.50:
        return "high"
    if score >= 0.30:
        return "medium"
    return "low"


def _machine_is_registered(device_id: str) -> bool:
    if not _require_registered_machine:
        return True

    normalized = device_id.strip()
    if not normalized or not _machine_service_url:
        return False

    try:
        response = httpx.get(f"{_machine_service_url}/machines/{normalized}", timeout=3.0)
    except httpx.HTTPError as exc:
        logger.warning("Machine registry lookup failed for %s: %s", normalized, exc)
        return False

    if response.status_code == 404:
        logger.info("Skipping auto maintenance for unregistered machine %s", normalized)
        return False

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Machine registry returned %s for %s: %s", response.status_code, normalized, exc)
        return False

    return True


def _dispatch_alert(device_id: str, level: str, score: float) -> Optional[str]:
    payload = {
        "machine_id": device_id,
        "risk_level": level,
        "anomaly_score": round(score, 4),
        "message": "Auto alert from AI engine",
        "channels": ["line", "toast", "sound"],
    }
    try:
        response = httpx.post(f"{_alert_url}/alerts", json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json().get("alert_id")
    except httpx.HTTPError:
        return None


def _create_work_order(device_id: str, level: str, alert_id: Optional[str]) -> Optional[str]:
    payload = {
        "machine_id": device_id,
        "issue": f"Investigate {level} anomaly",
        "priority": "high" if level in {"high", "critical"} else "medium",
        "source_alert_id": alert_id,
    }
    try:
        response = httpx.post(f"{_maintenance_url}/work-orders", json=payload, timeout=5.0)
        response.raise_for_status()
        return response.json().get("work_order_id")
    except httpx.HTTPError:
        return None


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
        min(current_health - int(policy["health_drop"]), int(policy["health_cap"])),
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
            logger.info("Machine %s disappeared before health update", device_id)
            return None
        machine_response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to read machine %s before health update: %s", device_id, exc)
        return None

    payload = _health_update_for_risk(level, machine_response.json())
    if not payload:
        return machine_response.json()

    try:
        response = httpx.put(f"{_machine_service_url}/machines/{device_id}", json=payload, timeout=3.0)
        if response.status_code == 404:
            logger.info("Machine %s disappeared before health update", device_id)
            return None
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        logger.warning("Failed to update health for machine %s: %s", device_id, exc)
        return None


def _record_high_risk_event(
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

    db = SessionLocal()
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
        logger.error("Failed to persist MS3 high-risk event from pipeline: %s", exc)
    finally:
        db.close()

    return event_id, alert_id, work_order_id


def _get_redis_client():
    global _redis_client
    if redis is None:
        raise RuntimeError("redis package is not installed")
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
    return _redis_client


def _publish_device_prediction_event(payload: dict) -> str | None:
    stream_name = os.getenv("AI_PREDICT_STREAM", "ms3:predict:events")
    maxlen = int(os.getenv("AI_PREDICT_STREAM_MAXLEN", "1000"))
    try:
        return _get_redis_client().xadd(
            stream_name,
            {
                "payload": json.dumps(payload, separators=(",", ":")),
                "device_id": str(payload.get("device_id", "")),
                "anomaly_score": str(payload.get("anomaly_score", 0.0)),
                "risk_level": str(payload.get("risk_level", "low")),
                "model": str(payload.get("model", "")),
            },
            maxlen=maxlen,
            approximate=True,
        )
    except Exception as exc:
        logger.warning("Failed to publish device prediction event: %s", exc)
        return None


def get_pipeline():
    """Load and cache the Chronos model (one instance per Celery worker process)."""
    global _pipeline
    if _pipeline is None:
        import torch
        from chronos import BaseChronosPipeline

        model_id = os.getenv("CHRONOS_MODEL_ID", "Stalemartyr/chronos-finetuned")
        requested_device = os.getenv("CHRONOS_DEVICE", "auto").strip().lower()
        cuda_available = torch.cuda.is_available()

        if requested_device == "cuda" and not cuda_available:
            logger.warning("CHRONOS_DEVICE=cuda requested but CUDA is unavailable; falling back to CPU.")

        device = "cuda" if cuda_available and requested_device in {"auto", "cuda"} else "cpu"
        logger.info(f"Loading Chronos model '{model_id}' on {device} ...")
        _pipeline = BaseChronosPipeline.from_pretrained(
            model_id, device_map=device
        )
        logger.info("Chronos model ready.")
    return _pipeline


def _score_sensor(predicted_value: float, sensor_name: str) -> float:
    """
    Map a sensor's predicted worst-case value to an anomaly score [0.0, 1.0].
    0.0 = well within normal range.  1.0 = critical anomaly.
    """
    return score_sensor_value(predicted_value, sensor_name)


# ── Celery task ──────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.run_inference_sensor")
def run_inference_sensor(
    device_id: str,
    sensor_name: str,
    records: List[Dict],
) -> Dict:
    """
    Run Chronos ML inference for ONE sensor of ONE device.

    Args:
        device_id:   Machine identifier, e.g. "CNC-001"
        sensor_name: Which sensor column to analyse, e.g. "temperature_c"
        records:     List of telemetry dicts (must include "timestamp" and sensor column)

    Returns:
        {
            "device_id": str,
            "sensor":    str,
            "score":     float,   # 0.0 (normal) → 1.0 (critical anomaly)
            "timestamp": str,     # ISO-8601 UTC
        }
    """
    id_col = "device_id"
    ts_col = "timestamp"
    prediction_length = 24   # forecast steps (e.g. 24 × 10 s = 4 minutes ahead)

    _zero = {
        "device_id": device_id,
        "sensor": sensor_name,
        "score": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        df = pd.DataFrame(records)

        # Guard: sensor column must exist and have at least some data
        if sensor_name not in df.columns or df[sensor_name].isna().all():
            logger.warning(f"[{device_id}/{sensor_name}] Column missing or all-NaN — skipping.")
            return _zero

        # ── 1. Keep ONLY timestamp + this sensor (avoids dtype-str crash on resample) ──
        df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
        df[sensor_name] = pd.to_numeric(df[sensor_name], errors="coerce")
        df_clean = df[[ts_col, sensor_name]].sort_values(ts_col)

        # Fill gaps: forward-fill → back-fill → zero for any remaining NaN
        df_clean[sensor_name] = df_clean[sensor_name].ffill().bfill().fillna(0.0)

        # ── 2. Resample to a fixed 10-second grid ────────────────────────────────
        df_resampled = (
            df_clean.set_index(ts_col)[[sensor_name]]
            .resample("10s")
            .mean()
            .interpolate(method="slinear")
            .reset_index()
        )
        # Chronos requires an id column alongside the time series
        df_resampled[id_col] = device_id

        if len(df_resampled) < 10:
            logger.warning(
                f"[{device_id}/{sensor_name}] Only {len(df_resampled)} rows after resample — "
                "using threshold fallback."
            )
            worst_current = float(df_clean[sensor_name].max())
            return {
                "device_id": device_id,
                "sensor": sensor_name,
                "score": _score_sensor(worst_current, sensor_name),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"[{device_id}/{sensor_name}] Running Chronos on {len(df_resampled)} rows "
            f"(forecast {prediction_length} steps) ..."
        )

        # ── 3. Chronos forecast ───────────────────────────────────────────────────
        try:
            pipeline = get_pipeline()
        except Exception as exc:
            logger.warning(
                f"[{device_id}/{sensor_name}] Chronos unavailable, using threshold fallback: {exc}"
            )
            worst_current = float(df_resampled[sensor_name].max())
            return {
                "device_id": device_id,
                "sensor": sensor_name,
                "score": _score_sensor(worst_current, sensor_name),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        df_pred = pipeline.predict_df(
            df_resampled,
            prediction_length=prediction_length,
            quantile_levels=[0.1, 0.5, 0.9],
            id_column=id_col,
            timestamp_column=ts_col,
            target=[sensor_name],      # single-column target list
        )

        # ── 4. Score: use worst (max) of the 90th-percentile forecast values ──────
        # df_pred columns: id_col, ts_col, "target_name", "0.1", "0.5", "0.9"
        p90_values = df_pred["0.9"].dropna().tolist()
        if not p90_values:
            logger.warning(f"[{device_id}/{sensor_name}] No p90 predictions returned.")
            return _zero

        worst_p90 = float(max(p90_values))
        score = _score_sensor(worst_p90, sensor_name)

        logger.info(
            f"[{device_id}/{sensor_name}] worst_p90={worst_p90:.3f}  score={score:.4f}"
        )
        return {
            "device_id": device_id,
            "sensor": sensor_name,
            "score": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(
            f"[{device_id}/{sensor_name}] Inference failed: {exc}", exc_info=True
        )
        return _zero


@celery_app.task(name="app.tasks.run_device_prediction")
def run_device_prediction(device_id: str, records: List[Dict]) -> Dict:
    """
    Queue entry point for MS3's MS2 polling pipeline.

    Receives one device's recent telemetry readings, runs per-sensor inference,
    aggregates the highest score for the device, and publishes one prediction
    event to the Redis Stream read by /predict/event.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    if not records:
        payload = {
            "device_id": device_id,
            "anomaly_score": 0.0,
            "risk_level": "low",
            "model": "chronos-device-pipeline",
            "per_device": {
                device_id: {
                    "anomaly_score": 0.0,
                    "per_sensor": {},
                }
            },
            "timestamp": timestamp,
        }
        _publish_device_prediction_event(payload)
        return payload

    df_check = pd.DataFrame(records)
    available = [
        sensor
        for sensor in SENSOR_NAMES
        if sensor in df_check.columns and df_check[sensor].notna().any()
    ]

    per_sensor: Dict[str, float] = {}
    for sensor in available:
        result = run_inference_sensor(device_id, sensor, records)
        per_sensor[sensor] = round(float(result.get("score", 0.0)), 4)

    anomaly_score = round(max(per_sensor.values(), default=0.0), 4)
    risk_level = _risk_level(anomaly_score)
    event_id, alert_id, work_order_id = _record_high_risk_event(
        device_id,
        risk_level,
        anomaly_score,
    )
    payload = {
        "device_id": device_id,
        "anomaly_score": anomaly_score,
        "risk_level": risk_level,
        "model": "chronos-device-pipeline",
        "per_device": {
            device_id: {
                "anomaly_score": anomaly_score,
                "per_sensor": per_sensor,
            }
        },
        "event_id": event_id,
        "alert_id": alert_id,
        "work_order_id": work_order_id,
        "timestamp": timestamp,
    }
    stream_id = _publish_device_prediction_event(payload)
    payload["stream_id"] = stream_id
    return payload
