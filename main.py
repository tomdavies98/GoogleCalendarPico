# Pico W Google Calendar day/week view — Pico-ResTouch-LCD-3.5
#
# RAM strategy:
# 1) Earliest: reserve 76KB FB, then import display (before JSON/cache modules).
# 2) Paint boot: load cache → UI (FB already held).
# 3) Fetch boot: release FB → Wi-Fi/TLS → cache → mark_paint → soft-reset.
#
# Soft-reset disconnects Thonny (EOF). Close Thonny for normal desk use.

import sys
import gc
import time

sys.path.append("lib")

# Ensure Ctrl-C works for mpremote/Thonny after every boot (never leave it disabled).
try:
    import micropython

    micropython.kbd_intr(3)
except Exception:
    pass

import config as cfg

# Inline dim apply — avoid importing orient.py before the FB slab (extra module
# + flash helpers were enough to leave no contiguous 2KB hole after reserve on
# portrait boots).
try:
    with open("orient.flag", "r") as _of:
        _om = _of.read(1)
except Exception:
    _om = "L"
_ot = cfg.ORIENT_PORTRAIT if _om == "P" else cfg.ORIENT_LANDSCAPE
cfg.WIDTH = _ot["width"]
cfg.HEIGHT = _ot["height"]
cfg.MADCTL = _ot["madctl"]
cfg.TOUCH_FLIP_X = _ot["touch_flip_x"]
cfg.TOUCH_FLIP_Y = _ot["touch_flip_y"]
cfg.TOUCH_SWAP_XY = _ot["touch_swap_xy"]
cfg.TOUCH_CHROME_BAND_PX = _ot["chrome_band"]
cfg.GUTTER_W = _ot["gutter_w"]
cfg.ORIENT = "P" if _om == "P" else "L"
print("ORIENT", cfg.ORIENT, cfg.WIDTH, "x", cfg.HEIGHT, "madctl", hex(cfg.MADCTL))

import fb_slab

gc.collect()
gc.collect()
print("ORIENT pre-FB free", gc.mem_free())
fb_slab.reserve()
print("ORIENT post-FB free", gc.mem_free(), "size", fb_slab.SIZE)

# Display next — fits in the contiguous remainder after the slab.
from display.lcd import create_lcd
from display.touch import Touch
from display.calendar_ui import CalendarUI

print("ORIENT post-import free", gc.mem_free())

import orient

orient.mark_boot()

import event_cache
import timeutil

_UI_MODS = (create_lcd, Touch, CalendarUI)


def _demo_events():
    utc = time.time()
    monday = timeutil.monday_midnight_utc(utc)
    today0 = timeutil.local_midnight_utc(utc)
    return [
        {
            "summary": "Standup",
            "location": "Meet",
            "start_epoch": today0 + 9 * 3600,
            "end_epoch": today0 + 9 * 3600 + 15 * 60,
            "all_day": False,
        },
        {
            "summary": "Design review",
            "location": "Room B",
            "start_epoch": today0 + 11 * 3600,
            "end_epoch": today0 + 12 * 3600,
            "all_day": False,
        },
        {
            "summary": "Lunch",
            "location": "",
            "start_epoch": today0 + 12 * 3600 + 30 * 60,
            "end_epoch": today0 + 13 * 3600 + 30 * 60,
            "all_day": False,
        },
        {
            "summary": "Team holiday",
            "location": "",
            "start_epoch": today0,
            "end_epoch": today0 + 24 * 3600,
            "all_day": True,
        },
        {
            "summary": "Planning",
            "location": "",
            "start_epoch": monday + 10 * 3600,
            "end_epoch": monday + 11 * 3600,
            "all_day": False,
        },
        {
            "summary": "1:1",
            "location": "",
            "start_epoch": monday + 2 * 86400 + 15 * 3600,
            "end_epoch": monday + 2 * 86400 + 15 * 3600 + 30 * 60,
            "all_day": False,
        },
    ]


def _load_secrets():
    try:
        import secrets as sec
    except ImportError:
        return None
    return sec


def _short_err(err, prefix="Err"):
    msg = "{}: {}".format(prefix, err)
    if len(msg) > 28:
        msg = msg[:28]
    return msg


def _normalize_view(mode, week_offset, day_offset, events, prefer_week=False):
    """
    Keep desk boot usable. Sticky week/-N from failed nav left the UI on an
    empty week with ~18KB free and felt frozen.
    """
    if mode not in ("day", "week"):
        mode = "day"
    try:
        week_offset = int(week_offset)
    except Exception:
        week_offset = 0
    try:
        day_offset = int(day_offset)
    except Exception:
        day_offset = 0
    if abs(week_offset) > 26:
        print("clamp week_offset", week_offset, "-> 0")
        week_offset = 0
    n_events = len(events or [])
    # Only keep week view when explicitly requested (pending/paint after nav)
    # or when we actually have events for that week.
    if mode == "week" and not prefer_week and n_events == 0:
        print("normalize empty week -> day")
        mode = "day"
        week_offset = 0
        day_offset = 0
    return mode, week_offset, day_offset


def _soft_reset(reason="sync"):
    print("=== rebooting to UI ({}) ===".format(reason))
    print("(Thonny EOF is normal — close Thonny for desk use)")
    time.sleep_ms(150)
    import machine

    machine.reset()


def _fetch_to_cache(sec, week_offset=0, mode="day", day_offset=0):
    import wifiutil

    # TLS needs the slab back; display modules can stay imported.
    try:
        fb_slab.release()
        gc.collect()
        gc.collect()
    except Exception:
        pass
    print("Fetch week", week_offset, "mode", mode, "free", gc.mem_free())
    wifiutil.connect(
        getattr(sec, "WIFI_SSID", None) or getattr(sec, "ssid", None),
        getattr(sec, "WIFI_PASSWORD", None) or getattr(sec, "password", None),
    )
    wifiutil.sync_ntp()
    gc.collect()
    print("free after wifi", gc.mem_free())

    from gcal import GoogleCalendar

    gcal = GoogleCalendar(
        sec.GOOGLE_CLIENT_ID,
        sec.GOOGLE_CLIENT_SECRET,
        sec.GOOGLE_REFRESH_TOKEN,
        getattr(sec, "GOOGLE_CALENDAR_ID", cfg.CALENDAR_ID),
    )
    gc.collect()
    events = gcal.fetch_week_events(week_offset=week_offset)
    gcal = None
    gc.collect()
    sync_label = timeutil.format_hhmm(timeutil.local_tuple())
    event_cache.save(
        events, sync_label, week_offset, "", mode=mode, day_offset=day_offset
    )
    print("Fetched", len(events), "events sync", sync_label)
    return events, sync_label


def _ui_show_error(ui, err, prefix="Err"):
    print("ERR", prefix, err)
    try:
        if gc.mem_free() > 24000:
            sys.print_exception(err)
    except Exception:
        pass
    if ui is None:
        return
    try:
        ui.report_error(err, prefix)
        # Never force a redraw here — FB is live and heap is often too tight.
    except Exception as e2:
        print("ui error display failed", e2)


def _schedule_fetch_and_reset(week, mode, day_off, release_fb=None):
    """
    Queue week fetch and hard-reset.

    release_fb: optional callable that drops LCD/FB refs first. Required under
    fragmented heaps — with the 76800 FB live, even a 640-byte alloc can fail
    despite mem_free() reporting tens of KB.
    """
    try:
        if release_fb is not None:
            try:
                release_fb()
            except Exception as e:
                print("SYNC release err", e)
            gc.collect()
            gc.collect()
        free = gc.mem_free()
        print("SYNC begin", week, mode, free)
        ok = event_cache.request_fetch(week, mode, day_off)
        if not ok:
            gc.collect()
            ok = event_cache.request_fetch(week, mode, day_off)
        if not ok:
            print("SYNC queue failed")
            return False
        print("SYNC ok reset", week)
        _soft_reset("week {}".format(week))
        return True
    except MemoryError as e:
        print("SYNC MemoryError", e, "free", gc.mem_free())
        return False
    except Exception as e:
        print("SYNC err", e)
        return False


def _run_ui(
    events,
    status,
    sync_label,
    week_offset,
    sec,
    mode="day",
    day_offset=0,
    ui_mods=None,
):
    # Close Thonny before sync reboots — its reconnect Ctrl-C aborts LCD import.
    create_lcd_fn, TouchCls, CalendarUICls = ui_mods or _UI_MODS
    if fb_slab.get() is None:
        # Fetch path released the slab; paint boots keep the early reserve.
        gc.collect()
        gc.collect()
        if not fb_slab.ensure():
            raise MemoryError("FB re-reserve failed")

    print(
        "UI bring-up free",
        gc.mem_free(),
        "orient",
        getattr(cfg, "ORIENT", "?"),
        getattr(cfg, "WIDTH", "?"),
        "x",
        getattr(cfg, "HEIGHT", "?"),
    )
    try:
        orient.log("ui bring-up free={}".format(gc.mem_free()))
    except Exception:
        pass
    bus, ssd, writer = create_lcd_fn(buf=fb_slab.get())
    print("ORIENT after create_lcd free", gc.mem_free())
    touch = TouchCls(bus)
    ui = CalendarUICls(ssd, writer, touch)
    print(
        "ORIENT after CalendarUI free",
        gc.mem_free(),
        "viewport",
        getattr(ui, "viewport_h", "?"),
    )
    ui.mode = mode if mode in ("day", "week") else "day"
    ui.week_offset = week_offset
    ui.day_offset = day_offset
    ui._recompute_geometry()
    ui.set_events(events)
    if sync_label:
        ui.set_sync_time(sync_label)
    if not status and not events:
        status = "No events this week"
    ui.set_status(status)
    ui.set_now()
    ui.needs_fetch = False
    ui.sync_locked = False
    ui.draw_if_dirty()
    print(
        "UI ready mode",
        ui.mode,
        "week",
        week_offset,
        "events",
        len(events),
        "free",
        gc.mem_free(),
    )
    try:
        orient.log("ui ready free={}".format(gc.mem_free()))
        orient.trim_log()
    except Exception:
        pass

    last_fetch = time.ticks_ms()
    last_clock = time.ticks_ms()
    fetched_week = week_offset

    def _release_fb_for_sync():
        """Drop LCD + slab so pending JSON can allocate (then we reboot)."""
        nonlocal bus, ssd, writer, touch, ui
        from display.lcd import release_lcd

        try:
            ui.sync_locked = True
            ui.needs_fetch = False
            ui._dirty = False
            ui._layout = []
            ui._hit_rects = []
            ui._btn_rects = []
            ui._detail = None
            ui._week_days = None
            ui._day_allday = None
            ui.ssd = None
            ui.w = None
            ui.touch = None
        except Exception:
            pass
        try:
            ssd, writer = release_lcd(ssd, writer)
        except Exception as e:
            print("release_lcd", e)
            ssd = None
            writer = None
        touch = None
        bus = None
        ui = None
        try:
            fb_slab.release()
        except Exception as e:
            print("fb release", e)
        # Rebind locals first (above), then GC. Collect while FB is still
        # referenced can MemoryError on the ~640B mark stack under fragmentation.
        try:
            gc.collect()
            gc.collect()
        except MemoryError:
            pass

    while True:
        try:
            now_ms = time.ticks_ms()
            try:
                gesture = touch.poll()
                ui.handle_gesture(gesture)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                _ui_show_error(ui, e, "Touch")

            if time.ticks_diff(now_ms, last_clock) >= 1000:
                try:
                    ui.set_now()
                except Exception as e:
                    _ui_show_error(ui, e, "Clock")
                last_clock = now_ms

            if ui is not None and getattr(ui, "needs_orient_reset", False):
                try:
                    import gc as _gc

                    orient.log(
                        "reset begin free={}".format(_gc.mem_free())
                    )
                except Exception:
                    orient.log("reset begin")
                try:
                    event_cache.mark_paint()
                except Exception as e:
                    orient.log("mark_paint FAIL {}".format(e))
                _soft_reset("orient")

            due = time.ticks_diff(now_ms, last_fetch) >= cfg.POLL_INTERVAL_MS
            week_changed = ui.needs_fetch and ui.week_offset != fetched_week
            if sec and (due or week_changed) and not ui.sync_locked:
                week = ui.week_offset
                mode_now = ui.mode
                day_off = ui.day_offset
                print(
                    "Scheduling fetch week",
                    week,
                    "mode",
                    mode_now,
                    "due" if due else "week",
                    "free",
                    gc.mem_free(),
                )
                ok = _schedule_fetch_and_reset(
                    week, mode_now, day_off, release_fb=_release_fb_for_sync
                )
                # reset normally never returns; if queue failed, we cannot
                # safely rebuild the LCD here — reboot to recover.
                if not ok:
                    print("SYNC failed — recovering via reset")
                    try:
                        event_cache.mark_paint()
                    except Exception:
                        pass
                    _soft_reset("sync fail")
                last_fetch = time.ticks_ms()

            if ui is not None and ui.needs_fetch and not sec:
                # Demo / no secrets: stay local, don't reboot-loop.
                ui.needs_fetch = False

            # Skip paints while a sync reset is in progress.
            if ui is not None and not ui.sync_locked:
                ui.draw_if_dirty()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if ui is not None:
                _ui_show_error(ui, e, "Loop")
            else:
                print("Loop err (no ui)", e)
            gc.collect()
            time.sleep_ms(200)
        time.sleep_ms(20)


def _start_ui_from_cache(
    sec,
    cached,
    week_offset,
    status="",
    mode="day",
    day_offset=0,
    prefer_week=False,
    ui_mods=None,
):
    if cached and cached.get("events") is not None:
        events = cached.get("events") or []
        sync_label = cached.get("sync") or "--:--"
        week_offset = int(cached.get("week") or week_offset)
        if prefer_week and cached.get("mode") in ("day", "week"):
            mode = cached.get("mode")
        elif not prefer_week:
            # Desk default: don't reopen sticky week view from cache.
            mode = "day"
            if abs(int(cached.get("week") or 0)) > 0 and not events:
                week_offset = 0
        try:
            day_offset = int(cached.get("day_offset") or day_offset)
        except Exception:
            pass
        print(
            "UI from cache",
            len(events),
            "week",
            week_offset,
            "mode",
            mode,
            "sync",
            sync_label,
        )
    else:
        events = _demo_events()
        sync_label = "--:--"
        if not status:
            status = "No secrets.py - demo mode" if sec is None else ""
        print("UI demo")
    mode, week_offset, day_offset = _normalize_view(
        mode, week_offset, day_offset, events, prefer_week=prefer_week
    )
    try:
        _run_ui(
            events,
            status,
            sync_label,
            week_offset,
            sec,
            mode=mode,
            day_offset=day_offset,
            ui_mods=ui_mods,
        )
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print("UI start failed:", e)
        try:
            orient.log(
                "UI start FAIL {} free={}".format(e, gc.mem_free())
            )
        except Exception:
            pass
        # Do not mark_paint + reset on bring-up failure — that black-loops.
        try:
            event_cache.save(
                events if cached else _demo_events(),
                "--:--",
                week_offset,
                _short_err(e, "UI"),
                mode=mode,
                day_offset=day_offset,
            )
        except Exception as e2:
            print("recover save failed", e2)
        raise


def main():
    try:
        gc.collect()
        print("boot free", gc.mem_free())

        # Soft-reset wipes RTC to ~2021; restore last NTP stamp before any UI math.
        timeutil.restore_time()
        print("clock", timeutil.local_tuple()[:6], "sane", timeutil.rtc_is_sane())

        sec = _load_secrets()
        print("boot after imports free", gc.mem_free())

        cached = event_cache.load()
        paint = event_cache.take_paint()
        pending = event_cache.take_pending()

        week_offset = 0
        mode = "day"
        day_offset = 0
        if pending is not None:
            week_offset = int(pending.get("week") or 0)
            mode = pending.get("mode") or "day"
            day_offset = int(pending.get("day_offset") or 0)
            # week_offset is ±weeks from *current* Monday after RTC restore
            if abs(week_offset) > 26:
                print("clamp pending week", week_offset)
                week_offset = 0
            print("Pending fetch for week", week_offset, "mode", mode)
        elif cached:
            week_offset = int(cached.get("week") or 0)
            if abs(week_offset) > 26:
                week_offset = 0
            if cached.get("mode") in ("day", "week"):
                mode = cached.get("mode")
            try:
                day_offset = int(cached.get("day_offset") or 0)
            except Exception:
                day_offset = 0

        # After a successful sync reboot: always paint, never fetch again this boot.
        if paint:
            print("Post-sync UI boot")
            # Week-nav paint keeps mode/week; otherwise always today.
            if mode != "week":
                mode = "day"
                week_offset = 0
                day_offset = 0
            _start_ui_from_cache(
                sec,
                cached,
                week_offset,
                mode=mode,
                day_offset=day_offset,
                prefer_week=(mode == "week"),
                ui_mods=_UI_MODS,
            )
            return

        need_fetch = False
        if sec is not None:
            if pending is not None:
                need_fetch = True
            elif not timeutil.rtc_is_sane():
                # Must NTP before trusting "today" / week arrows.
                print("RTC insane — forcing sync")
                need_fetch = True
            elif not event_cache.is_fresh(cached, cfg.POLL_INTERVAL_MS):
                need_fetch = True

        # Mid week-nav fetch: keep week mode. Otherwise desk boots in Day/today.
        prefer_week = pending is not None and mode == "week"
        if not prefer_week:
            mode, week_offset, day_offset = _normalize_view(
                "day",
                0,
                0,
                (cached or {}).get("events") if cached else [],
                prefer_week=False,
            )

        if need_fetch:
            try:
                _fetch_to_cache(
                    sec, week_offset, mode=mode, day_offset=day_offset
                )
                event_cache.mark_paint()
                _soft_reset("cache ready")
                return
            except Exception as e:
                print("Fetch failed:", e)
                msg = _short_err(e, "Fetch")
                # Keep prior cache week if fetch failed; still open UI.
                try:
                    _start_ui_from_cache(
                        sec,
                        cached,
                        week_offset,
                        status=msg,
                        mode=mode,
                        day_offset=day_offset,
                        prefer_week=prefer_week,
                    )
                except Exception as e2:
                    print("UI after fetch fail:", e2)
                    try:
                        event_cache.mark_paint()
                    except Exception:
                        pass
                    _soft_reset("recover")
                return

        _start_ui_from_cache(
            sec,
            cached,
            week_offset,
            mode=mode,
            day_offset=day_offset,
            prefer_week=prefer_week,
        )
    except KeyboardInterrupt:
        raise
    except Exception as e:
        # Stay on serial REPL rather than paint-reboot looping a dead UI.
        print("main err", e)
        try:
            sys.print_exception(e)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
