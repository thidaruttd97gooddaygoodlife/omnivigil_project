import json
from linebot.v3.messaging import FlexMessage, FlexBubble, FlexBox, FlexText, FlexButton, URIAction

def create_machine_alert_message(machine_id, status, error_detail):
    # Determine alert card color based on risk level
    normalized_status = str(status).upper()
    if normalized_status in ["CRITICAL", "HIGH"]:
        color = "#FF4B4B"
    elif normalized_status == "MEDIUM":
        color = "#F59E0B"
    else:
        color = "#10B981"
        
    sensor = "N/A"
    val_str = "N/A"
    reason = error_detail
    action = "Perform general maintenance diagnostics."
    is_structured = False
    
    try:
        data = json.loads(error_detail)
        sensor = data.get("sensor", "N/A")
        val_str = data.get("value", "N/A")
        reason = data.get("cause", "N/A")
        action = data.get("action", "N/A")
        is_structured = True
    except Exception:
        pass

    if is_structured:
        body_contents = [
            FlexBox(
                layout='horizontal',
                contents=[
                    FlexText(text="Status:", color='#aaaaaa', size='sm', flex=1),
                    FlexText(text=normalized_status, color=color, size='sm', flex=3, weight='bold')
                ]
            ),
            FlexBox(
                layout='horizontal',
                margin='md',
                contents=[
                    FlexText(text="Sensor:", color='#aaaaaa', size='sm', flex=1),
                    FlexText(text=sensor, color='#ffffff', size='sm', flex=3, weight='bold')
                ]
            ),
            FlexBox(
                layout='horizontal',
                margin='md',
                contents=[
                    FlexText(text="Value:", color='#aaaaaa', size='sm', flex=1),
                    FlexText(text=val_str, color='#ffffff', size='sm', flex=3, weight='bold')
                ]
            ),
            FlexBox(
                layout='vertical',
                margin='lg',
                contents=[
                    FlexText(text="Reason:", color='#aaaaaa', size='xs', weight='bold'),
                    FlexText(text=reason, size='sm', color='#fca5a5', wrap=True)
                ]
            ),
            FlexBox(
                layout='vertical',
                margin='lg',
                contents=[
                    FlexText(text="🛠️ Suggested Action:", color='#aaaaaa', size='xs', weight='bold'),
                    FlexText(text=action, size='sm', color='#93c5fd', wrap=True)
                ]
            )
        ]
    else:
        body_contents = [
            FlexBox(
                layout='horizontal',
                contents=[
                    FlexText(text="Status:", color='#aaaaaa', size='sm', flex=1),
                    FlexText(text=normalized_status, color=color, size='sm', flex=3, weight='bold')
                ]
            ),
            FlexBox(
                layout='vertical',
                margin='lg',
                contents=[
                    FlexText(text="Issue Detail:", color='#aaaaaa', size='sm'),
                    FlexText(text=error_detail, size='md', color='#ffffff', wrap=True)
                ]
            )
        ]
    
    flex_content = FlexBubble(
        header=FlexBox(
            layout='vertical',
            background_color=color,
            contents=[
                FlexText(text="⚠ MACHINE ANOMALY DETECTED", weight='bold', color='#ffffff', size='xs'),
                FlexText(text=machine_id, weight='bold', color='#ffffff', size='xl', margin='xs')
            ]
        ),
        body=FlexBox(
            layout='vertical',
            background_color="#1e293b",
            contents=body_contents
        ),
        footer=FlexBox(
            layout='vertical',
            background_color="#0f172a",
            contents=[
                FlexButton(
                    action=URIAction(label="View Live System Map", uri="http://localhost:3000/dashboard/system"),
                    style='primary',
                    color=color
                )
            ]
        )
    )
    return FlexMessage(alt_text=f"แจ้งเตือนความผิดปกติเครื่องจักร {machine_id}", contents=flex_content)
