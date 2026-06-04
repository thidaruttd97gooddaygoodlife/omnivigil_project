from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

# Incoming create payload (API or event-driven creation path)
class WorkOrderCreate(BaseModel):
    machine_id: str
    issue: str
    priority: str = "medium"
    source_alert_id: Optional[str] = None

# Standard work order response
class WorkOrderResponse(BaseModel):
    work_order_id: int
    machine_id: str
    issue: str
    priority: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Completion payload when technician marks work as done
class CompleteRequest(BaseModel):
    action_taken: str