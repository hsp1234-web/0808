import datetime
try:
    import pytz
except ImportError:
    # If pytz is not installed, we can try to use the built-in zoneinfo (Python 3.9+)
    # This is a fallback to make the script more robust.
    from zoneinfo import ZoneInfo

def get_taipei_time_iso():
    """
    獲取當前的台北時間，並將其格式化為帶有時區偏移的 ISO 8601 字串。
    例如: 2025-09-03T10:00:00+08:00
    """
    try:
        # 優先使用 pytz
        tz = pytz.timezone('Asia/Taipei')
    except NameError:
        # 如果 pytz 不存在，則使用 zoneinfo
        tz = ZoneInfo('Asia/Taipei')

    now_in_tz = datetime.datetime.now(tz)

    # isoformat() 預設會產生像 +08:00 這樣的偏移，這正是我們需要的格式。
    return now_in_tz.isoformat()

if __name__ == "__main__":
    print(get_taipei_time_iso())
