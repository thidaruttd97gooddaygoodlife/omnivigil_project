from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

import psycopg
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Database Pool
pool: Optional[ConnectionPool] = None

class WorkOrderRequest(BaseModel):
    machine_id: str
    issue: str
    priority: str = "medium"
    source_alert_id: Optional[str] = None

class WorkOrderResponse(BaseModel):
    work_order_id: str
    status: str
    created_at: str

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
                        priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                        source_alert_id VARCHAR(100),
                        status VARCHAR(40) NOT NULL DEFAULT 'open',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        acknowledged_at TIMESTAMPTZ
                    )
                """)
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
    return {"status": "ok", "service": "ms5-maintenance", "db_connected": pool is not None}

@app.post("/work-orders", response_model=WorkOrderResponse)
def create_work_order(request: WorkOrderRequest) -> WorkOrderResponse:
    work_order_id = str(uuid4())
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO work_orders (work_order_id, machine_id, issue, priority, source_alert_id, status)
                    VALUES (%s, %s, %s, %s, %s, 'open')
                    RETURNING created_at
                    """,
                    (work_order_id, request.machine_id, request.issue, request.priority, request.source_alert_id)
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
def list_work_orders(limit: int = 50) -> dict:
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM work_orders ORDER BY created_at DESC LIMIT %s",
                    (limit,)
                )
                items = cursor.fetchall()
                
                # Convert datetime to string for JSON serialization
                for item in items:
                    item['work_order_id'] = str(item['work_order_id'])
                    item['created_at'] = item['created_at'].isoformat()
                    if item['acknowledged_at']:
                        item['acknowledged_at'] = item['acknowledged_at'].isoformat()
                
                return {"items": items}
    except Exception as e:
        logger.error(f"Failed to list work orders: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/work-orders/{work_order_id}")
def get_work_order(work_order_id: str) -> dict:
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM work_orders WHERE work_order_id = %s",
                    (work_order_id,)
                )
                item = cursor.fetchone()
                if not item:
                    raise HTTPException(status_code=404, detail="Work order not found")
                
                item['work_order_id'] = str(item['work_order_id'])
                item['created_at'] = item['created_at'].isoformat()
                if item['acknowledged_at']:
                    item['acknowledged_at'] = item['acknowledged_at'].isoformat()
                
                return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get work order: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.patch("/work-orders/{work_order_id}/ack")
def ack_work_order(work_order_id: str) -> dict:
    ack_time = datetime.now(timezone.utc)
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE work_orders 
                    SET status = 'acknowledged', acknowledged_at = %s 
                    WHERE work_order_id = %s 
                    RETURNING *
                    """,
                    (ack_time, work_order_id)
                )
                item = cursor.fetchone()
                if not item:
                    raise HTTPException(status_code=404, detail="Work order not found")
                
                conn.commit()
                
                item['work_order_id'] = str(item['work_order_id'])
                item['created_at'] = item['created_at'].isoformat()
                item['acknowledged_at'] = item['acknowledged_at'].isoformat()
                
                return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge work order: {e}")
        raise HTTPException(status_code=500, detail="Database error")

class StatusUpdateRequest(BaseModel):
    status: str

@app.patch("/work-orders/{work_order_id}/status")
def update_work_order_status(work_order_id: str, request: StatusUpdateRequest) -> dict:
    """Generic endpoint to update work order status."""
    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE work_orders 
                    SET status = %s 
                    WHERE work_order_id = %s 
                    RETURNING *
                    """,
                    (request.status, work_order_id)
                )
                item = cursor.fetchone()
                if not item:
                    raise HTTPException(status_code=404, detail="Work order not found")
                
                conn.commit()
                
                item['work_order_id'] = str(item['work_order_id'])
                item['created_at'] = item['created_at'].isoformat()
                if item['acknowledged_at']:
                    item['acknowledged_at'] = item['acknowledged_at'].isoformat()
                
                return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        raise HTTPException(status_code=500, detail="Database error")
