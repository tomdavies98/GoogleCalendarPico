"""CalendarUI toolbar nav state (fake SSD — no SPI / heap claims)."""
from __future__ import annotations

import config as cfg
import orient
from tests.host.fake_display import make_ui


def test_week_then_day_stays_on_cache_no_fetch():
    ui = make_ui([])
    ui._do_action("week")
    assert ui.mode == "week"
    ui.needs_fetch = False
    ui._do_action("day")
    assert ui.mode == "day"
    assert ui.needs_fetch is False


def test_prev_next_actions_are_removed():
    ui = make_ui([])
    ui._do_action("week")
    ui.week_offset = 0
    ui.needs_fetch = False
    ui._dirty = False
    ui._do_action("prev")
    ui._do_action("next")
    assert ui.week_offset == 0
    assert ui.needs_fetch is False


def test_now_jumps_home_without_fetch_when_already_today():
    ui = make_ui([])
    ui._do_action("week")
    ui.week_offset = 0
    ui.needs_fetch = False
    ui._do_action("now")
    assert ui.week_offset == 0
    assert ui.needs_fetch is False


def test_rot_sets_orient_reset_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(orient, "ORIENT_PATH", str(tmp_path / "orient.flag"))
    monkeypatch.setattr(orient, "LOG_PATH", str(tmp_path / "orient_log.txt"))
    orient.save(orient.LANDSCAPE)
    orient._boot_ms = 0  # grace expired
    ui = make_ui([])
    ui._do_action("rot")
    assert ui.needs_orient_reset is True
    assert orient.load() == orient.PORTRAIT
    orient.save(orient.LANDSCAPE)


def test_rot_blocked_during_grace(tmp_path, monkeypatch):
    monkeypatch.setattr(orient, "ORIENT_PATH", str(tmp_path / "orient.flag"))
    monkeypatch.setattr(orient, "LOG_PATH", str(tmp_path / "orient_log.txt"))
    orient.save(orient.LANDSCAPE)
    orient.mark_boot()
    ui = make_ui([])
    ui._do_action("rot")
    assert ui.needs_orient_reset is False
    assert orient.load() == orient.LANDSCAPE


def test_toolbar_spec_portrait_fits_width(monkeypatch):
    monkeypatch.setattr(cfg, "WIDTH", 320)
    monkeypatch.setattr(cfg, "HEIGHT", 480)
    monkeypatch.setattr(cfg, "ORIENT", "P")
    ui = make_ui([])
    spec = ui._toolbar_spec()
    actions = [a for _x, _w, _l, a in spec]
    labels = [l for _x, _w, l, _a in spec]
    assert "rot" in actions
    assert "H" in labels  # in portrait, button offers horizontal
    assert "now" in actions
    right = max(x + w for x, w, _l, _a in spec)
    assert right <= 320


def test_toolbar_orient_label_landscape_offers_vertical(monkeypatch):
    monkeypatch.setattr(cfg, "WIDTH", 480)
    monkeypatch.setattr(cfg, "HEIGHT", 320)
    monkeypatch.setattr(cfg, "ORIENT", "L")
    ui = make_ui([])
    labels = [l for _x, _w, l, _a in ui._toolbar_spec()]
    assert "V" in labels
