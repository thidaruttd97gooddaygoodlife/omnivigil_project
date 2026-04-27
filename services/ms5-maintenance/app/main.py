from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import psycopg
import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ms5-maintenance")

app = FastAPI(title="MS5 Maintenance", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://omni:omni_password@postgres:5432/maintenance")
MACHINE_SERVICE_URL = os.getenv("MACHINE_SERVICE_URL", "http://ms6-machine:8006").strip().rstrip("/")
JWT_SECRET = os.getenv("JWT_SECRET", "omni_dev_secret_change_me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
REQUIRE_REGISTERED_MACHINE = os.getenv("REQUIRE_REGISTERED_MACHINE", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

# Database Pool
pool: Optional[ConnectionPool] = None
bearer_scheme = HTTPBearer(auto_error=False)

ALLOWED_PRIORITIES = {"low", "medium", "high", "urgent"}
ALLOWED_STATUSES = {"open", "in_progress", "acknowledged", "completed", "cancelled"}
ALLOWED_TRANSITIONS = {
    "open": {"in_progress", "acknowledged", "completed", "cancelled"},
    "in_progress": {"acknowledged", "completed", "cancelled"},
    "acknowledged": {"in_progress", "completed", "cancelled"},
    "completed": set(),
    "cancelled": {"open", "in_progress"},
}


def _current_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def _require_admin_or_supervisor(payload: dict = Depends(_current_token_payload)) -> dict:
    if payload.get("role") not in {"admin", "supervisor"}:
        raise HTTPException(status_code=403, detail="Not authorized to manage work orders")
    return payload


class WorkOrderRequest(BaseModel):
    machine_id: str
    issue: str
    description: Optional[str] = None
    priority: str = "medium"
    assigned_to: Optional[str] = None
    estimated_hours: float = Field(default=2.0, ge=0.0, le=10000.0)
    source_alert_id: Optional[str] = None


class WorkOrderResponse(BaseModel):
    work_order_id: str
    status: str
    created_at: str


class StatusUpdateRequest(BaseModel):
    status: str
    action_taken: Optional[str] = None


class WorkOrderMetadataUpdateRequest(BaseModel):
    assigned_to: Optional[str] = None
    estimated_hours: Optional[float] = Field(default=None, ge=0.0, le=10000.0)


class CompleteWorkOrderRequest(BaseModel):
    action_taken: Optional[str] = None


def _normalize_priority(priority: str) -> str:
    normalized = priority.strip().lower()
    if normalized not in ALLOWED_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority '{priority}'. Allowed: {sorted(ALLOWED_PRIORITIES)}",
        )
    return normalized


def _normalize_estimated_hours(value: float) -> float:
    if value < 0:
        raise HTTPException(status_code=400, detail="estimated_hours must be >= 0")
    return float(value)


def _normalize_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}",
        )
    return normalized


def _ensure_machine_exists(machine_id: str) -> None:
    normalized = machine_id.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="machine_id is required")

    if not REQUIRE_REGISTERED_MACHINE:
        return

    if not MACHINE_SERVICE_URL:
        raise HTTPException(status_code=503, detail="Machine registry is not configured")

    try:
        response = httpx.get(f"{MACHINE_SERVICE_URL}/machines/{normalized}", timeout=3.0)
    except httpx.HTTPError as exc:
        logger.warning("Machine registry lookup failed for %s: %s", normalized, exc)
        raise HTTPException(status_code=503, detail="Machine registry is unavailable") from exc

    if response.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail=f"Machine '{normalized}' is not registered in Machine Registry",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Machine registry returned %s for %s", response.status_code, normalized)
        raise HTTPException(status_code=503, detail="Machine registry lookup failed") from exc


def _status_for_health(health_score: int) -> str:
    if health_score >= 80:
        return "normal"
    if health_score >= 50:
        return "warning"
    return "critical"


def _recover_machine_after_completion(machine_id: str) -> None:
    if not machine_id:
        return

    if not MACHINE_SERVICE_URL:
        return

    try:
        response = httpx.get(f"{MACHINE_SERVICE_URL}/machines/{machine_id}", timeout=3.0)
        if response.status_code == 404:
            logger.info("Skipping health recovery for missing machine %s", machine_id)
            return
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Machine health recovery lookup failed for %s: %s", machine_id, exc)
        return

    machine = response.json()
    current_health = int(machine.get("healthScore", 100))
    health_ceiling = int(machine.get("healthCeiling", 100))
    recovered_health = min(health_ceiling, current_health + 60)
    payload = {
        "healthScore": recovered_health,
        "status": _status_for_health(recovered_health),
    }

    try:
        update_response = httpx.put(f"{MACHINE_SERVICE_URL}/machines/{machine_id}", json=payload, timeout=3.0)
        update_response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Machine health recovery update failed for %s: %s", machine_id, exc)


def _get_pool() -> ConnectionPool:
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool is not initialized")
    return pool


def _serialize_work_order(item: dict) -> dict:
    if item.get("work_order_id") is not None:
        item["work_order_id"] = str(item["work_order_id"])

    for dt_key in ("created_at", "acknowledged_at", "accepted_at", "completed_at", "updated_at"):
        if item.get(dt_key):
            item[dt_key] = item[dt_key].isoformat()
    return item


def _get_current_status(work_order_id: str) -> str:
    active_pool = _get_pool()
    with active_pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM work_orders WHERE work_order_id = %s",
                (work_order_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Work order not found")
            return str(row[0])


def _validate_transition(current_status: str, next_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if next_status not in allowed and next_status != current_status:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{next_status}'",
        )


def _update_status(work_order_id: str, next_status: str, action_taken: Optional[str] = None) -> dict:
    current_status = _get_current_status(work_order_id)
    _validate_transition(current_status, next_status)

    active_pool = _get_pool()
    now = datetime.now(timezone.utc)

    if next_status == current_status:
        with active_pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM work_orders WHERE work_order_id = %s",
                    (work_order_id,),
                )
                item = cursor.fetchone()
                if not item:
                    raise HTTPException(status_code=404, detail="Work order not found")
                return _serialize_work_order(item)

    with active_pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            if next_status == "acknowledged":
                cursor.execute(
                    """
                    UPDATE work_orders
                    SET status = %s,
                        acknowledged_at = COALESCE(acknowledged_at, %s),
                        updated_at = %s
                    WHERE work_order_id = %s
                    RETURNING *
                    """,
                    (next_status, now, now, work_order_id),
                )
            elif next_status == "in_progress":
                cursor.execute(
                    """
                    UPDATE work_orders
                    SET status = %s,
                        accepted_at = COALESCE(accepted_at, %s),
                        updated_at = %s
                    WHERE work_order_id = %s
                    RETURNING *
                    """,
                    (next_status, now, now, work_order_id),
                )
            elif next_status == "completed":
                cursor.execute(
                    """
                    UPDATE work_orders
                    SET status = %s,
                        completed_at = COALESCE(completed_at, %s),
                        action_taken = COALESCE(%s, action_taken),
                        updated_at = %s
                    WHERE work_order_id = %s
                    RETURNING *
                    """,
                    (next_status, now, action_taken, now, work_order_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE work_orders
                    SET status = %s,
                        updated_at = %s
                    WHERE work_order_id = %s
                    RETURNING *
                    """,
                    (next_status, now, work_order_id),
                )

            item = cursor.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Work order not found")
            conn.commit()
            return _serialize_work_order(item)


def _init_db() -> None:
    """Initialize the work_orders table if it doesn't exist."""
    try:
        with psycopg.connect(POSTGRES_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS work_orders (
                        id SERIAL PRIMARY KEY,
                        work_order_id UUID UNIQUE NOT NULL,
                        machine_id VARCHAR(100) NOT NULL,
                        issue TEXT NOT NULL,
                        description TEXT,
                        priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                        assigned_to VARCHAR(255),
                        estimated_hours DOUBLE PRECISION NOT NULL DEFAULT 2.0,
                        source_alert_id VARCHAR(100),
                        status VARCHAR(40) NOT NULL DEFAULT 'open',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        acknowledged_at TIMESTAMPTZ,
                        accepted_at TIMESTAMPTZ,
                        completed_at TIMESTAMPTZ,
                        action_taken TEXT,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                # Backward-compatible schema upgrade for existing deployments.
                cursor.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS description TEXT")
                cursor.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255)")
                cursor.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS estimated_hours DOUBLE PRECISION NOT NULL DEFAULT 2.0")
                cursor.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ")
                cursor.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ")
                cursor.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS action_taken TEXT")
                cursor.execute("ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_orders_created_at ON work_orders(created_at DESC)")
                logger.info("Database table 'work_orders' initialized.")
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

@app.on_event("startup")
def startup() -> None:
    global pool
    _init_db()
    pool = ConnectionPool(conninfo=POSTGRES_URL, min_size=1, max_size=10)
    logger.info("Database connection pool initialized.")

@app.on_event("shutdown")
def shutdown() -> None:
    if pool:
        pool.close()
        logger.info("Database connection pool closed.")

@app.get("/health")
def health() -> dict:
    db_connected = False
    if pool:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            db_connected = True
        except Exception as e:
            logger.warning(f"Health DB check failed: {e}")

    return {"status": "ok", "service": "ms5-maintenance", "db_connected": db_connected}

@app.post("/work-orders", response_model=WorkOrderResponse)
def create_work_order(request: WorkOrderRequest) -> WorkOrderResponse:
    active_pool = _get_pool()
    work_order_id = str(uuid4())
    priority = _normalize_priority(request.priority)
    estimated_hours = _normalize_estimated_hours(request.estimated_hours)
    machine_id = request.machine_id.strip()
    _ensure_machine_exists(machine_id)
    
    try:
        with active_pool.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO work_orders (
                        work_order_id, machine_id, issue, description, priority,
                        assigned_to, estimated_hours, source_alert_id, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open')
                    RETURNING created_at
                    """,
                    (
                        work_order_id,
                        machine_id,
                        request.issue,
                        request.description,
                        priority,
                        request.assigned_to,
                        estimated_hours,
                        request.source_alert_id,
                    ),
                )
                res = cursor.fetchone()
                conn.commit()
                
                created_at = res[0].isoformat() if isinstance(res[0], datetime) else str(res[0])
                
                return WorkOrderResponse(
                    work_order_id=work_order_id,
                    status="open",
                    created_at=created_at,
                )
    except Exception as e:
        logger.error(f"Failed to create work order: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/work-orders")
def list_work_orders(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    active_pool = _get_pool()
    try:
        normalized_status = _normalize_status(status) if status else None
        sql = "SELECT * FROM work_orders"
        params: list[object] = []

        if normalized_status:
            sql += " WHERE status = %s"
            params.append(normalized_status)

        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with active_pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(sql, params)
                items = cursor.fetchall()
                for item in items:
                    _serialize_work_order(item)
                return {"items": items}
    except Exception as e:
        logger.error(f"Failed to list work orders: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/work-orders/{work_order_id}")
def get_work_order(work_order_id: str) -> dict:
    active_pool = _get_pool()
    try:
        with active_pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM work_orders WHERE work_order_id = %s",
                    (work_order_id,)
                )
                item = cursor.fetchone()
                if not item:
                    raise HTTPException(status_code=404, detail="Work order not found")
                return _serialize_work_order(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get work order: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.patch("/work-orders/{work_order_id}")
def update_work_order_metadata(
    work_order_id: str,
    request: WorkOrderMetadataUpdateRequest,
    _caller: dict = Depends(_require_admin_or_supervisor),
) -> dict:
    """Update assignment metadata without changing the workflow status."""
    active_pool = _get_pool()
    updates: list[str] = []
    params: list[object] = []

    if "assigned_to" in request.model_fields_set:
        assigned_to = request.assigned_to.strip() if request.assigned_to else None
        updates.append("assigned_to = %s")
        params.append(assigned_to)

    if "estimated_hours" in request.model_fields_set:
        if request.estimated_hours is None:
            raise HTTPException(status_code=400, detail="estimated_hours is required")
        updates.append("estimated_hours = %s")
        params.append(_normalize_estimated_hours(request.estimated_hours))

    if not updates:
        return get_work_order(work_order_id)

    updates.append("updated_at = %s")
    params.append(datetime.now(timezone.utc))
    params.append(work_order_id)

    try:
        with active_pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    UPDATE work_orders
                    SET {", ".join(updates)}
                    WHERE work_order_id = %s
                    RETURNING *
                    """,
                    params,
                )
                item = cursor.fetchone()
                if not item:
                    raise HTTPException(status_code=404, detail="Work order not found")
                conn.commit()
                return _serialize_work_order(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update work order metadata: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.patch("/work-orders/{work_order_id}/ack")
def ack_work_order(
    work_order_id: str,
    _caller: dict = Depends(_require_admin_or_supervisor),
) -> dict:
    try:
        return _update_status(work_order_id, "acknowledged")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge work order: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.patch("/work-orders/{work_order_id}/status")
def update_work_order_status(
    work_order_id: str,
    request: StatusUpdateRequest,
    _caller: dict = Depends(_require_admin_or_supervisor),
) -> dict:
    """Generic endpoint to update work order status."""
    try:
        next_status = _normalize_status(request.status)
        return _update_status(work_order_id, next_status, action_taken=request.action_taken)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.patch("/work-orders/{work_order_id}/accept")
def accept_work_order(
    work_order_id: str,
    _caller: dict = Depends(_require_admin_or_supervisor),
) -> dict:
    try:
        return _update_status(work_order_id, "in_progress")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to accept work order: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.patch("/work-orders/{work_order_id}/complete")
def complete_work_order(
    work_order_id: str,
    request: CompleteWorkOrderRequest,
    _caller: dict = Depends(_require_admin_or_supervisor),
) -> dict:
    try:
        current_status = _get_current_status(work_order_id)
        item = _update_status(work_order_id, "completed", action_taken=request.action_taken)
        if current_status != "completed":
            _recover_machine_after_completion(str(item.get("machine_id", "")))
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete work order: {e}")
        raise HTTPException(status_code=500, detail="Database error")
