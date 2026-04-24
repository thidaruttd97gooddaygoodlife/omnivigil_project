from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

# สำหรับรับ request จาก MS3 (POST /work-orders)
class WorkOrderCreate(BaseModel):
    machine_id: str
    issue: str
    priority: str = "medium"
    source_alert_id: Optional[str] = None

# สำหรับตอบ response กลับไป
class WorkOrderResponse(BaseModel):
    work_order_id: int
    machine_id: str
    issue: str
    priority: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# สำหรับรับข้อมูลตอนช่างกด "ซ่อมเสร็จ"
class CompleteRequest(BaseModel):
    action_taken: str   # ช่างเขียนว่าทำอะไรไป