"""Orientation flag + config apply (no hardware)."""
from __future__ import annotations

import orient
import config as cfg


def test_apply_landscape_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(orient, "ORIENT_PATH", str(tmp_path / "orient.flag"))
    monkeypatch.setattr(orient, "LOG_PATH", str(tmp_path / "orient_log.txt"))
    assert orient.load() == orient.LANDSCAPE
    mode = orient.apply(cfg)
    assert mode == orient.LANDSCAPE
    assert cfg.WIDTH == 480
    assert cfg.HEIGHT == 320
    assert cfg.MADCTL == 0x48
    assert cfg.TOUCH_SWAP_XY is False


def test_toggle_to_portrait(tmp_path, monkeypatch):
    monkeypatch.setattr(orient, "ORIENT_PATH", str(tmp_path / "orient.flag"))
    monkeypatch.setattr(orient, "LOG_PATH", str(tmp_path / "orient_log.txt"))
    nxt = orient.toggle()
    assert nxt == orient.PORTRAIT
    assert orient.load() == orient.PORTRAIT
    orient.apply(cfg)
    assert cfg.WIDTH == 320
    assert cfg.HEIGHT == 480
    assert cfg.MADCTL == 0x48  # same panel addressing; dims select portrait blit
    assert cfg.TOUCH_SWAP_XY is True
    # restore landscape for other tests in this process
    orient.save(orient.LANDSCAPE)
    orient.apply(cfg)


def test_log_survives_append(tmp_path, monkeypatch):
    monkeypatch.setattr(orient, "ORIENT_PATH", str(tmp_path / "orient.flag"))
    monkeypatch.setattr(orient, "LOG_PATH", str(tmp_path / "orient_log.txt"))
    orient.clear_log()
    orient.log("hello")
    orient.log("world")
    text = (tmp_path / "orient_log.txt").read_text(encoding="utf-8")
    assert "hello" in text and "world" in text
