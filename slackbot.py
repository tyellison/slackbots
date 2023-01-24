import os, time, json, datetime as dt
from messages import Messages
from requests import get
from threading import Lock
from tabulate import tabulate
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pass_planner_helper import compute_passes


DT_FORMAT = "%Y-%m-%d %H:%M"
WEATHERBIT_TOKEN = os.environ.get("WEATHERBIT_TOKEN")
daily_update_lock = Lock()
weather_alert_lock = Lock()
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


@app.event("app_mention")
def handle_app_mention_events(logger):
    logger.warning(fmt_log_msg('app_mention'))

@app.event("message")
def handle_message_events(logger):
    logger.warning(fmt_log_msg('message'))

@app.command("/daily_update")
def handle_daily_update_command(ack, say, logger):
    ack()

    if daily_update_lock.acquire(blocking=False) == False:
        logger.error(fmt_log_msg('daily_update_enabled'))
        return

    logger.warning(fmt_log_msg('daily_update_disabled'))

    while True:
        now = dt.datetime.now()
        tgt = now.replace(hour=6, minute=0, second=0, microsecond=0)
        td = tgt - now

        if td.days < 0:
            tgt += dt.timedelta(days=1)
            td = tgt - now

        time.sleep(td.total_seconds())
        pass_table = get_pass_table() 
        weather_alerts = get_weather_alerts()
        num_alerts = len(weather_alerts)

        if num_alerts > 0:
            say(f"{num_alerts} {Messages['weather_alerts']}\n\n{pass_table}")   

        say(pass_table)
        
@app.command("/persistent_weather_alerts")
def handle_weather_alert_listener_command(ack, logger, say):
    ack()

    if weather_alert_lock.acquire(blocking=False) == False:
        logger.error(fmt_log_msg('persistent_weather_alerts_enabled'))
        return
    
    logger.warning(fmt_log_msg('persistent_weather_alerts_disabled'))

    while True:
        now = dt.datetime.now()
        tgt = now.replace(hour=now.hour, minute=0, second=0, microsecond=0)
        tgt += dt.timedelta(hours=1)
        td = tgt - now
        time.sleep(td.total_seconds())
        weather_alerts = get_weather_alerts()
        num_alerts = len(weather_alerts)

        if num_alerts > 0:
            say(f"{num_alerts} {Messages['weather_alerts']}")

@app.command("/pass_info")
def handle_pass_info_command(ack, logger, say):
    ack()
    pass_table = get_pass_table()
    logger.warning(fmt_log_msg('pass_info_enabled'))
    say(pass_table)

@app.command("/weather_alerts")
def handle_weather_alerts_command(ack, logger, say):
    ack()
    alerts = get_weather_alerts()

    num_alerts = len(alerts)
    
    if num_alerts > 0:
        alert_msg = f"{num_alerts} {Messages['weather_alerts']}"
        say(alert_msg)
    
    else:
        logger.warning(fmt_log_msg('no_weather_alerts'))

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

def get_weather_alerts():
    url = f"{Messages['weatherbit_url']}{WEATHERBIT_TOKEN}"
    
    try:
        req = get(url)
        #alerts = json.loads(req.text)["alerts"]
        return [1]
    
    except:
        print(fmt_log_msg('http_error'))
        return []

def fmt_log_msg(msg_key):
    try:
        msg = f"[{dt.datetime.now().strftime(DT_FORMAT)}]: {Messages[msg_key]}"
    
    except KeyError as e:
        return e
    
    return msg


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()