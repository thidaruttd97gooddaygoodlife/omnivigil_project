from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="MS5 Maintenance", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WorkOrderRequest(BaseModel):
    machine_id: str
    issue: str
    priority: str = "medium"
    source_alert_id: Optional[str] = None


class WorkOrderResponse(BaseModel):
    work_order_id: str
    status: str
    created_at: str


_work_orders: List[dict] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ms5-maintenance"}


@app.post("/work-orders", response_model=WorkOrderResponse)
def create_work_order(request: WorkOrderRequest) -> WorkOrderResponse:
    work_order_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "work_order_id": work_order_id,
        "machine_id": request.machine_id,
        "issue": request.issue,
        "priority": request.priority,
        "source_alert_id": request.source_alert_id,
        "status": "open",
        "created_at": created_at,
        "acknowledged_at": None,
    }
    _work_orders.append(payload)

    return WorkOrderResponse(
        work_order_id=work_order_id,
        status="open",
        created_at=created_at,
    )


@app.get("/work-orders")
def list_work_orders(limit: int = 50) -> dict:
    return {"items": _work_orders[-limit:]}


@app.get("/work-orders/{work_order_id}")
def get_work_order(work_order_id: str) -> dict:
    for item in _work_orders:
        if item["work_order_id"] == work_order_id:
            return item
    return {"error": "not_found"}


@app.patch("/work-orders/{work_order_id}/ack")
def ack_work_order(work_order_id: str) -> dict:
    for item in _work_orders:
        if item["work_order_id"] == work_order_id:
            item["status"] = "acknowledged"
            item["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
            return item
    return {"error": "not_found"}
