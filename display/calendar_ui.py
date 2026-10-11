# Day + week calendar UI — toolbar buttons only (no drag scroll).

import gc
import time
import config as cfg
from display import lcd as colors
from display.touch import GESTURE_TAP, GESTURE_DOWN, GESTURE_UP
import timeutil

try:
    from writer import CWriter
except ImportError:
    import sys

    sys.path.append("lib")
    from writer import CWriter


class CalendarUI:
    def __init__(self, ssd, writer, touch=None):
        self.ssd = ssd
        self.w = writer
        self.touch = touch

        self.mode = cfg.DEFAULT_VIEW  # "day" | "week"
        self.week_offset = 0
        self.day_offset = 0
        self.needs_fetch = False
        self.needs_orient_reset = False  # Rot toggled — main soft-resets
        self.sync_locked = False  # ignore nav that would queue another fetch

        self.events = []
        self.all_day = []
        self._layout = []
        self._hit_rects = []
        self._btn_rects = []

        self.scroll = 0.0
        self.auto_follow = True
        self._manual_until = 0
        self._now_min = 0.0
        self._status = ""
        self._sync_label = "--:--"
        self._detail = None
        self._dirty = True
        self._clock_dirty = True
        self._chrome_consumed = False

        self._recompute_geometry()

    def _short_err(self, err, prefix="Err"):
        msg = "{}: {}".format(prefix, err)
        if len(msg) > 28:
            msg = msg[:28]
        return msg

    def report_error(self, err, prefix="Err"):
        """Log + status bar; never raise."""
        print("ERR", prefix, err)
        try:
            import gc

            free = gc.mem_free()
            print("ERR free", free, "mode", self.mode, "week", self.week_offset)
            # print_exception allocates; skip when the heap is already tight
            if free > 24000:
                import sys

                sys.print_exception(err)
        except Exception:
            pass
        try:
            # Status only — do not force an immediate full redraw here
            self._status = self._short_err(err, prefix)
            self._dirty = True
        except Exception as e2:
            print("status set failed", e2)

    def _recompute_geometry(self):
        self.content_top = cfg.HEADER_H + cfg.TOOLBAR_H
        if self.mode == "day":
            self.timeline_top = self.content_top + cfg.ALLDAY_H
            self.content_h = int(cfg.DAY_MINUTES * cfg.PPM)
        else:
            self.timeline_top = self.content_top + 22
            self.content_h = 7 * cfg.WEEK_ROW_H * 4
        self.viewport_h = cfg.HEIGHT - self.timeline_top
        self.max_scroll = max(0, self.content_h - self.viewport_h)

    def snapshot(self):
        return {
            "events": self.events + self.all_day,
            "scroll": self.scroll,
            "auto_follow": self.auto_follow,
            "manual_until": self._manual_until,
            "status": self._status,
            "sync_label": self._sync_label,
            "detail": self._detail,
            "mode": self.mode,
            "week_offset": self.week_offset,
            "day_offset": self.day_offset,
        }

    def restore(self, state):
        if not state:
            return
        self.mode = state.get("mode", cfg.DEFAULT_VIEW)
        self.week_offset = state.get("week_offset", 0)
        self.day_offset = state.get("day_offset", 0)
        self.scroll = state.get("scroll", 0.0)
        self.auto_follow = state.get("auto_follow", True)
        self._manual_until = state.get("manual_until", 0)
        self._status = state.get("status", "")
        self._sync_label = state.get("sync_label", "--:--")
        self._detail = state.get("detail")
        self._recompute_geometry()
        self.set_events(state.get("events") or [])
        self._dirty = True

    def set_events(self, events):
        try:
            timed = []
            allday = []
            for e in events or []:
                if e.get("all_day"):
                    allday.append(e)
                else:
                    timed.append(e)
            self.events = timed
            self.all_day = allday
            print(
                "set_events timed",
                len(timed),
                "allday",
                len(allday),
                "mode",
                self.mode,
            )
            if self.mode == "day":
                self._pack_day_events()
            else:
                self._pack_week_events()
            self._dirty = True
        except Exception as e:
            self.report_error(e, "Events")

    def set_status(self, text):
        if text != self._status:
            self._status = text or ""
            self._dirty = True

    def set_sync_time(self, label):
        if label != self._sync_label:
            self._sync_label = label
            self._clock_dirty = True

    def set_now(self, now_min=None):
        if now_min is None:
            now_min = timeutil.minutes_since_midnight()
        prev_min = int(self._now_min)
        if (not self.auto_follow) and time.ticks_ms() >= self._manual_until:
            self.auto_follow = True
            if self.mode == "day" and self.day_offset == 0:
                self.scroll = self._scroll_for_now(now_min)
                self._clamp_scroll()
                self._dirty = True
        if self.mode == "day" and self.day_offset == 0 and self.auto_follow:
            new_scroll = self._scroll_for_now(now_min)
            if abs(new_scroll - self.scroll) >= 1:
                self.scroll = new_scroll
                self._clamp_scroll()
                self._dirty = True
        self._now_min = now_min
        # Full redraw every minute is expensive; in week mode it can freeze
        # the UI when free RAM is already tight after FB bring-up.
        if int(now_min) != prev_min and self.mode == "day":
            self._dirty = True
        elif int(now_min) != prev_min:
            self._clock_dirty = True

    def jump_to_now(self):
        self.week_offset = 0
        self.day_offset = 0
        self.auto_follow = True
        self._manual_until = 0
        if self.mode == "day":
            self.scroll = self._scroll_for_now(self._now_min)
        else:
            self.scroll = 0
        self._clamp_scroll()
        self.needs_fetch = True
        self._dirty = True

    def _in_chrome(self, y):
        band = cfg.TOUCH_CHROME_BAND_PX
        return y < band or y >= (cfg.HEIGHT - band)

    def handle_gesture(self, g):
        if g is None:
            return
        try:
            kind = g["kind"]
            sx = g.get("sx", g["x"])
            sy = g.get("sy", g["y"])

            if kind == GESTURE_DOWN:
                self._chrome_consumed = False
                print("DOWN", sx, sy, "mode", self.mode)
                if self._try_chrome_action(sx, sy):
                    self._chrome_consumed = True
                return

            if kind == GESTURE_UP:
                self._chrome_consumed = False
                return

            if kind == GESTURE_TAP:
                print(
                    "TAP",
                    sx,
                    sy,
                    "mode",
                    self.mode,
                    "consumed",
                    self._chrome_consumed,
                )
                if self._chrome_consumed:
                    self._chrome_consumed = False
                    return
                # Retry toolbar if DOWN missed; else content taps
                if self._try_chrome_action(sx, sy):
                    return
                self._on_tap(sx, sy)
                return
        except Exception as e:
            self.report_error(e, "Touch")

    def draw_if_dirty(self):
        if not self._dirty:
            return
        try:
            # Full redraw temporarily needs ~20KB; UI often sits near 30KB free.
            # Always collect before paint so a toolbar tap does not OOM mid-draw.
            gc.collect()
            free = gc.mem_free()
            if getattr(cfg, "DEBUG_DRAW", False):
                print(
                    "DRAW begin free",
                    free,
                    "mode",
                    self.mode,
                    "scroll",
                    int(self.scroll),
                    "max",
                    int(self.max_scroll),
                )
            if free < 12000:
                print("ERR skip draw low RAM", free)
                self._status = "Low RAM"
                self._dirty = False
                return
            self._draw_full()
            self._dirty = False
            self._clock_dirty = False
            gc.collect()
            if getattr(cfg, "DEBUG_DRAW", False):
                print("DRAW ok free", gc.mem_free())
        except MemoryError as e:
            # Avoid redraw storm: keep status text, do not re-dirty.
            print("ERR Low RAM draw", e, "free", gc.mem_free())
            try:
                gc.collect()
            except Exception:
                pass
            self._status = self._short_err(e, "Low RAM")
            self._dirty = False
        except Exception as e:
            print("ERR Draw", e, "free", gc.mem_free())
            try:
                if gc.mem_free() > 24000:
                    import sys

                    sys.print_exception(e)
            except Exception:
                pass
            try:
                self._status = self._short_err(e, "Draw")
            except Exception:
                pass
            self._dirty = False

    def _scroll_for_now(self, now_min):
        y = now_min * cfg.PPM
        return y - self.viewport_h * cfg.AUTO_FOLLOW_BIAS

    def _clamp_scroll(self):
        try:
            if self.scroll < 0:
                self.scroll = 0
            # Guard against broken geometry (avoid huge redraw ranges).
            max_s = self.max_scroll
            if max_s is None or max_s < 0:
                max_s = 0
                self.max_scroll = 0
            if max_s > 100000:
                print("ERR max_scroll insane", max_s)
                max_s = 100000
                self.max_scroll = max_s
            if self.scroll > max_s:
                self.scroll = max_s
        except Exception as e:
            print("ERR clamp", e)
            self.scroll = 0

    def _enter_manual(self):
        self.auto_follow = False
        self._manual_until = time.ticks_add(
            time.ticks_ms(), cfg.MANUAL_FOLLOW_TIMEOUT_MS
        )

    def _scroll_step(self):
        if self.mode == "day":
            step = cfg.SCROLL_STEP_MINUTES * cfg.PPM
        else:
            step = max(40, int(self.viewport_h * 0.75))
        # Keep steps modest so one tap never jumps the whole day buffer.
        if step > 400:
            step = 400
        return step

    def _scroll_by(self, direction):
        """direction: -1 up, +1 down. Logs + safe clamp; never raises."""
        try:
            before = self.scroll
            step = self._scroll_step()
            self._enter_manual()
            self.scroll = before + direction * step
            self._clamp_scroll()
            if getattr(cfg, "DEBUG_DRAW", False):
                print(
                    "NAV scroll",
                    "up" if direction < 0 else "down",
                    "mode",
                    self.mode,
                    "scroll",
                    int(before),
                    "->",
                    int(self.scroll),
                    "step",
                    int(step),
                    "max",
                    int(self.max_scroll),
                    "free",
                    gc.mem_free(),
                )
            else:
                print(
                    "NAV",
                    "up" if direction < 0 else "down",
                    int(before),
                    "->",
                    int(self.scroll),
                    "free",
                    gc.mem_free(),
                )
            self._dirty = True
        except Exception as e:
            self.report_error(e, "Scroll")

    def _view_day0(self):
        return timeutil.local_midnight_utc() + self.day_offset * 86400

    def _view_monday(self):
        return timeutil.monday_midnight_utc() + self.week_offset * 7 * 86400

    def _pack_day_events(self):
        day0 = self._view_day0()
        day1 = day0 + 86400
        timed = []
        allday = []
        for e in self.events + self.all_day:
            s = e.get("start_epoch") or 0
            en = e.get("end_epoch") or s
            if e.get("all_day"):
                if s < day1 and en > day0:
                    allday.append(e)
            else:
                if s < day1 and en > day0:
                    timed.append(e)
        self._day_allday = allday
        self._layout = []
        # Simple non-overlap pack
        columns = []
        for e in sorted(timed, key=lambda x: x.get("start_epoch") or 0):
            s = e.get("start_epoch") or 0
            en = e.get("end_epoch") or s
            start_m = max(0, (s - day0) / 60.0)
            end_m = min(cfg.DAY_MINUTES, (en - day0) / 60.0)
            if end_m <= start_m:
                end_m = start_m + 15
            col = 0
            while True:
                ok = True
                for c_start, c_end, c_col in columns:
                    if c_col == col and not (end_m <= c_start or start_m >= c_end):
                        ok = False
                        break
                if ok:
                    break
                col += 1
            columns.append((start_m, end_m, col))
            self._layout.append(
                {
                    "event": e,
                    "start_m": start_m,
                    "end_m": end_m,
                    "col": col,
                    "cols": 1,
                }
            )
        max_col = 0
        for it in self._layout:
            max_col = max(max_col, it["col"])
        ncols = max_col + 1
        for it in self._layout:
            it["cols"] = ncols

    def _pack_week_events(self):
        monday = self._view_monday()
        days = [[] for _ in range(7)]
        pool = self.events + self.all_day
        for e in pool:
            s = e.get("start_epoch") or 0
            en = e.get("end_epoch") or s
            for d in range(7):
                d0 = monday + d * 86400
                d1 = d0 + 86400
                if s < d1 and en > d0:
                    start_m = 0 if e.get("all_day") else max(0, (s - d0) / 60.0)
                    days[d].append((start_m, e))
        for d in range(7):
            days[d].sort(key=lambda x: (0 if x[1].get("all_day") else 1, x[0]))
        self._week_days = days
        counts = [len(days[d]) for d in range(7)]
        print(
            "week pack mon",
            int(monday),
            "pool",
            len(pool),
            "per_day",
            counts,
        )
        max_n = max(counts) if counts else 0
        self.content_h = max(self.viewport_h, max_n * cfg.WEEK_ROW_H + 8)
        self.max_scroll = max(0, self.content_h - self.viewport_h)

    def _orient_button_label(self):
        # Show the orientation you switch *to*: V = vertical/portrait, H = horizontal.
        if getattr(cfg, "ORIENT", "L") == "P" or cfg.WIDTH <= 320:
            return "H"
        return "V"

    def _toolbar_spec(self):
        """
        Ordered (x, w, label, action) for the active width.
        Keep hit zones and draw in sync via this single list.
        """
        w = cfg.WIDTH
        orient_lbl = self._orient_button_label()
        if w <= 320:
            return [
                (2, 48, "Day", "day"),
                (52, 48, "Wk", "week"),
                (102, 28, "^", "up"),
                (132, 28, "v", "down"),
                (162, 36, orient_lbl, "rot"),
                (w - 52, 50, "Now", "now"),
            ]
        return [
            (2, 70, "Day", "day"),
            (76, 58, "Week", "week"),
            (140, 36, "^", "up"),
            (180, 36, "v", "down"),
            (w - 118, 40, orient_lbl, "rot"),
            (w - 76, 72, "Now", "now"),
        ]

    def _toolbar_x_action(self, x):
        for bx, bw, _label, action in self._toolbar_spec():
            if bx <= x < bx + bw:
                return action
        # Prefer right-side Now/Rot when tap lands in the gap near the edge.
        if x >= cfg.WIDTH - 80:
            return "now"
        return None

    def _hit_button(self, x, y):
        slop = cfg.TOUCH_HIT_SLOP
        in_bar = self._in_chrome(y) or y < (cfg.HEADER_H + cfg.TOOLBAR_H + 48)

        # Escape hatch: left chrome in week view → Day (width of Day button).
        day_right = 74 if cfg.WIDTH > 320 else 52
        if self.mode == "week" and in_bar and x < day_right:
            return "day"

        # In toolbar/chrome bands, match by X against drawn buttons (ignore Y).
        if in_bar and self._btn_rects:
            for bx, by, bw, bh, action in self._btn_rects:
                if bx - slop <= x < bx + bw + slop:
                    return action
            return self._toolbar_x_action(x)
        for bx, by, bw, bh, action in self._btn_rects:
            if (
                bx - slop <= x < bx + bw + slop
                and by - slop <= y < by + bh + slop
            ):
                return action
        return None

    def _try_chrome_action(self, x, y):
        try:
            action = self._hit_button(x, y)
            if action:
                print("BTN", action, "at", x, y, "mode", self.mode)
                self._do_action(action)
                return True
            if self._in_chrome(y) or y < cfg.HEADER_H + cfg.TOOLBAR_H + 48:
                print("MISS chrome", x, y, "mode", self.mode)
            return False
        except Exception as e:
            self.report_error(e, "Btn")
            return True

    def _on_tap(self, x, y):
        try:
            if self._detail:
                self._detail = None
                self._dirty = True
                return

            if self.mode == "week":
                if self.content_top <= y < self.timeline_top:
                    col_w = cfg.WIDTH // 7
                    day_i = min(6, x // col_w)
                    monday = self._view_monday()
                    today0 = timeutil.local_midnight_utc()
                    self.day_offset = int(
                        round((monday + day_i * 86400 - today0) / 86400.0)
                    )
                    self.mode = "day"
                    self.auto_follow = self.day_offset == 0
                    self.scroll = (
                        0
                        if self.day_offset != 0
                        else self._scroll_for_now(self._now_min)
                    )
                    self._recompute_geometry()
                    self._pack_day_events()
                    self._dirty = True
                    return

            for rx, ry, rw, rh, ev in self._hit_rects:
                if rx <= x < rx + rw and ry <= y < ry + rh:
                    self._detail = ev
                    self._dirty = True
                    return
        except Exception as e:
            self.report_error(e, "Tap")

    def _sync_week_offset_from_day(self):
        day0 = self._view_day0()
        mon = timeutil.monday_midnight_utc()
        return int(
            round((timeutil.monday_midnight_utc(day0) - mon) / (7 * 86400.0))
        )

    def _do_action(self, action):
        try:
            if action == "day":
                self.mode = "day"
                self._detail = None
                if self.day_offset == 0:
                    self.auto_follow = True
                    self.scroll = self._scroll_for_now(self._now_min)
                self._recompute_geometry()
                self._pack_day_events()
                self._dirty = True
            elif action == "week":
                # Week view is always anchored to today's week (+ week_offset).
                self.week_offset = self._sync_week_offset_from_day()
                if abs(self.week_offset) > 26:
                    print("clamp week_offset on enter", self.week_offset)
                    self.week_offset = 0
                    self.day_offset = 0
                self.mode = "week"
                self._detail = None
                self.scroll = 0
                self.auto_follow = False
                self._recompute_geometry()
                self._pack_week_events()
                self._dirty = True
            elif action == "rot":
                if self.sync_locked or self.needs_fetch:
                    print("BTN rot ignored (sync pending)")
                    self._status = "Syncing..."
                    return
                try:
                    import orient

                    if not orient.rot_allowed():
                        orient.log("rot blocked (grace)")
                        self._status = "Wait…"
                        self._dirty = True
                        return
                    try:
                        import gc

                        free = gc.mem_free()
                    except Exception:
                        free = -1
                    orient.log(
                        "rot tap mode={} week={} free={}".format(
                            self.mode, self.week_offset, free
                        )
                    )
                    nxt = orient.toggle()
                    self._status = "Rotate..."
                    self.needs_orient_reset = True
                    self._dirty = False
                    orient.log("rot queued reset -> {}".format(nxt))
                except Exception as e:
                    try:
                        import orient as _o

                        _o.log("rot FAIL {}".format(e))
                    except Exception:
                        pass
                    self.report_error(e, "Rot")
            elif action == "up":
                self._scroll_by(-1)
            elif action == "down":
                self._scroll_by(1)
            elif action == "now":
                if self.sync_locked or self.needs_fetch:
                    print("BTN now ignored (sync pending)")
                    self._status = "Syncing..."
                    return
                old_week = self.week_offset
                self.jump_to_now()
                if self.week_offset != old_week:
                    self.needs_fetch = True
                    self._status = "Syncing..."
                    self._dirty = False
                else:
                    self.needs_fetch = False
                    self._recompute_geometry()
                    if self.mode == "day":
                        self._pack_day_events()
                    else:
                        self._pack_week_events()
                    self._dirty = True
        except Exception as e:
            self.report_error(e, "Action")

    def _text(self, s, x, y, fg=None, bg=None):
        if fg is None:
            fg = colors.WHITE
        if bg is None:
            bg = colors.DARKBLUE
        self.w.setcolor(fg, bg)
        CWriter.set_textpos(self.ssd, y, x)
        self.w.printstring(s)

    def _trunc(self, s, max_px):
        if not s:
            return ""
        max_chars = max(1, max_px // 6)
        if len(s) <= max_chars:
            return s
        if max_chars <= 1:
            return s[:1]
        return s[: max_chars - 1] + ".."

    def _button(self, x, y, w, h, label, action, active=False):
        bg = colors.BLUE if active else colors.GREY
        self.ssd.fill_rect(x, y, w, h, bg)
        tx = x + max(2, (w - len(label) * 6) // 2)
        self._text(label, tx, y + 8, colors.WHITE, bg)
        self._btn_rects.append((x, y, w, h, action))

    def _draw_full(self):
        self.ssd.fill(colors.DARKBLUE)
        self._btn_rects = []
        self._hit_rects = []
        self._draw_header()
        self._draw_toolbar()
        if self.mode == "day":
            self._draw_allday()
            self._draw_day_timeline()
            if self.day_offset == 0:
                self._draw_now_line()
        else:
            self._draw_week()
        if self._detail:
            self._draw_detail()
        self.ssd.show()

    def _draw_header(self):
        self.ssd.fill_rect(0, 0, cfg.WIDTH, cfg.HEADER_H, colors.BLACK)
        lt = timeutil.local_tuple()
        clock_s = timeutil.format_hhmm(lt)
        if self.mode == "day":
            title = timeutil.format_day_short(self._view_day0())
            if self.day_offset == 0:
                title = "Today " + title
        else:
            title = timeutil.format_week_label(self._view_monday())
        title_max = cfg.WIDTH // 2 - 24
        self._text(
            self._trunc(title, title_max), 8, 8, colors.WHITE, colors.BLACK
        )
        self._text(clock_s, cfg.WIDTH // 2 - 16, 8, colors.YELLOW, colors.BLACK)
        sync_s = "sync " + self._sync_label
        if self._status:
            self._text(
                self._trunc(self._status, cfg.WIDTH - 16),
                8,
                22,
                colors.ORANGE,
                colors.BLACK,
            )
        else:
            sync_x = max(8, cfg.WIDTH - 8 - len(sync_s) * 6)
            self._text(sync_s, sync_x, 22, colors.GREY, colors.BLACK)

    def _draw_toolbar(self):
        y = cfg.HEADER_H
        self.ssd.fill_rect(0, y, cfg.WIDTH, cfg.TOOLBAR_H, colors.BLACK)
        for bx, bw, label, action in self._toolbar_spec():
            active = (action == "day" and self.mode == "day") or (
                action == "week" and self.mode == "week"
            )
            self._button(bx, y + 1, bw, 26, label, action, active)

    def _draw_allday(self):
        y0 = self.content_top
        self.ssd.fill_rect(0, y0, cfg.WIDTH, cfg.ALLDAY_H, colors.DARKGREEN)
        items = getattr(self, "_day_allday", self.all_day)
        if not items:
            self._text("No all-day", 8, y0 + 6, colors.LIGHTGREEN, colors.DARKGREEN)
            return
        titles = ", ".join(e.get("summary") or "(No title)" for e in items[:4])
        self._text(
            self._trunc(titles, cfg.WIDTH - 16),
            8,
            y0 + 6,
            colors.WHITE,
            colors.DARKGREEN,
        )

    def _draw_day_timeline(self):
        top = self.timeline_top
        vh = self.viewport_h
        if vh < 1:
            vh = 1
        self.ssd.fill_rect(0, top, cfg.GUTTER_W, vh, colors.BLACK)
        self.ssd.fill_rect(
            cfg.GUTTER_W, top, cfg.WIDTH - cfg.GUTTER_W, vh, colors.DARKBLUE
        )

        ppm = cfg.PPM if cfg.PPM else 1.0
        first_min = int(self.scroll / ppm)
        first_hour = max(0, min(24, first_min // 60))
        last_hour = min(24, int((self.scroll + vh) / ppm) // 60 + 1)
        if last_hour < first_hour:
            last_hour = first_hour
        # Hard cap hour lines — a bad scroll must never loop huge.
        if last_hour - first_hour > 30:
            print("ERR hour range", first_hour, last_hour, "scroll", self.scroll)
            last_hour = first_hour + 30
        for hour in range(first_hour, last_hour + 1):
            cy = hour * 60 * ppm - self.scroll
            sy = int(top + cy)
            if sy < top - 12 or sy > cfg.HEIGHT:
                continue
            self.ssd.hline(cfg.GUTTER_W, sy, cfg.WIDTH - cfg.GUTTER_W, colors.GREY)
            if sy - 6 >= top and sy - 6 < cfg.HEIGHT - 8:
                self._text(
                    "{:02d}".format(hour), 8, sy - 6, colors.GREY, colors.BLACK
                )

        usable_w = cfg.WIDTH - cfg.GUTTER_W - 4
        for it in self._layout:
            y0 = top + it["start_m"] * ppm - self.scroll
            y1 = top + it["end_m"] * ppm - self.scroll
            if y1 < top or y0 > cfg.HEIGHT:
                continue
            draw_y = max(top, int(y0))
            draw_h = max(12, min(vh, int(y1) - draw_y))
            if draw_h > vh:
                draw_h = vh
            cols = max(1, it["cols"])
            col_w = usable_w // cols
            x = cfg.GUTTER_W + 2 + it["col"] * col_w
            w = col_w - 3
            ev = it["event"]
            bg = colors.EVENT_A if (it["col"] % 2) == 0 else colors.EVENT_B
            self.ssd.fill_rect(x, draw_y, w, draw_h, bg)
            self._text(
                self._trunc(ev.get("summary") or "", w - 4),
                x + 2,
                draw_y + 2,
                colors.WHITE,
                bg,
            )
            self._hit_rects.append((x, draw_y, w, draw_h, ev))

    def _draw_now_line(self):
        y = int(self.timeline_top + self._now_min * cfg.PPM - self.scroll)
        if self.timeline_top <= y < cfg.HEIGHT:
            self.ssd.hline(cfg.GUTTER_W, y, cfg.WIDTH - cfg.GUTTER_W, colors.RED)
            self.ssd.fill_rect(cfg.GUTTER_W, y - 1, 6, 3, colors.RED)

    def _draw_week(self):
        top = self.timeline_top
        col_w = cfg.WIDTH // 7
        monday = self._view_monday()
        today0 = timeutil.local_midnight_utc()
        # Day headers
        for d in range(7):
            x = d * col_w
            d0 = monday + d * 86400
            label = timeutil.format_day_short(d0)
            if col_w < 50:
                label = (label or "?")[:2]
            else:
                label = label[:5]
            bg = colors.DARKGREEN if d0 == today0 else colors.BLACK
            self.ssd.fill_rect(x, self.content_top, col_w - 1, 22, bg)
            self._text(label, x + 2, self.content_top + 6, colors.WHITE, bg)

        self.ssd.fill_rect(0, top, cfg.WIDTH, self.viewport_h, colors.DARKBLUE)
        days = getattr(self, "_week_days", [[] for _ in range(7)])
        total = 0
        for d in range(7):
            total += len(days[d])
        if total == 0:
            self._text(
                "No events this week",
                cfg.WIDTH // 2 - 60,
                top + 40,
                colors.GREY,
                colors.DARKBLUE,
            )
            return
        for d in range(7):
            x = d * col_w
            items = days[d]
            for i, (_sm, ev) in enumerate(items):
                sy = int(top + i * cfg.WEEK_ROW_H - self.scroll)
                if sy + cfg.WEEK_ROW_H < top or sy > cfg.HEIGHT:
                    continue
                h = cfg.WEEK_ROW_H - 2
                bg = colors.EVENT_A if not ev.get("all_day") else colors.DARKGREEN
                self.ssd.fill_rect(x + 1, sy, col_w - 3, h, bg)
                self._text(
                    self._trunc(ev.get("summary") or "", col_w - 6),
                    x + 3,
                    sy + 8,
                    colors.WHITE,
                    bg,
                )
                self._hit_rects.append((x, sy, col_w - 3, h, ev))

    def _draw_detail(self):
        ev = self._detail
        if not ev:
            return
        x, y, w, h = 40, 60, cfg.WIDTH - 80, 160
        self.ssd.fill_rect(x, y, w, h, colors.BLACK)
        self.ssd.rect(x, y, w, h, colors.YELLOW)
        self._text(self._trunc(ev.get("summary") or "", w - 16), x + 8, y + 12)
        loc = ev.get("location") or ""
        if loc:
            self._text(self._trunc(loc, w - 16), x + 8, y + 36, colors.CYAN, colors.BLACK)
        when = timeutil.format_range_local(
            ev.get("start_epoch") or 0,
            ev.get("end_epoch") or 0,
            ev.get("all_day"),
        )
        self._text(when, x + 8, y + 60, colors.YELLOW, colors.BLACK)
        self._text("Tap to close", x + 8, y + h - 28, colors.GREY, colors.BLACK)
