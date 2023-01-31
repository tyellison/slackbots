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
    """
    Receives any mentions to app '@<app_name>' in channels where app is authorized.

        Parameters:

            logger: Slack API object which prints text to console

        Returns:
    """

    logger.warning(fmt_log_msg('app_mention'))

@app.event("message")
def handle_message_events(logger):
    """
    Receives any messages posted to Slack channel where bot is added.

        Parameters:

            logger: Slack API object which prints text to console

        Returns:

    """

    logger.warning(fmt_log_msg('message'))

@app.command("/daily_update")
def handle_daily_update_command(ack, say, logger):
    """
    Receives '/daily_update' slash command from Slack channel specified in Slack apps. 
    Sends mandatory ack back to callee and blocks any future attempts to send command 
    to app by using WEATHER_ALERT_THREAD_LOCK. Note it is important to block future 
    calls to handle_daily_update_command(...) because having multiple threads running 
    this handler will result in an excess of Weatherbit API calls (we are only alotted 
    50 per day due to using the free subscription plan) and many messages being sent 
    back to the callee.Gets any existing weather alerts from Weatherbit and computes 
    passes for the next 24 hours, puts this info in a formatted string and sends this 
    info back to the channel the callee sent from.


        Parameters:

            ack: Slack API object to send ack back to callee process
            say: Slack API object which allows app to send text back to Slack
            logger: Slack API object which prints text to console

        Returns:
            
    """

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
    """
    Receives '/persistent_weather_alerts' slash command from slack channel specified in 
    Slack apps. Sends mandatory ack back to callee and blocks any future attempts to 
    send command to app by using WEATHER_ALERT_THREAD_LOCK. Note it is important to block
    future calls to handle_persistent_weather_alerts_command(...) because having multiple 
    threads running this handler will result in an excess of Weatherbit API calls (we are 
    only alotted 50 per day due to using the free subscription plan) and many of the same
    message being posted to Slack. Sends hourly requests to Weatherbit API and receives a 
    list of any existing alerts. Parses Weatherbit list and adds any new alerts to a shared 
    program scope list (DAILY_WEATHER_ALERTS). Note that you can not use a set/dictionary 
    or any data structure which guarantees the uniqueness of items with raw alert objects 
    since alert json objects are not hashable. Since DAILY_WEATHER_ALERTS may be accessed 
    by handle_daily_update_command(...) we use DAILY_WEATHER_ALERTS_DATA_LOCK to guarantee 
    atomicity of actions which read and write from and to DAILY_WEATHER_ALERTS. We also 
    include a time offset, DAILY_UPDATE_MINUTE, to allow
    handle_persistent_weather_alerts_command(...) to clear DAILY_WEATHER_ALERTS at the 
    DAILY_UPDATE_HOUR and repopulate it with any new/existing alerts. Note 
    DAILY_WEATHER_ALERTS is cleared at DAILY_UPDATE_HOUR not at midnight so any weather 
    alerts from the previous day are not cleared and posted at 1am to Slack. Also note 
    that no weather alerts are sent to Slack during WEATHER_ALERT_BLACKOUT_HOURS which
    defaults to contain just the DAILY_UPDATE_HOUR; adding more hours will silence 
    messages but not stop the routine from sending and receiving Weatherbit API requests.


        Parameters:

            ack: Slack API object to send ack back to callee process
            say: Slack API object which allows app to send text back to Slack
            logger: Slack API object which prints text to console

        Returns:
            
    """
    
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
    """
    Receives '/pass_info' slash command and sends an ack back to Slack callee. Calls 
    get_pass_table(...) to get a formatted string with pass information for the next 
    24 hours. Logs and sends formatted pass info string to Slack callee.

        Parameters:

            ack: Slack API object to send ack back to callee process
            say: Slack API object which allows app to send text back to Slack
            logger: Slack API object which prints text to console    

        Returns:

    """

    ack()
    pass_table = get_pass_table()
    logger.warning(fmt_log_msg('pass_info'))
    say(pass_table)

@app.command("/weather_alerts")
def handle_weather_alerts_command(ack, logger, say):
    """
    Receives '/weather_alerts' slash command and sends an ack back to Slack callee. Calls 
    get_weather_alerts(...) to get a list of json weather alert objects from Weatherbit. 
    If there are any alert objects then create a formatted string to send to Slack callee 
    and log an update message.

        Parameters:

            ack: Slack API object to send ack back to callee process
            say: Slack API object which allows app to send text back to Slack
            logger: Slack API object which prints text to console    

        Returns:
    """

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
    """
    Computes pass times, max elevation angle, and pass duration. 

        Parameters:

            dt_format (string): optional format specifier string which controls the 
                                time resolution of pass start times.

        Returns: 

            pass_table (string): text formatted as a table with start time, max elevation 
                                 angle, and pass duration for all passes above 15 degrees
                                 for the next 24 hours from the time the command was
                                 received.
    """

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
    """
    Sends formatted requests to Weatherbit API to receive list of json objects which
    contain weather alert information. Requests are sent with a timeout specified by
    HTTP_TIMEOUT. Note that retries are not allowed due to the limited number of API
    calls and my uncertainty around whether or not failed API requests count towards 
    the total number of allowed requests. Note how the API token is stored and kept 
    as an environment variable, this was a security best practice recommended by 
    Slack API documentation and this convention was followed for the Weatherbit API
    token as well.

        Parameters:

        Returns: 

    """

    url = f"{Messages['weatherbit_url']}{os.environ.get('WEATHERBIT_TOKEN')}"
    
    try:
        req = get(url, timeout=HTTP_TIMEOUT)
        alerts = json.loads(req.text)["alerts"]
        return alerts
    
    except:
        print(fmt_log_msg('http_error'))
        return []

def fmt_log_msg(msg):
    """
    Creates a formatted string to be logged to the console the application is run from.
    Note how messages are kept in Message dictionary to keep long strings away from the
    core code - this is a stylistic preference of the author.

        Parameters:

            msg (string): either a key to be passed to Messages dictionary or any other 
                          text to be logged.

        Returns:

            fmt_msg (string): formatted string with date and time stamp and some 
                              extra information contained in the msg argument.
    """

    if msg in Messages:
        fmt_msg = f"[{dt.datetime.now().strftime(DT_FORMAT)}]: {Messages[msg]}"
    
    else:
        fmt_msg = f"[{dt.datetime.now().strftime(DT_FORMAT)}]: {msg}"
    
    return fmt_msg


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()