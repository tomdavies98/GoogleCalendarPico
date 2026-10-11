# Google Calendar REST client for MicroPython (refresh-token OAuth).

import gc
import time
import socket
import urequests
import config as cfg
import timeutil


def _with_timeout(fn):
    """urequests has no timeout arg on many builds — use socket default."""
    try:
        old = socket.getdefaulttimeout()
    except AttributeError:
        old = None
    try:
        socket.setdefaulttimeout(cfg.HTTP_TIMEOUT_S)
    except AttributeError:
        return fn()
    try:
        return fn()
    finally:
        try:
            socket.setdefaulttimeout(old)
        except Exception:
            pass


class GoogleCalendar:
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{}/events"

    def __init__(self, client_id, client_secret, refresh_token, calendar_id=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.calendar_id = calendar_id or cfg.CALENDAR_ID
        self.access_token = None
        self._expires_at = 0

    def ensure_token(self):
        now = time.time()
        if self.access_token and now < self._expires_at - 60:
            return self.access_token
        return self.refresh_access_token()

    def refresh_access_token(self):
        data = (
            "client_id={}&client_secret={}&refresh_token={}&grant_type=refresh_token"
        ).format(
            _urlencode(self.client_id),
            _urlencode(self.client_secret),
            _urlencode(self.refresh_token),
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        gc.collect()
        resp = _with_timeout(
            lambda: urequests.post(self.TOKEN_URL, data=data, headers=headers)
        )
        try:
            body = resp.json()
        finally:
            resp.close()
        if "access_token" not in body:
            raise RuntimeError("Token refresh failed: {}".format(body))
        self.access_token = body["access_token"]
        expires_in = int(body.get("expires_in", 3600))
        self._expires_at = time.time() + expires_in
        return self.access_token

    def fetch_todays_events(self, max_results=None):
        tmin, tmax = timeutil.local_day_bounds_rfc3339()
        if max_results is None:
            max_results = cfg.MAX_EVENTS
        return self.fetch_events(tmin, tmax, max_results)

    def fetch_week_events(self, week_offset=0, max_results=None):
        tmin, tmax = timeutil.local_week_bounds_rfc3339(week_offset=week_offset)
        if max_results is None:
            max_results = cfg.MAX_EVENTS_WEEK
        return self.fetch_events(tmin, tmax, max_results)

    def fetch_events(self, tmin, tmax, max_results=None):
        if max_results is None:
            max_results = cfg.MAX_EVENTS
        token = self.ensure_token()
        cal = self.calendar_id.replace("@", "%40")
        # Avoid aggressive fields= filtering — some calendars return empty items
        # when the partial response shape is unexpected on MicroPython json.
        url = (
            self.EVENTS_URL.format(cal)
            + "?singleEvents=true&orderBy=startTime"
            + "&maxResults={}&timeMin={}&timeMax={}".format(
                max_results,
                _urlencode(tmin),
                _urlencode(tmax),
            )
        )
        print("gcal", tmin, "..", tmax)
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
        }
        gc.collect()
        resp = _with_timeout(lambda: urequests.get(url, headers=headers))
        try:
            if resp.status_code == 401:
                resp.close()
                token = self.refresh_access_token()
                headers["Authorization"] = "Bearer " + token
                gc.collect()
                resp = _with_timeout(lambda: urequests.get(url, headers=headers))
            status = resp.status_code
            body = resp.json()
        finally:
            resp.close()

        if status >= 400 or "error" in body:
            raise RuntimeError("events.list failed: {}".format(body))

        items = body.get("items") or []
        print("gcal items", len(items))
        events = []
        for it in items:
            if it.get("status") == "cancelled":
                continue
            start = it.get("start") or {}
            end = it.get("end") or {}
            if "date" in start:
                s_epoch, _ = timeutil.parse_rfc3339(start["date"])
                e_epoch, _ = timeutil.parse_rfc3339(end.get("date") or start["date"])
                all_day = True
            else:
                s_epoch, _ = timeutil.parse_rfc3339(start.get("dateTime"))
                e_epoch, _ = timeutil.parse_rfc3339(end.get("dateTime"))
                all_day = False
            if s_epoch is None:
                continue
            events.append(
                {
                    "summary": it.get("summary") or "(No title)",
                    "location": it.get("location") or "",
                    "start_epoch": s_epoch,
                    "end_epoch": e_epoch if e_epoch is not None else s_epoch,
                    "all_day": all_day,
                }
            )
        return events


def _urlencode(s):
    out = []
    for c in str(s):
        o = ord(c)
        if (
            (48 <= o <= 57)
            or (65 <= o <= 90)
            or (97 <= o <= 122)
            or c in "-._~"
        ):
            out.append(c)
        elif c == " ":
            out.append("+")
        else:
            out.append("%{:02X}".format(o))
    return "".join(out)
