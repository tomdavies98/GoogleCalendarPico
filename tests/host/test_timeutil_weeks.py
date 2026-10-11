"""Host tests for week math and RTC sanity (no Pico hardware)."""
from __future__ import annotations

import time

import timeutil


def test_rtc_is_sane_accepts_2025():
    assert timeutil.rtc_is_sane(1735689600) is True  # 2025-01-01 UTC


def test_rtc_is_sane_rejects_2021_default():
    assert timeutil.rtc_is_sane(1609459200) is False


def test_week_label_plus_one_week_stays_same_year():
    try:
        mon = time.mktime((2026, 10, 5, 0, 0, 0, 0, 0))
    except TypeError:
        mon = time.mktime((2026, 10, 5, 0, 0, 0, 0, 0, -1))

    label0 = timeutil.format_week_label(mon)
    label1 = timeutil.format_week_label(mon + 7 * 86400)
    assert "Oct" in label0
    assert "26" in label0
    assert "Oct" in label1
    assert "26" in label1
    y0 = time.gmtime(int(mon))[0]
    y1 = time.gmtime(int(mon + 7 * 86400))[0]
    assert y1 == y0


def test_monday_plus_offset_is_seven_days():
    utc = 1728086400
    a = timeutil.monday_midnight_utc(utc=utc)
    b = a + 7 * 86400
    assert abs((b - a) - 7 * 86400) < 1


def test_persist_and_restore_stamp(tmp_path, monkeypatch):
    stamp = tmp_path / "rtc_stamp.txt"
    monkeypatch.setattr(timeutil, "_RTC_STAMP_PATH", str(stamp))

    good = 1735689600
    assert timeutil.persist_time(good) is True
    assert stamp.read_text().strip() == str(good)

    called = {}

    def fake_set(utc):
        called["utc"] = int(utc)

    monkeypatch.setattr(timeutil, "set_utc_epoch", fake_set)

    def sane(utc=None):
        # Current RTC insane; stamp epoch is sane.
        if utc is None:
            return False
        return 2024 <= time.gmtime(int(utc))[0] <= 2036

    monkeypatch.setattr(timeutil, "rtc_is_sane", sane)
    assert timeutil.restore_time() is True
    assert called["utc"] == good
