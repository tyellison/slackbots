import os, time, datetime as dt
from messages import Messages
from threading import Lock
from tabulate import tabulate
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pass_planner_helper import compute_passes


DT_FORMAT = "%Y-%m-%d %H:%M"
daily_update_lock = Lock()
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


##### SLACK API CALLBACKS ##### 
@app.event("app_mention")
def handle_app_mention_events(logger):
    logger.warning(f"{now_strftime()}: {Messages['app_mention']}")

@app.event("message")
def handle_message_events(logger):
    logger.warning(f"{now_strftime}: {Messages['message']}")

@app.command("/daily_update")
def handle_daily_update_command(ack, say, logger):
    ack()

    if daily_update_lock.acquire(blocking=False) == False:
        logger.error(f"{now_strftime()}: {Messages['daily_update_enabled']}")
        return

    logger.warning(f"{now_strftime()}: {Messages['daily_update_disabled']}")

    tgt = dt.datetime(2023, 1, 1, 6, 0, 0)
    while True:
        now = dt.datetime.now()
        tgt = dt.datetime.combine(now.date(), tgt.time())
        td = tgt - now

        if td.days < 0:
            tgt += dt.timedelta(days=1)
            td = tgt - now

        time.sleep(td.total_seconds())
        #weather = get_weather()
        pass_table = get_pass_table()    
        say(pass_table)

@app.command("/pass_info")
def handle_pass_info_command(ack, logger, say):
    ack()
    pass_table = get_pass_table()
    logger.warning(f"{now_strftime()}: {Messages['pass_info_enabled']}")
    say(pass_table)

""" 
@app.command("/weather")
def handle_recur_command(ack, body, say):
"""

def get_pass_table(dt_format=DT_FORMAT):
    passes = compute_passes()
    passes = [pi_obj for pi_obj in passes if pi_obj.max_alt_deg >= 15.0]
    passes = [ 
                [pi.local_start_time.strftime(dt_format), 
                round(pi.max_alt_deg, 0), 
                round(pi.duration.total_seconds(), 0)] 
                for pi in passes 
             ]
    pass_table_headers = ["Start Time (PST)", "Max Elev (deg)", "Duration (sec)"]
    pass_table = tabulate(passes, headers=pass_table_headers, tablefmt="plain", numalign="right", stralign="left")
    return pass_table

def get_weather():
    weather = []
    return weather

def now_strftime(dt_format=DT_FORMAT):
    return dt.datetime.now().strftime(DT_FORMAT)


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
    