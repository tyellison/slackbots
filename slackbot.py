import os, time
from tabulate import tabulate
from datetime import datetime as dt
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pass_planner_helper import compute_passes

DT_FORMAT = "%Y-%m-%d %H:%M"
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

##### SLACK API CALLBACKS ##### 
@app.event("app_mention")
def handle_app_mention_events(body, say):
    pass

@app.event("message")
def handle_message_events(body, say):
    pass

@app.command("/schedule")
def handle_daily_update_command(ack, body, say):
    pass_table = get_pass_table()
    weather = get_weather()

@app.command("/pass_info")
def handle_pass_info_command(ack, body, say):
    ack()
    pass_table = get_pass_table()
    say(pass_table)

""" 
@app.command("/weather")
def handle_recur_command(ack, body, say):
"""

def get_pass_table():
    passes = compute_passes()
    passes = [pi_obj for pi_obj in passes if pi_obj.max_alt_deg >= 15.0]
    passes = [ \
                [pi.local_start_time.strftime(DT_FORMAT), \
                round(pi.max_alt_deg, 0), \
                round(pi.duration.total_seconds(), 0)] \
                for pi in passes \
             ]
    pass_table_headers = ["Start Time (PST)", "Max Elev (deg)", "Duration (sec)"]
    pass_table = tabulate(passes, headers=pass_table_headers, tablefmt="plain", numalign="right", stralign="left")
    return pass_table

def get_weather():
    weather = []
    return weather

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
    