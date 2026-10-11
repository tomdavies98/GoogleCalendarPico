# Shared UI bring-up + free-RAM asserts for MicroPython scenarios.
# Run from repo root (unix) or with upy_test/ on sys.path (device).

import gc
import sys

# Repo paths when running under unix MicroPython from project root
for _p in (".", "lib", "tests/upy"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import fake_hw

# Observed Pico W desk UI floors (after FB + CalendarUI)
HEAPSIZE = 190000
MIN_FREE_AFTER_UI = 20000
MIN_FREE_BEFORE_SYNC = 8000
MIN_FREE_DURING_NAV = 12000


def _is_rp2():
    return sys.platform == "rp2"


def assert_free(min_free, label):
    gc.collect()
    free = gc.mem_free()
    print("FREE", label, free, "min", min_free)
    if free < min_free:
        raise AssertionError(
            "free RAM {} < {} at {}".format(free, min_free, label)
        )
    return free


def _make_mem_ssd(buf, width, height):
    """In-memory GS4 framebuffer (unix / no SPI)."""
    import framebuf

    try:
        from boolpalette import BoolPalette
    except ImportError:
        sys.path.append("lib")
        from boolpalette import BoolPalette

    class MemSSD(framebuf.FrameBuffer):
        def __init__(self, buf, w, h):
            self.width = w
            self.height = h
            self.mode = framebuf.GS4_HMSB
            self.palette = BoolPalette(self.mode)
            self.lut = bytearray(32)
            self._buf = buf
            self.mvb = memoryview(buf)
            self.show_count = 0
            super().__init__(buf, w, h, self.mode)

        def show(self):
            self.show_count += 1

        def rgb(self, r, g, b):
            return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    return MemSSD(buf, width, height)


def bringup_ui(events=None):
    """
    Mirror main._run_ui bring-up: reserve FB, create display, CalendarUI, paint.
    Returns (ui, ssd, writer, bus_or_none).
    """
    fake_hw.install()
    import config as cfg
    import fb_slab
    from display import lcd as colors
    from display.calendar_ui import CalendarUI

    gc.collect()
    gc.collect()
    # Prior mpremote runs can leave a fragmented heap / live slab.
    try:
        fb_slab.release()
    except Exception:
        pass
    gc.collect()
    gc.collect()
    print("bringup free", gc.mem_free())
    # Import first (above), then reserve — matches main._run_ui.
    fb_slab.reserve()
    buf = fb_slab.get()

    bus = None
    if _is_rp2():
        from display.lcd import create_lcd
        from display.touch import Touch

        bus, ssd, writer = create_lcd(buf=buf)
        touch = Touch(bus)
    else:
        ssd = _make_mem_ssd(buf, cfg.WIDTH, cfg.HEIGHT)
        sys.path.append("lib")
        from writer import CWriter
        import fonts.arial10 as font

        # Register palette colors like create_lcd
        for idx, rgb in (
            (colors.BLACK, (0, 0, 0)),
            (colors.GREEN, (0, 200, 80)),
            (colors.RED, (220, 50, 50)),
            (colors.LIGHTRED, (180, 80, 80)),
            (colors.BLUE, (60, 120, 220)),
            (colors.YELLOW, (230, 200, 40)),
            (colors.GREY, (90, 90, 100)),
            (colors.MAGENTA, (200, 60, 180)),
            (colors.CYAN, (40, 190, 200)),
            (colors.LIGHTGREEN, (80, 160, 100)),
            (colors.DARKGREEN, (20, 60, 40)),
            (colors.DARKBLUE, (20, 30, 55)),
            (colors.ORANGE, (230, 140, 40)),
            (colors.EVENT_A, (50, 100, 180)),
            (colors.EVENT_B, (70, 90, 160)),
            (colors.WHITE, (240, 240, 245)),
        ):
            CWriter.create_color(ssd, idx, rgb[0], rgb[1], rgb[2])
        writer = CWriter(
            ssd, font, fgcolor=colors.WHITE, bgcolor=colors.DARKBLUE, verbose=False
        )
        writer.set_clip(True, True, False)
        touch = None

    ui = CalendarUI(ssd, writer, touch)
    ui.mode = "day"
    ui.week_offset = 0
    ui.day_offset = 0
    ui._recompute_geometry()
    ui.set_events(events or [])
    ui.needs_fetch = False
    ui.sync_locked = False
    ui.draw_if_dirty()
    gc.collect()
    assert_free(MIN_FREE_AFTER_UI, "after UI ready")
    print(
        "UI ready mode",
        ui.mode,
        "free",
        gc.mem_free(),
        "platform",
        sys.platform,
    )
    return ui, ssd, writer, bus


def tap(ui, action, draw=True):
    """
    Toolbar action + optional paint.
    Matches main loop: skip paint when needs_fetch / sync_locked.
    """
    print("TAP", action, "mode", ui.mode, "week", ui.week_offset)
    ui._do_action(action)
    if draw and (not ui.needs_fetch) and (not ui.sync_locked):
        ui.draw_if_dirty()
        gc.collect()
        assert_free(MIN_FREE_DURING_NAV, "after tap " + action)
    else:
        print(
            "TAP skip draw fetch",
            ui.needs_fetch,
            "locked",
            ui.sync_locked,
            "free",
            gc.mem_free(),
        )
    return ui


def release_fb_for_sync(ui, ssd=None, writer=None, bus=None):
    """
    Mirror main._release_fb_for_sync (break refs only).

    Returns (None, None, None). Caller MUST rebind:
        ssd, writer, bus = release_fb_for_sync(ui, ssd, writer, bus)
        gc.collect(); gc.collect()
    before request_fetch. Collecting inside this function cannot free the
    FrameBuffer while the caller still holds ssd/bus, and gc.collect() itself
    can MemoryError (mark stack ~640B) on a fragmented low heap.
    """
    import fb_slab

    ui.sync_locked = True
    ui.needs_fetch = False
    ui._dirty = False
    ui._status = "Syncing..."
    ui._layout = []
    ui._hit_rects = []
    ui._btn_rects = []
    ui._detail = None
    ui._week_days = None
    ui._day_allday = None
    ui.ssd = None
    ui.w = None
    ui.touch = None
    try:
        from display.lcd import release_lcd

        release_lcd(ssd, writer)
    except Exception:
        pass
    try:
        fb_slab.release()
    except Exception:
        pass
    return None, None, None


def schedule_fetch_like_main(ui):
    """
    Same contract as main._schedule_fetch_and_reset after FB release:
    no redraw, request_fetch, then reset stub -> SystemExit RESET.

    Call release_fb_for_sync, rebind Nones, gc.collect, then this.
    """
    import event_cache

    fake_hw.install()
    week = ui.week_offset
    mode = ui.mode
    day_off = ui.day_offset
    # Critical: must NOT full-redraw here (historical crash at free≈4592)
    free = gc.mem_free()
    print("SYNC begin", week, mode, free)
    if free < MIN_FREE_BEFORE_SYNC:
        raise AssertionError(
            "free {} too low before sync (min {})".format(free, MIN_FREE_BEFORE_SYNC)
        )
    ok = event_cache.request_fetch(week, mode, day_off)
    if not ok:
        try:
            gc.collect()
        except MemoryError:
            pass
        ok = event_cache.request_fetch(week, mode, day_off)
    if not ok:
        raise AssertionError("request_fetch failed")
    print("SYNC ok reset", week)
    fake_hw.trigger_reset()


def sample_events():
    """Small event pool for pack/draw stress."""
    import time
    import timeutil

    utc = time.time()
    if not timeutil.rtc_is_sane(utc):
        # unix/default clock: pin to a sane 2026 stamp for labels
        utc = 1791686400
        try:
            timeutil.set_utc_epoch(utc)
        except Exception:
            pass
    today0 = timeutil.local_midnight_utc(utc)
    monday = timeutil.monday_midnight_utc(utc)
    return [
        {
            "summary": "Standup",
            "location": "",
            "start_epoch": today0 + 9 * 3600,
            "end_epoch": today0 + 9 * 3600 + 900,
            "all_day": False,
        },
        {
            "summary": "Review",
            "location": "",
            "start_epoch": today0 + 14 * 3600,
            "end_epoch": today0 + 15 * 3600,
            "all_day": False,
        },
        {
            "summary": "All day",
            "location": "",
            "start_epoch": today0,
            "end_epoch": today0 + 86400,
            "all_day": True,
        },
        {
            "summary": "Tue slot",
            "location": "",
            "start_epoch": monday + 86400 + 10 * 3600,
            "end_epoch": monday + 86400 + 11 * 3600,
            "all_day": False,
        },
    ]
