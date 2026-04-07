import os
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
from pydantic import BaseModel
from line_utils import create_machine_alert_message
load_dotenv()
app = FastAPI()

class MachineAlert(BaseModel):
    machine_id: str
    status: str
    detail: Optional[str] = "No details provided"

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400)
    return "OK"

@app.post("/notify/machine-failure")
async def notify_machine_failure(alert: MachineAlert): 
    """
    รับข้อมูลจาก AI Service และใช้ Pydantic ตรวจสอบโครงสร้าง
    """
    # ดึงค่าจาก Object ได้โดยตรงเลย ไม่ต้องใช้ .get() แล้ว
    machine_id = alert.machine_id
    status = alert.status
    detail = alert.detail
    
    TARGET_USER_ID = "C82453137b46265b4a33a92826f0d74f6" 
    
    flex_msg = create_machine_alert_message(machine_id, status, detail)
    line_bot_api.push_message(TARGET_USER_ID, flex_msg)
    
    return {"message": "Notification sent", "machine": machine_id}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    source_type = event.source.type
    
    if source_type == "group":
        group_id = event.source.group_id
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"Group ID ของกลุ่มนี้คือ: {group_id}\n TARGET_USER_ID ")
        )
    elif source_type == "user":
        user_id = event.source.user_id
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"User ID : {user_id}")
        )