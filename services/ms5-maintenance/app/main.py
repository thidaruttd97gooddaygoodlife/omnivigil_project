from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import WorkOrder
from app.schemas import WorkOrderCreate, WorkOrderResponse, CompleteRequest

# สร้าง table ทุกตารางใน DB ตอน startup (ถ้ายังไม่มี)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="MS5 Maintenance System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ms5-maintenance"}


# MS3 เรียก endpoint นี้เมื่อตรวจพบ anomaly
@app.post("/work-orders", response_model=WorkOrderResponse)
def create_work_order(payload: WorkOrderCreate, db: Session = Depends(get_db)):
    order = WorkOrder(
        machine_id=payload.machine_id,
        issue=payload.issue,
        priority=payload.priority,
        source_alert_id=payload.source_alert_id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    # MS3 ต้องการ field ชื่อ work_order_id เพื่อเก็บไว้ใน response
    return WorkOrderResponse(
        work_order_id=order.id,
        machine_id=order.machine_id,
        issue=order.issue,
        priority=order.priority,
        status=order.status,
        created_at=order.created_at,
    )


@app.get("/work-orders")
def list_work_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(WorkOrder)
    if status:
        query = query.filter(WorkOrder.status == status)
    orders = query.order_by(WorkOrder.created_at.desc()).all()
    return {"items": [
        {
            "id": o.id,
            "machine_id": o.machine_id,
            "issue": o.issue,
            "priority": o.priority,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]}


@app.patch("/work-orders/{order_id}/accept")
def accept_work_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found")
    if order.status != "open":
        raise HTTPException(status_code=400, detail=f"Cannot accept order with status '{order.status}'")
    order.status = "in_progress"
    order.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Work order accepted", "id": order_id, "status": "in_progress"}


@app.patch("/work-orders/{order_id}/complete")
def complete_work_order(
    order_id: int,
    payload: CompleteRequest,
    db: Session = Depends(get_db)
):
    order = db.query(WorkOrder).filter(WorkOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Work order not found")
    if order.status not in {"open", "in_progress"}:
        raise HTTPException(status_code=400, detail=f"Cannot complete order with status '{order.status}'")
    order.status = "completed"
    order.action_taken = payload.action_taken
    order.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Work order completed", "id": order_id, "status": "completed"}

