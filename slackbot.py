import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


@app.event("app_mention")
def handle_app_mention_events(body, say):
    pass

@app.event("message")
def handle_message_events(body, say):
    pass

@app.command("/pass_info")
def handle_pass_info_command(ack, body, say):
    ack()
    say("command acknowledged")
    


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()