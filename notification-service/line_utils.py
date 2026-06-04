from linebot.v3.messaging import FlexMessage, FlexBubble, FlexBox, FlexText, FlexButton, URIAction

def create_machine_alert_message(machine_id, status, error_detail):

    color = "#FF4B4B" if status == "CRITICAL" else "#FFCC00"
    
    flex_content = FlexBubble(
        header=FlexBox(
            layout='vertical',
            background_color=color,
            contents=[
                FlexText(text="MACHINE ALERT", weight='bold', color='#ffffff', size='sm'),
                FlexText(text=machine_id, weight='bold', color='#ffffff', size='xl')
            ]
        ),
        body=FlexBox(
            layout='vertical',
            contents=[
                FlexBox(
                    layout='horizontal',
                    contents=[
                        FlexText(text="Status:", color='#aaaaaa', size='sm', flex=1),
                        FlexText(text=status, color=color, size='sm', flex=3, weight='bold')
                    ]
                ),
                FlexBox(
                    layout='vertical',
                    margin='lg',
                    contents=[
                        FlexText(text="Issue Detail:", color='#aaaaaa', size='sm'),
                        FlexText(text=error_detail, size='md', wrap=True)
                    ]
                )
            ]
        ),
        footer=FlexBox(
            layout='vertical',
            contents=[
                FlexButton(
                    action=URIAction(label="View Dashboard", uri="https://your-dashboard.com"),
                    style='primary',
                    color=color
                )
            ]
        )
    )
    return FlexMessage(alt_text=f"แจ้งเตือนเครื่องจักร {machine_id}", contents=flex_content)