# Flash cache + boot flags for Pico W RAM strategy.
# Network runs WITHOUT the LCD framebuffer; UI boots from cache on a clean heap.

import json
import time

CACHE_PATH = "events_cache.json"
PENDING_PATH = "fetch_pending.json"
PAINT_PATH = "paint_ui.flag"

_BAD_STATUS_PREFIXES = (
    "Low RAM",
    "Net:",
    "API:",
    "Wi-Fi:",
    "Connecting",
    "Sync deferred",
)


def _is_ok_status(status):
    s = status or ""
    if not s:
        return True
    for p in _BAD_STATUS_PREFIXES:
        if s.startswith(p) or p in s:
            return False
    return True


def save(events, sync_label, week_offset=0, status="", mode="day", day_offset=0):
    if not _is_ok_status(status):
        status = ""
    payload = {
        "t": time.time(),
        "sync": sync_label or "--:--",
        "week": week_offset,
        "mode": mode or "day",
        "day_offset": int(day_offset or 0),
        "status": status,
        "ok": True,
        "events": events or [],
    }
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(payload, f)
        return True
    except Exception as e:
        print("cache save failed:", e)
        return False


def load():
    try:
        with open(CACHE_PATH, "r") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        if not _is_ok_status(payload.get("status")):
            payload["status"] = ""
            payload["ok"] = False
        return payload
    except Exception:
        return None


def clear():
    try:
        import os

        os.remove(CACHE_PATH)
    except Exception:
        pass


def age_s(payload):
    if not payload:
        return 1e9
    try:
        return abs(time.time() - float(payload.get("t") or 0))
    except Exception:
        return 1e9


def is_fresh(payload, max_age_ms):
    if not payload:
        return False
    if payload.get("ok") is False:
        return False
    if not _is_ok_status(payload.get("status")):
        return False
    if (payload.get("sync") or "--:--") == "--:--":
        return False
    # Soft-reset often leaves RTC at ~2021; do not treat that as "fresh forever".
    try:
        import timeutil

        if not timeutil.rtc_is_sane():
            return False
    except Exception:
        pass
    age_ms = age_s(payload) * 1000
    # Unset / skewed RTC historically made age huge; only trust long ages when sane.
    if age_ms > 7 * 24 * 3600 * 1000:
        return True
    return age_ms < max_age_ms


def mark_paint():
    """Next boot must open the UI from cache (skip Wi-Fi). Survives soft-reset."""
    try:
        with open(PAINT_PATH, "w") as f:
            f.write("1")
        return True
    except Exception as e:
        print("paint flag failed:", e)
        return False


def has_paint():
    """True if paint_ui.flag exists (does not clear it)."""
    try:
        with open(PAINT_PATH, "r") as f:
            f.read(1)
        return True
    except Exception:
        return False


def take_paint():
    """True if a post-sync UI boot was requested; clears the flag."""
    try:
        with open(PAINT_PATH, "r") as f:
            f.read()
    except Exception:
        return False
    try:
        import os

        os.remove(PAINT_PATH)
    except Exception:
        pass
    return True


def request_fetch(week_offset=0, mode="day", day_offset=0):
    """Ask the next boot to sync this week (no LCD teardown needed)."""
    # Hand-built JSON — json.dump can need a contiguous alloc that fails when
    # the FB is live and the heap is fragmented (seen: ENOMEM at free≈35KB).
    # Do not gc.collect() here: under fragmentation collect's mark stack
    # (~640B) can MemoryError even when mem_free() looks fine.
    mode_s = "week" if mode == "week" else "day"
    try:
        week_i = int(week_offset)
    except Exception:
        week_i = 0
    try:
        day_i = int(day_offset or 0)
    except Exception:
        day_i = 0
    line = '{"week":%d,"mode":"%s","day_offset":%d}' % (week_i, mode_s, day_i)
    try:
        f = open(PENDING_PATH, "w")
        try:
            f.write(line)
        finally:
            f.close()
        return True
    except Exception as e:
        print("pending save failed:", e)
        return False


def take_pending():
    """Return pending dict {week, mode, day_offset} or None; deletes the flag."""
    try:
        with open(PENDING_PATH, "r") as f:
            payload = json.load(f)
    except Exception:
        return None
    try:
        import os

        os.remove(PENDING_PATH)
    except Exception:
        pass
    if not isinstance(payload, dict):
        return {"week": 0, "mode": "day", "day_offset": 0}
    try:
        week = int(payload.get("week") or 0)
    except Exception:
        week = 0
    mode = payload.get("mode") or "day"
    if mode not in ("day", "week"):
        mode = "day"
    try:
        day_offset = int(payload.get("day_offset") or 0)
    except Exception:
        day_offset = 0
    return {"week": week, "mode": mode, "day_offset": day_offset}
