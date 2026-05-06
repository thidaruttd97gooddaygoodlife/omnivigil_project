from __future__ import annotations

"""
MS3 AI Engine (FastAPI Front Door)
==================================

This API accepts telemetry windows from MS2 and submits per-sensor inference
jobs to Celery workers. The HTTP contract is submit-only:
- POST /analyze returns 202 immediately with a job_id.
- Background monitor threads collect Celery results and dispatch anomaly events
  via Redis Pub/Sub for downstream consumers (MS4/MS5).
"""

import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

import redis
from celery import group
from celery.result import GroupResult
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.tasks import ALL_SENSORS, run_inference_sensor

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="MS3 AI Engine (Web Server)", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_event_channel = os.getenv("REDIS_EVENT_CHANNEL", "anomaly_detected")
_job_key_prefix = os.getenv("MS3_JOB_PREFIX", "ms3:job")

_jobs_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_last_events: List[dict] = []


def _job_key(job_id: str) -> str:
    return f"{_job_key_prefix}:{job_id}"


def _save_job(job_id: str, payload: dict) -> None:
    """Persist job status to Redis, with in-memory fallback on transient errors.

    The service is designed to be resilient: if Redis is temporarily unavailable,
    job status is still kept in local process memory so the status endpoint
    can return something meaningful.
    """
    try:
        client = _get_redis_client()
        try:
            client.set(_job_key(job_id), json.dumps(payload))
            # Retain status for one day so operators can inspect after completion.
            client.expire(_job_key(job_id), 86400)
        finally:
            client.close()
        return
    except Exception:
        pass

    with _jobs_lock:
        _jobs[job_id] = payload


def _load_job(job_id: str) -> Optional[dict]:
    """Read job status from Redis first; fallback to in-memory cache."""
    try:
        client = _get_redis_client()
        try:
            raw = client.get(_job_key(job_id))
        finally:
            client.close()
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass

    with _jobs_lock:
        return _jobs.get(job_id)


class TelemetryReading(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device_id: str
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


class AnalyzeRequest(BaseModel):
    telemetry: List[TelemetryReading]


class AnalyzeAcceptedResponse(BaseModel):
    accepted: bool
    job_id: str
    status: str
    queued_tasks: int


class AnalyzeJobStatusResponse(BaseModel):
    job_id: str
    status: str
    submitted_at: str
    completed_at: Optional[str] = None
    anomaly_score: Optional[float] = None
    risk_level: Optional[str] = None
    per_device: Optional[dict] = None
    error: Optional[str] = None


def _risk_level(score: float) -> str:
    if score >= 0.9:
        return "critical"
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _get_redis_client() -> redis.Redis:
    return redis.from_url(_redis_url, decode_responses=True)


def _publish_event(event: dict) -> None:
    client = _get_redis_client()
    try:
        client.publish(_event_channel, json.dumps(event))
    finally:
        client.close()


def _aggregate_task_results(results: List[dict]) -> tuple[float, dict]:
    per_device_scores: Dict[str, Dict[str, float]] = defaultdict(dict)
    for result in results:
        device_id = result.get("device_id")
        sensor = result.get("sensor")
        score = float(result.get("score", 0.0))
        if device_id and sensor:
            per_device_scores[device_id][sensor] = score

    per_device = {
        device_id: {
            "anomaly_score": round(max(sensor_scores.values(), default=0.0), 4),
            "per_sensor": {key: round(value, 4) for key, value in sensor_scores.items()},
        }
        for device_id, sensor_scores in per_device_scores.items()
    }

    overall = max((item["anomaly_score"] for item in per_device.values()), default=0.0)
    return round(overall, 4), per_device


def _monitor_job(job_id: str, group_result: GroupResult) -> None:
    # Called in a separate thread for each submitted job.
    # It waits for Celery results, aggregates per-sensor scores, updates job
    # status, and publishes an anomaly event only for high/critical findings.
    try:
        results = group_result.get(timeout=300.0, propagate=False)
        anomaly_score, per_device = _aggregate_task_results(results)
        level = _risk_level(anomaly_score)
        completed_at = datetime.now(timezone.utc).isoformat()

        payload = _load_job(job_id)
        if payload is None:
            return
        payload["status"] = "completed"
        payload["completed_at"] = completed_at
        payload["anomaly_score"] = anomaly_score
        payload["risk_level"] = level
        payload["per_device"] = per_device
        _save_job(job_id, payload)

        if level in {"high", "critical"}:
            worst_device = max(per_device, key=lambda key: per_device[key]["anomaly_score"])
            event = {
                "event_id": str(uuid4()),
                "job_id": job_id,
                "device_id": worst_device,
                "anomaly_score": anomaly_score,
                "risk_level": level,
                "timestamp": completed_at,
                "source": "ms3-ai-engine",
            }
            _publish_event(event)
            _last_events.append(event)
    except Exception as exc:
        payload = _load_job(job_id)
        if payload is not None:
            payload["status"] = "failed"
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()
            payload["error"] = str(exc)
            _save_job(job_id, payload)
        logging.exception("MS3 monitor failed for job_id=%s", job_id)


@app.get("/health")
# Health endpoint for the AI engine service.
# Confirms the service is running and indicates the submission-only mode used for async jobs.
def health() -> dict:
    return {
        "status": "ok",
        "service": "ms3-ai-engine",
        "mode": "submit-only",
        "event_channel": _event_channel,
    }


@app.post("/analyze", status_code=202, response_model=AnalyzeAcceptedResponse)
# Submit telemetry to MS3 for async anomaly analysis.
# Accepts a list of readings, creates per-sensor Celery tasks, and returns a tracking job_id.
def analyze(request: AnalyzeRequest) -> AnalyzeAcceptedResponse:
    if not request.telemetry:
        raise HTTPException(status_code=400, detail="telemetry cannot be empty")

    device_groups: Dict[str, List[dict]] = defaultdict(list)
    for reading in request.telemetry:
        device_groups[reading.device_id].append(reading.model_dump(mode="json"))

    signatures = []
    for device_id, records in device_groups.items():
        available = [
            sensor for sensor in ALL_SENSORS if any(item.get(sensor) is not None for item in records)
        ]
        for sensor in available:
            signatures.append(run_inference_sensor.s(device_id, sensor, records))

    if not signatures:
        raise HTTPException(status_code=400, detail="telemetry does not include analyzable sensors")

    # Submit all per-sensor tasks to Celery in one group.
    # The client gets a job_id immediately while processing happens asynchronously.
    group_result = group(signatures).apply_async()
    job_id = group_result.id

    _save_job(
        job_id,
        {
            "job_id": job_id,
            "status": "queued",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "queued_tasks": len(signatures),
            "completed_at": None,
            "anomaly_score": None,
            "risk_level": None,
            "per_device": None,
            "error": None,
        },
    )

    monitor = threading.Thread(target=_monitor_job, args=(job_id, group_result), daemon=True)
    monitor.start()

    return AnalyzeAcceptedResponse(
        accepted=True,
        job_id=job_id,
        status="queued",
        queued_tasks=len(signatures),
    )


@app.get("/analyze/jobs/{job_id}", response_model=AnalyzeJobStatusResponse)
# Retrieve async analysis job status by job_id.
# Returns queued/completed state, risk scores, and any error encountered.
def analyze_job_status(job_id: str) -> AnalyzeJobStatusResponse:
    payload = _load_job(job_id)

    if payload is None:
        raise HTTPException(status_code=404, detail="job_id not found")

    return AnalyzeJobStatusResponse(**payload)


@app.get("/events")
# Returns the most recent service events and state transitions for debugging.
# This endpoint is especially useful for inspecting publish/subscribe activity.
def events(limit: int = 50) -> dict:
    return {"items": _last_events[-limit:]}


@app.post("/models/refresh")
# Simulated model refresh endpoint.
# Enqueues a model refresh action in MS3; currently simulated and not a production reload.
def refresh_model() -> dict:
    return {"status": "queued", "message": "model refresh simulated"}
