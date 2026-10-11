"""Minimal SSD/writer doubles for CalendarUI nav tests (no SPI)."""


class FakeSSD:
    def __init__(self, width=480, height=320):
        self.width = width
        self.height = height
        self.show_count = 0
        self.fill = 0

    def fill(self, c):
        self.fills += 1

    def fill_rect(self, x, y, w, h, c):
        pass

    def hline(self, x, y, w, c):
        pass

    def rect(self, x, y, w, h, c):
        pass

    def show(self):
        self.show_count += 1


class FakeWriter:
    def setcolor(self, *a, **k):
        return 0, 0

    def printstring(self, s):
        pass


def make_ui(events=None):
    from display.calendar_ui import CalendarUI

    ui = CalendarUI(FakeSSD(), FakeWriter(), touch=None)
    ui.mode = "day"
    ui.week_offset = 0
    ui.day_offset = 0
    ui.needs_fetch = False
    ui.sync_locked = False
    ui._recompute_geometry()
    if events is not None:
        ui.set_events(events)
    else:
        ui.set_events([])
    ui._dirty = False
    return ui
