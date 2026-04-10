from __future__ import annotations

import os
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

import pika
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ms4-alert")

app = FastAPI(title="MS4 Alert", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//")


class AlertRequest(BaseModel):
    machine_id: str
    risk_level: str
    anomaly_score: float
    message: Optional[str] = None
    channels: List[str] = ["line", "toast", "sound"]


class AlertResponse(BaseModel):
    alert_id: str
    status: str
    sent_at: str
    line_message: str
    toast_message: str


_alerts: List[dict] = []
_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _rabbitmq_consumer() -> None:
    """Background worker to consume alerts from RabbitMQ."""
    logger.info("RabbitMQ consumer thread started.")
    
    while not _stop_event.is_set():
        try:
            parameters = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            
            channel.queue_declare(queue='alerts', durable=True)
            
            def callback(ch, method, properties, body):
                try:
                    payload = json.loads(body.decode())
                    logger.info(f"Received alert from RabbitMQ: {payload.get('alert_id')}")
                    
                    # Store in memory (similar to HTTP request)
                    _alerts.append(payload)
                    
                    # Acknowledge the message
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Error processing RabbitMQ message: {e}")
                    # Re-queue if processing failed? For now, just ack to avoid loop
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='alerts', on_message_callback=callback)
            
            # Start consuming
            channel.start_consuming()
            
        except Exception as e:
            if not _stop_event.is_set():
                logger.warning(f"RabbitMQ consumer connection lost: {e}. Retrying in 5s...")
                time.sleep(5)
    
    logger.info("RabbitMQ consumer thread stopped.")


@app.on_event("startup")
def startup() -> None:
    global _worker_thread
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_rabbitmq_consumer, daemon=True)
    _worker_thread.start()


@app.on_event("shutdown")
def shutdown() -> None:
    _stop_event.set()
    # Pika connection will eventually time out or we could try to close it if we kept a reference


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok", 
        "service": "ms4-alert", 
        "worker_running": _worker_thread is not None and _worker_thread.is_alive()
    }


@app.post("/alerts", response_model=AlertResponse)
def create_alert(request: AlertRequest) -> AlertResponse:
    alert_id = str(uuid4())
    sent_at = datetime.now(timezone.utc).isoformat()
    line_message = f"LINE: {request.machine_id} risk {request.risk_level} score {request.anomaly_score}"
    toast_message = f"ALERT: {request.machine_id} is {request.risk_level}"

    payload = {
        "alert_id": alert_id,
        "sent_at": sent_at,
        "machine_id": request.machine_id,
        "risk_level": request.risk_level,
        "anomaly_score": request.anomaly_score,
        "channels": request.channels,
        "message": request.message,
    }
    _alerts.append(payload)

    return AlertResponse(
        alert_id=alert_id,
        status="sent",
        sent_at=sent_at,
        line_message=line_message,
        toast_message=toast_message,
    )


@app.get("/alerts")
def list_alerts(limit: int = 50) -> dict:
    return {"items": _alerts[-limit:]}


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    for item in _alerts:
        if item["alert_id"] == alert_id:
            return item
    return {"error": "not_found"}
