from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

import psycopg
import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("ms4-alert")

app = FastAPI(title="MS4 Alert", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MS4 listens to Redis Pub/Sub events from MS3 and saves those events into
# a PostgreSQL audit table. It is not the source of inference results; it only
# records and exposes alert history.

_alert_postgres_url = os.getenv(
    "ALERT_POSTGRES_URL",
    "postgresql://omni:omni_password@localhost:5432/maintenance",
)
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_event_channel = os.getenv("REDIS_EVENT_CHANNEL", "anomaly_detected")

_listener_stop = threading.Event()


class AlertRequest(BaseModel):
    machine_id: str
    risk_level: str
    anomaly_score: float
    event_id: Optional[str] = None
    message: Optional[str] = None
    channels: List[str] = ["line", "toast", "sound"]


class AlertResponse(BaseModel):
    alert_id: str
    status: str
    sent_at: str
    line_message: str
    toast_message: str


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(_alert_postgres_url)


def _init_db() -> None:
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_audit (
                    alert_id TEXT PRIMARY KEY,
                    event_id TEXT,
                    machine_id TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    anomaly_score DOUBLE PRECISION NOT NULL,
                    line_message TEXT NOT NULL,
                    toast_message TEXT NOT NULL,
                    channels_json TEXT NOT NULL,
                    message TEXT,
                    sent_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        conn.commit()


def _persist_alert(payload: AlertRequest) -> AlertResponse:
    alert_id = str(uuid4())
    sent_at = datetime.now(timezone.utc).isoformat()
    line_message = f"LINE: {payload.machine_id} risk {payload.risk_level} score {payload.anomaly_score:.4f}"
    toast_message = f"ALERT: {payload.machine_id} is {payload.risk_level}"

    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO alert_audit (
                    alert_id,
                    event_id,
                    machine_id,
                    risk_level,
                    anomaly_score,
                    line_message,
                    toast_message,
                    channels_json,
                    message,
                    sent_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    alert_id,
                    payload.event_id,
                    payload.machine_id,
                    payload.risk_level,
                    payload.anomaly_score,
                    line_message,
                    toast_message,
                    json.dumps(payload.channels),
                    payload.message,
                    sent_at,
                ),
            )
        conn.commit()

    return AlertResponse(
        alert_id=alert_id,
        status="sent",
        sent_at=sent_at,
        line_message=line_message,
        toast_message=toast_message,
    )


def _listener_loop() -> None:
    # Subscribe to the anomaly event channel from MS3.
    # Each published event means MS3 found a high/critical risk level.
    client = redis.from_url(_redis_url, decode_responses=True)
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(_event_channel)

    logger.info("MS4 event listener started channel=%s", _event_channel)

    try:
        while not _listener_stop.is_set():
            message = pubsub.get_message(timeout=1.0)
            if not message:
                continue

            try:
                data = json.loads(message["data"])
                request = AlertRequest(
                    machine_id=data.get("device_id", "unknown-device"),
                    risk_level=data.get("risk_level", "high"),
                    anomaly_score=float(data.get("anomaly_score", 0.0)),
                    event_id=data.get("event_id"),
                    message="Auto alert from anomaly event",
                )
                _persist_alert(request)
            except Exception:
                logger.exception("Failed to process anomaly event in MS4")
    finally:
        pubsub.close()
        client.close()
        logger.info("MS4 event listener stopped")


@app.on_event("startup")
def startup() -> None:
    _init_db()
    thread = threading.Thread(target=_listener_loop, daemon=True, name="ms4-event-listener")
    thread.start()
    app.state.listener_thread = thread


@app.on_event("shutdown")
def shutdown() -> None:
    _listener_stop.set()
    thread = getattr(app.state, "listener_thread", None)
    if thread and thread.is_alive():
        thread.join(timeout=3.0)


@app.get("/health")
# Health endpoint for alert service liveness checks.
# Reports the configured event channel used to receive anomaly events.
def health() -> dict:
    return {
        "status": "ok",
        "service": "ms4-alert",
        "event_channel": _event_channel,
    }


@app.post("/alerts", response_model=AlertResponse)
# Create/emit an alert directly via HTTP.
# This route exists for compatibility and manual testing of alert persistence.
def create_alert(request: AlertRequest) -> AlertResponse:
    # Keep direct API mode for compatibility and manual tests.
    return _persist_alert(request)


@app.get("/alerts")
# List recent alerts from the audit store.
# Returns stored alert metadata for dashboards, history, and review.
def list_alerts(limit: int = 50) -> dict:
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    alert_id,
                    event_id,
                    machine_id,
                    risk_level,
                    anomaly_score,
                    line_message,
                    toast_message,
                    channels_json,
                    message,
                    sent_at
                FROM alert_audit
                ORDER BY sent_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()

    items = [
        {
            "alert_id": row[0],
            "event_id": row[1],
            "machine_id": row[2],
            "risk_level": row[3],
            "anomaly_score": float(row[4]),
            "line_message": row[5],
            "toast_message": row[6],
            "channels": json.loads(row[7] or "[]"),
            "message": row[8],
            "sent_at": row[9].isoformat() if row[9] else None,
        }
        for row in rows
    ]
    return {"items": items}


@app.get("/alerts/{alert_id}")
# Retrieve a single alert by its unique alert_id.
# Useful for getting full stored details for a specific incident.
def get_alert(alert_id: str) -> dict:
    with _get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    alert_id,
                    event_id,
                    machine_id,
                    risk_level,
                    anomaly_score,
                    line_message,
                    toast_message,
                    channels_json,
                    message,
                    sent_at
                FROM alert_audit
                WHERE alert_id = %s
                """,
                (alert_id,),
            )
            row = cursor.fetchone()

    if not row:
        return {"error": "not_found"}

    return {
        "alert_id": row[0],
        "event_id": row[1],
        "machine_id": row[2],
        "risk_level": row[3],
        "anomaly_score": float(row[4]),
        "line_message": row[5],
        "toast_message": row[6],
        "channels": json.loads(row[7] or "[]"),
        "message": row[8],
        "sent_at": row[9].isoformat() if row[9] else None,
    }
