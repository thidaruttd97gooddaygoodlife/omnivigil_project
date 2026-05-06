from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

def now_utc():
    return datetime.now(timezone.utc)

class WorkOrder(Base):
    __tablename__ = "work_orders"

    id            = Column(Integer, primary_key=True, index=True)
    machine_id    = Column(String(100), nullable=False, index=True)
    issue         = Column(Text, nullable=False)
    priority      = Column(String(20), default="medium")   # low | medium | high | critical
    status        = Column(String(20), default="pending")  # pending | in_progress | completed
    source_alert_id = Column(String(100), nullable=True)   # Alert ID propagated from MS4
    action_taken  = Column(Text, nullable=True)            # Maintenance action filled by engineer on completion
    created_at    = Column(DateTime(timezone=True), default=now_utc)
    accepted_at   = Column(DateTime(timezone=True), nullable=True)
    completed_at  = Column(DateTime(timezone=True), nullable=True)