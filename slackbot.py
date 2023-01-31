import os, time, json, datetime as dt
from messages import Messages
from requests import get
from threading import Lock
from tabulate import tabulate
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from pass_planner_helper import compute_passes


DT_FORMAT = "%Y-%m-%d %H:%M"
DAILY_UPDATE_MINUTE = 5
DAILY_UPDATE_HOUR = 6
WEATHER_ALERT_BLACKOUT_HOURS = {DAILY_UPDATE_HOUR}
DAILY_WEATHER_ALERTS = []
DAILY_WEATHER_ALERTS_DATA_LOCK = Lock()
DAILY_UPDATE_THREAD_LOCK = Lock()
WEATHER_ALERT_THREAD_LOCK = Lock()
HTTP_TIMEOUT = 90
THREAD_TIMEOUT = HTTP_TIMEOUT * 2
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

    if DAILY_UPDATE_THREAD_LOCK.acquire(blocking=False) == False:
        logger.error(fmt_log_msg('daily_update_enabled'))
        return

    logger.warning(fmt_log_msg('daily_update_disabled'))

    while True:
        now = dt.datetime.now()
        tgt = now.replace(hour=DAILY_UPDATE_HOUR, minute=DAILY_UPDATE_MINUTE, second=0, microsecond=0)
        td = tgt - now

        if td.days < 0:
            tgt += dt.timedelta(days=1)
            td = tgt - now

        time.sleep(td.total_seconds())
        pass_table = get_pass_table() 
        weather_alerts = []

        DAILY_WEATHER_ALERTS_DATA_LOCK.acquire(blocking=True, timeout=THREAD_TIMEOUT)
        weather_alerts = DAILY_WEATHER_ALERTS.copy()
        DAILY_WEATHER_ALERTS_DATA_LOCK.release()

        num_alerts = len(weather_alerts)

        if num_alerts > 0:
            say(f"{num_alerts} {Messages['weather_alerts']}\n\n{pass_table}")   
        
        else:
            say(pass_table)
        
@app.command("/persistent_weather_alerts")
def handle_persistent_weather_alerts_command(ack, logger, say):
    ack()

    if WEATHER_ALERT_THREAD_LOCK.acquire(blocking=False) == False:
        logger.error(fmt_log_msg('persistent_weather_alerts_enabled'))
        return
    
    logger.warning(fmt_log_msg('persistent_weather_alerts_disabled'))

    while True:
        now = dt.datetime.now()
        tgt = now.replace(minute=0, second=0, microsecond=0)
        tgt += dt.timedelta(hours=1)
        td = tgt - now
        time.sleep(td.total_seconds())
        weather_alerts = get_weather_alerts()
        new_alerts = 0

        DAILY_WEATHER_ALERTS_DATA_LOCK.acquire(blocking=True, timeout=THREAD_TIMEOUT)
        if tgt.hour == DAILY_UPDATE_HOUR:
            DAILY_WEATHER_ALERTS.clear()

        for alert in weather_alerts:
            if alert not in DAILY_WEATHER_ALERTS:
                DAILY_WEATHER_ALERTS.append(alert)
                new_alerts += 1

        DAILY_WEATHER_ALERTS_DATA_LOCK.release()

        if new_alerts > 0 and tgt.hour not in WEATHER_ALERT_BLACKOUT_HOURS:
            say(f"{new_alerts} {Messages['weather_alerts']}")

        {logger.warning(fmt_log_msg(alert)) for alert in weather_alerts}

@app.command("/pass_info")
def handle_pass_info_command(ack, logger, say):
    ack()
    pass_table = get_pass_table()
    logger.warning(fmt_log_msg('pass_info'))
    say(pass_table)

@app.command("/weather_alerts")
def handle_weather_alerts_command(ack, logger, say):
    ack()
    alerts = get_weather_alerts()

    num_alerts = len(alerts)
    
    if num_alerts > 0:
        alert_msg = f"{num_alerts} {Messages['weather_alerts']}"
        say(alert_msg)
        logger.warning(fmt_log_msg('new_weather_alerts'))
    
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
    url = f"{Messages['weatherbit_url']}{os.environ.get('WEATHERBIT_TOKEN')}"
    
    try:
        req = get(url, timeout=HTTP_TIMEOUT)
        alerts = json.loads(req.text)["alerts"]
        return alerts
    
    except:
        print(fmt_log_msg('http_error'))
        return []

def fmt_log_msg(msg):
    if msg in Messages:
        msg = f"[{dt.datetime.now().strftime(DT_FORMAT)}]: {Messages[msg]}"
    
    else:
        msg = f"[{dt.datetime.now().strftime(DT_FORMAT)}]: {msg}"
    
    return msg


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()