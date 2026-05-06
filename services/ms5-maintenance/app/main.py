from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import httpx
import redis
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import WorkOrder
from app.schemas import CompleteRequest, WorkOrderCreate, WorkOrderResponse

app = FastAPI(title="MS5 Maintenance System", version="0.2.0")
logger = logging.getLogger("ms5-maintenance")

_ms1_auth_url = os.getenv("MS1_AUTH_URL", "http://localhost:8001")
_internal_service_key = os.getenv("INTERNAL_SERVICE_KEY", "").strip()
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_event_channel = os.getenv("REDIS_EVENT_CHANNEL", "anomaly_detected")
_auto_create_threshold = float(os.getenv("AUTO_CREATE_THRESHOLD", "0.9"))

_bearer_scheme = HTTPBearer(auto_error=False)
_listener_stop = threading.Event()


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    thread = threading.Thread(target=_event_listener_loop, daemon=True, name="ms5-event-listener")
    thread.start()
    app.state.listener_thread = thread


@app.on_event("shutdown")
def shutdown() -> None:
    _listener_stop.set()
    thread = getattr(app.state, "listener_thread", None)
    if thread and thread.is_alive():
        thread.join(timeout=3.0)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _verify_jwt_or_internal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    x_internal_key: Optional[str] = Header(default=None),
) -> dict:
    # Verification logic for endpoints that require authentication.
    # The service supports two trusted paths:
    # 1) Internal trusted service call using X-Internal-Key.
    # 2) User-facing request with bearer JWT verified by MS1.
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


def _create_work_order_record(payload: WorkOrderCreate, db: Session) -> WorkOrder:
    order = WorkOrder(
        machine_id=payload.machine_id,
        issue=payload.issue,
        priority=payload.priority,
        source_alert_id=payload.source_alert_id,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def _event_listener_loop() -> None:
    # This background thread subscribes to the same Redis event channel used by
    # MS3. When an anomaly event arrives with high enough score, it creates a
    # maintenance work order automatically.
    client = redis.from_url(_redis_url, decode_responses=True)
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(_event_channel)

    try:
        while not _listener_stop.is_set():
            message = pubsub.get_message(timeout=1.0)
            if not message:
                continue

            try:
                event = json.loads(message["data"])
                score = float(event.get("anomaly_score", 0.0))
                if score <= _auto_create_threshold:
                    continue

                device_id = event.get("device_id", "unknown-device")
                risk_level = event.get("risk_level", "high")
                event_id = event.get("event_id")

                payload = WorkOrderCreate(
                    machine_id=device_id,
                    issue=f"Investigate {risk_level} anomaly (score={score:.4f})",
                    priority="critical" if score > 0.95 else "high",
                    source_alert_id=event_id,
                )

                db = SessionLocal()
                try:
                    _create_work_order_record(payload, db)
                finally:
                    db.close()
            except Exception:
                # Keep listener alive even if one event is malformed.
                logger.exception("Failed to process anomaly event in MS5")
                continue
    finally:
        pubsub.close()
        client.close()


@app.get("/health")
# Health endpoint for maintenance service readiness.
# Reports the configured alert event channel and auto-create threshold.
def health() -> dict:
    return {
        "status": "ok",
        "service": "ms5-maintenance",
        "event_channel": _event_channel,
        "auto_create_threshold": _auto_create_threshold,
    }


@app.post("/work-orders", response_model=WorkOrderResponse)
# Create a new maintenance work order from HTTP request payload.
# Protected endpoint used by operators or internal automation.
def create_work_order(
    payload: WorkOrderCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(_verify_jwt_or_internal),
):
    order = _create_work_order_record(payload, db)
    return WorkOrderResponse(
        work_order_id=order.id,
        machine_id=order.machine_id,
        issue=order.issue,
        priority=order.priority,
        status=order.status,
        created_at=order.created_at,
    )


@app.get("/work-orders")
# List open/filtered maintenance work orders.
# Supports optional status filtering, pagination via limit/offset.
def list_work_orders(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: dict = Depends(_verify_jwt_or_internal),
):
    query = db.query(WorkOrder)
    if status_filter:
        query = query.filter(WorkOrder.status == status_filter)

    orders = (
        query
        .order_by(WorkOrder.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "work_order_id": item.id,
                "machine_id": item.machine_id,
                "issue": item.issue,
                "priority": item.priority,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in orders
        ]
    }


@app.get("/work-orders/{order_id}")
# Retrieve a single maintenance work order by ID.
# Returns full order lifecycle fields including acceptance/completion.
def get_work_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(_verify_jwt_or_internal),
):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found")

    return {
        "work_order_id": order.id,
        "machine_id": order.machine_id,
        "issue": order.issue,
        "priority": order.priority,
        "status": order.status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "action_taken": order.action_taken,
    }


@app.patch("/work-orders/{order_id}/accept")
# Accept a pending work order and transition it to in_progress.
# Marks the accepted_at timestamp and enforces state validation.
def accept_work_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(_verify_jwt_or_internal),
):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot accept order with status '{order.status}'")

    order.status = "in_progress"
    order.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Work order accepted", "work_order_id": order_id, "status": "in_progress"}


@app.patch("/work-orders/{order_id}/complete")
# Complete an active work order and record action taken.
# Only pending or in_progress orders may be completed.
def complete_work_order(
    order_id: int,
    payload: CompleteRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(_verify_jwt_or_internal),
):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found")
    if order.status not in {"pending", "in_progress"}:
        raise HTTPException(status_code=400, detail=f"Cannot complete order with status '{order.status}'")

    order.status = "completed"
    order.action_taken = payload.action_taken
    order.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Work order completed", "work_order_id": order_id, "status": "completed"}
