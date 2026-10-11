# Local time helpers for Europe/London (or fixed offset).

import time
import config as cfg

# machine.reset() clears the RP2040 RTC back to ~2021. Persist last NTP.
_RTC_STAMP_PATH = "rtc_stamp.txt"


_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def rtc_is_sane(utc=None):
    """True when the clock looks like a real post-NTP wall time."""
    if utc is None:
        utc = time.time()
    try:
        y = time.gmtime(int(utc))[0]
    except Exception:
        return False
    return 2024 <= y <= 2036


def set_utc_epoch(utc):
    """Set the hardware RTC from a UTC unix epoch (same convention as ntptime)."""
    import machine

    tm = time.gmtime(int(utc))
    # RTC.datetime: (Y, M, D, weekday 1-7 Mon=1, h, m, s, sub)
    machine.RTC().datetime(
        (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0)
    )


def persist_time(utc=None):
    """Save UTC epoch so the next soft-reset can restore labels."""
    if utc is None:
        utc = time.time()
    if not rtc_is_sane(utc):
        return False
    try:
        with open(_RTC_STAMP_PATH, "w") as f:
            f.write(str(int(utc)))
        return True
    except Exception as e:
        print("rtc stamp save failed", e)
        return False


def restore_time():
    """
    If RTC was wiped by reset (~Jan 2021), reload last NTP stamp.
    Stamp may be minutes/hours stale — better than being years wrong.
    """
    if rtc_is_sane():
        return True
    try:
        with open(_RTC_STAMP_PATH, "r") as f:
            utc = int((f.read() or "0").strip() or "0")
    except Exception:
        print("RTC unset (no stamp); year", time.gmtime()[0])
        return False
    if not rtc_is_sane(utc):
        return False
    try:
        set_utc_epoch(utc)
        print("RTC restored", time.gmtime())
        return True
    except Exception as e:
        print("RTC restore failed", e)
        return False


def _mktime(y, mo, d, hh=0, mm=0, ss=0):
    """mktime compatible with MicroPython (8-tuple) and CPython (9-tuple)."""
    t8 = (y, mo, d, hh, mm, ss, 0, 0)
    try:
        return time.mktime(t8)
    except TypeError:
        return time.mktime((y, mo, d, hh, mm, ss, 0, 0, -1))


def _last_sunday(year, month):
    # Day-of-month for last Sunday in month (1-31).
    for day in range(31, 0, -1):
        try:
            t = _mktime(year, month, day)
        except OverflowError:
            continue
        wd = time.localtime(t)[6]  # 0=Mon .. 6=Sun in MicroPython
        if wd == 6:
            return day
    return 31


def uk_offset_minutes(utc_tuple=None):
    """BST: last Sunday March 01:00 UTC → last Sunday October 01:00 UTC."""
    if cfg.TZ_FORCE_OFFSET_MINUTES is not None:
        return cfg.TZ_FORCE_OFFSET_MINUTES

    if utc_tuple is None:
        utc_tuple = time.gmtime()
    y, mo, d, h = utc_tuple[0], utc_tuple[1], utc_tuple[2], utc_tuple[3]

    mar = _last_sunday(y, 3)
    oct_ = _last_sunday(y, 10)

    # Before last Sunday March 01:00 → GMT
    if mo < 3 or (mo == 3 and (d < mar or (d == mar and h < 1))):
        return 0
    # From last Sunday October 01:00 → GMT
    if mo > 10 or (mo == 10 and (d > oct_ or (d == oct_ and h >= 1))):
        return 0
    return 60


def utc_epoch():
    return time.time()


def local_epoch(utc=None):
    if utc is None:
        utc = utc_epoch()
    off = uk_offset_minutes(time.gmtime(utc)) * 60
    return utc + off


def local_tuple(utc=None):
    return time.localtime(local_epoch(utc))


def format_hhmm(minutes_or_tuple):
    if isinstance(minutes_or_tuple, (tuple, list)):
        return "{:02d}:{:02d}".format(minutes_or_tuple[3], minutes_or_tuple[4])
    m = int(minutes_or_tuple) % (24 * 60)
    return "{:02d}:{:02d}".format(m // 60, m % 60)


def format_header_date(lt=None):
    if lt is None:
        lt = local_tuple()
    # MicroPython: tm_wday 0=Mon
    return "{} {} {}".format(_DAYS[lt[6]], lt[2], _MONTHS[lt[1] - 1])


def minutes_since_midnight(lt=None):
    if lt is None:
        lt = local_tuple()
    return lt[3] * 60 + lt[4] + lt[5] / 60.0


def local_midnight_utc(utc=None):
    """UTC epoch of local midnight for the local calendar day containing utc."""
    if utc is None:
        utc = utc_epoch()
    off_sec = uk_offset_minutes(time.gmtime(utc)) * 60
    local_now = utc + off_sec
    local = time.localtime(local_now)
    secs_into_day = local[3] * 3600 + local[4] * 60 + local[5]
    start_local_epoch = local_now - secs_into_day
    return start_local_epoch - off_sec


def local_day_bounds_rfc3339(utc=None, day_offset=0):
    """Return (timeMin, timeMax) RFC3339 covering a local calendar day."""
    start_utc = local_midnight_utc(utc) + day_offset * 86400
    end_utc = start_utc + 86400
    return _rfc3339(start_utc), _rfc3339(end_utc)


def monday_midnight_utc(utc=None):
    """UTC epoch of local Monday 00:00 for the week containing utc."""
    day0 = local_midnight_utc(utc)
    off_sec = uk_offset_minutes(time.gmtime(day0 + 3600)) * 60
    # weekday of that local day (0=Mon)
    wd = time.localtime(day0 + off_sec)[6]
    return day0 - wd * 86400


def local_week_bounds_rfc3339(utc=None, week_offset=0):
    """Mon 00:00 .. next Mon 00:00 local, as RFC3339 UTC strings."""
    start = monday_midnight_utc(utc) + week_offset * 7 * 86400
    end = start + 7 * 86400
    return _rfc3339(start), _rfc3339(end)


def day_offset_from_today(day0_utc):
    """Integer day delta of day0_utc (local midnight UTC) vs today."""
    today0 = local_midnight_utc()
    return int(round((day0_utc - today0) / 86400.0))


def format_day_short(day0_utc):
    """e.g. 'Mon 12 Oct' for a local-midnight UTC epoch."""
    off = uk_offset_minutes(time.gmtime(day0_utc + 3600)) * 60
    lt = time.localtime(day0_utc + off)
    return "{} {} {}".format(_DAYS[lt[6]], lt[2], _MONTHS[lt[1] - 1])


def format_week_label(monday_utc):
    """e.g. '6-12 Oct 26' for the week starting monday_utc."""
    off = uk_offset_minutes(time.gmtime(monday_utc + 3600)) * 60
    a = time.localtime(monday_utc + off)
    b = time.localtime(monday_utc + 6 * 86400 + off)
    yy = a[0] % 100
    if a[1] == b[1]:
        return "{}-{} {} {:02d}".format(a[2], b[2], _MONTHS[a[1] - 1], yy)
    return "{} {}-{} {} {:02d}".format(
        a[2], _MONTHS[a[1] - 1], b[2], _MONTHS[b[1] - 1], yy
    )


def _rfc3339(epoch):
    t = time.gmtime(int(epoch))
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
        t[0], t[1], t[2], t[3], t[4], t[5]
    )


def parse_rfc3339(s):
    """
    Parse RFC3339 to (utc_epoch, all_day).
    Supports ...Z, ...+HH:MM, and date-only YYYY-MM-DD.
    """
    if not s:
        return None, False
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        y = int(s[0:4])
        mo = int(s[5:7])
        d = int(s[8:10])
        # All-day: treat as local midnight
        off = uk_offset_minutes() * 60
        # Approximate UTC for that local midnight
        try:
            utc_mid = _mktime(y, mo, d)
        except Exception:
            utc_mid = 0
        return utc_mid - off, True

    # Normalize timezone
    tz_sign = None
    tz_hh = 0
    tz_mm = 0
    body = s
    if s.endswith("Z") or s.endswith("z"):
        body = s[:-1]
    else:
        # Find +HH:MM or -HH:MM at end
        for i in range(len(s) - 1, 9, -1):
            if s[i] in "+-" and i > 10:
                tz_sign = 1 if s[i] == "+" else -1
                parts = s[i + 1 :].split(":")
                tz_hh = int(parts[0])
                tz_mm = int(parts[1]) if len(parts) > 1 else 0
                body = s[:i]
                break

    # body: YYYY-MM-DDTHH:MM:SS[.fff]
    if "T" in body:
        date, tim = body.split("T", 1)
    else:
        date, tim = body, "00:00:00"
    y = int(date[0:4])
    mo = int(date[5:7])
    d = int(date[8:10])
    tim = tim.split(".")[0]
    bits = tim.split(":")
    hh = int(bits[0]) if len(bits) > 0 else 0
    mm = int(bits[1]) if len(bits) > 1 else 0
    ss = int(bits[2]) if len(bits) > 2 else 0
    try:
        epoch = _mktime(y, mo, d, hh, mm, ss)
    except Exception:
        epoch = 0
    # MicroPython mktime is typically UTC-based on RP2
    if tz_sign is not None:
        epoch -= tz_sign * (tz_hh * 3600 + tz_mm * 60)
    return epoch, False


def format_range_local(start_epoch, end_epoch, all_day=False):
    if all_day:
        return "All day"
    a = time.localtime(start_epoch + uk_offset_minutes(time.gmtime(start_epoch)) * 60)
    b = time.localtime(end_epoch + uk_offset_minutes(time.gmtime(end_epoch)) * 60)
    return "{}-{}".format(format_hhmm(a), format_hhmm(b))
