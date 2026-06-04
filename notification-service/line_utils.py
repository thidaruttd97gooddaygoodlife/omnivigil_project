from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction

def create_machine_alert_message(machine_id, status, error_detail):

    color = "#FF4B4B" if status == "CRITICAL" else "#FFCC00"
    
    flex_content = BubbleContainer(
        header=BoxComponent(
            layout='vertical',
            background_color=color,
            contents=[
                TextComponent(text="MACHINE ALERT", weight='bold', color='#ffffff', size='sm'),
                TextComponent(text=machine_id, weight='bold', color='#ffffff', size='xl')
            ]
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                BoxComponent(
                    layout='horizontal',
                    contents=[
                        TextComponent(text="Status:", color='#aaaaaa', size='sm', flex=1),
                        TextComponent(text=status, color=color, size='sm', flex=3, weight='bold')
                    ]
                ),
                BoxComponent(
                    layout='vertical',
                    margin='lg',
                    contents=[
                        TextComponent(text="Issue Detail:", color='#aaaaaa', size='sm'),
                        TextComponent(text=error_detail, size='md', wrap=True)
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout='vertical',
            contents=[
                ButtonComponent(
                    action=URIAction(label="View Dashboard", uri="https://your-dashboard.com"),
                    style='primary',
                    color=color
                )
            ]
        )
    )
    return FlexSendMessage(alt_text=f"แจ้งเตือนเครื่องจักร {machine_id}", contents=flex_content)