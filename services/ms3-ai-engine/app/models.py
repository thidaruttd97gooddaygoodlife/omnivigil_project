from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .database import Base

class Event(Base):
    __tablename__ = "events"

    event_id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True)
    risk_level = Column(String)
    anomaly_score = Column(Float)
    alert_id = Column(String, nullable=True)
    work_order_id = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
