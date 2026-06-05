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
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Import LINE SDK v3 classes
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_structured_logging(service_name: str):
    logger = logging.getLogger(service_name)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "").upper() == "JSON":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
    logger.addHandler(handler)
    logger.propagate = False
    
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root_handler = logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "").upper() == "JSON":
        root_handler.setFormatter(JSONFormatter())
    else:
        root_handler.setFormatter(logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-8s] [root] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
    root.addHandler(root_handler)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    return logger

# Setup Logging
logger = setup_structured_logging("ms4-alert")

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

# LINE Configuration
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN", ""))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET", "dummy_secret"))


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


def send_line_notification(machine_id: str, risk_level: str, detail: str) -> None:
    """Send alert notification via LINE."""
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    channel_secret = os.getenv("LINE_CHANNEL_SECRET")
    if not access_token or not channel_secret:
        logger.warning("LINE credentials not fully configured, skipping LINE notification.")
        return
        
    TARGET_USER_ID = os.getenv("LINE_TARGET_USER_ID")
    if not TARGET_USER_ID or TARGET_USER_ID.strip() == "":
        TARGET_USER_ID = "C82453137b46265b4a33a92826f0d74f6"
    try:
        from app.line_utils import create_machine_alert_message
        flex_msg = create_machine_alert_message(machine_id, risk_level, detail)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=TARGET_USER_ID,
                    messages=[flex_msg]
                )
            )
        logger.info(f"LINE notification sent successfully for machine {machine_id}")
    except Exception as e:
        logger.error(f"Failed to send LINE notification: {e}")


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
                    
                    # Send LINE notification if "line" is in channels
                    channels = payload.get("channels", ["line", "toast", "sound"])
                    if "line" in channels:
                        machine_id = payload.get("machine_id", "Unknown")
                        risk_level = payload.get("risk_level", "UNKNOWN")
                        anomaly_score = payload.get("anomaly_score", 0.0)
                        message = payload.get("message")
                        detail = message or f"Anomaly Score: {anomaly_score}"
                        send_line_notification(machine_id, risk_level, detail)
                    
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

    # Check if "line" is in requested channels
    if "line" in request.channels:
        detail = request.message or f"Anomaly Score: {request.anomaly_score}"
        send_line_notification(request.machine_id, request.risk_level, detail)

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


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    source_type = event.source.type
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if source_type == "group":
            group_id = event.source.group_id
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"Group ID ของกลุ่มนี้คือ: {group_id}")]
                )
            )
        elif source_type == "user":
            user_id = event.source.user_id
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"User ID : {user_id}")]
                )
            )
