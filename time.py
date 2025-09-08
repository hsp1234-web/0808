import datetime
import pytz

def get_taipei_time():
    """Returns the current time in Taipei (UTC+8) in ISO 8601 format."""
    taipei_tz = pytz.timezone('Asia/Taipei')
    now_utc = datetime.datetime.now(pytz.utc)
    now_taipei = now_utc.astimezone(taipei_tz)
    return now_taipei.isoformat()

if __name__ == "__main__":
    print(get_taipei_time())
