# Persist landscape/portrait and apply dims + touch/LCD constants on boot.

ORIENT_PATH = "orient.flag"
LOG_PATH = "orient_log.txt"
LOG_MAX = 1800
LANDSCAPE = "L"
PORTRAIT = "P"

_boot_ms = None


def _ticks_ms():
    try:
        import time

        return time.ticks_ms()
    except Exception:
        import time

        return int(time.time() * 1000)


def _ticks_diff(a, b):
    try:
        import time

        return time.ticks_diff(a, b)
    except Exception:
        return int(a) - int(b)


def _now_tag():
    try:
        return str(_ticks_ms())
    except Exception:
        return "?"


def log(msg, flash=True):
    """
    Print + optional flash breadcrumb (survives soft-reset).

    Append-only — never read/truncate here. Truncation allocates and can
    fragment the boot heap before calendar_ui import (ENOMEM ~2344B).
    """
    line = "{} {}".format(_now_tag(), msg)
    print("ORIENT", line)
    if not flash:
        return
    try:
        import config as cfg

        if not getattr(cfg, "DEBUG_ORIENT", True):
            return
    except Exception:
        pass
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
            f.write("\n")
    except Exception:
        pass


def trim_log():
    """Call after UI is up (or from probe) — safe to allocate."""
    try:
        with open(LOG_PATH, "r") as f:
            data = f.read()
        if len(data) > LOG_MAX:
            with open(LOG_PATH, "w") as f:
                f.write(data[-LOG_MAX:])
    except Exception:
        pass


def dump_log():
    try:
        with open(LOG_PATH, "r") as f:
            print("--- orient_log ---")
            print(f.read())
            print("--- end ---")
    except Exception as e:
        print("orient_log empty/err", e)


def clear_log():
    try:
        import os

        os.remove(LOG_PATH)
    except Exception:
        pass


def load():
    """Return 'L' or 'P'. Missing/invalid file => landscape."""
    try:
        with open(ORIENT_PATH, "r") as f:
            v = f.read(1)
        if v == PORTRAIT:
            return PORTRAIT
    except Exception:
        pass
    return LANDSCAPE


def save(mode):
    m = PORTRAIT if mode == PORTRAIT else LANDSCAPE
    try:
        with open(ORIENT_PATH, "w") as f:
            f.write(m)
        log("save {}".format(m))
        return True
    except Exception as e:
        log("save FAIL {}".format(e))
        print("orient save failed:", e)
        return False


def toggle():
    """Flip orientation on flash. Returns the new mode."""
    cur = load()
    nxt = PORTRAIT if cur == LANDSCAPE else LANDSCAPE
    log("toggle {} -> {}".format(cur, nxt))
    save(nxt)
    return nxt


def mark_boot():
    """Call once from main after apply(); starts Rot grace timer."""
    global _boot_ms
    _boot_ms = _ticks_ms()
    log("boot_mark", flash=False)


def rot_allowed(grace_ms=None):
    """False during post-boot grace — blocks mis-mapped touch reboot loops."""
    if grace_ms is None:
        try:
            import config as cfg

            grace_ms = int(getattr(cfg, "ROT_GRACE_MS", 5000))
        except Exception:
            grace_ms = 5000
    if _boot_ms is None:
        return True
    return _ticks_diff(_ticks_ms(), _boot_ms) >= grace_ms


def apply(cfg=None):
    """
    Mutate config for the saved orientation. Call before create_lcd / UI.
    Returns 'L' or 'P'.
    """
    if cfg is None:
        import config as cfg
    mode = load()
    table = cfg.ORIENT_PORTRAIT if mode == PORTRAIT else cfg.ORIENT_LANDSCAPE
    cfg.WIDTH = table["width"]
    cfg.HEIGHT = table["height"]
    cfg.MADCTL = table["madctl"]
    cfg.TOUCH_FLIP_X = table["touch_flip_x"]
    cfg.TOUCH_FLIP_Y = table["touch_flip_y"]
    cfg.TOUCH_SWAP_XY = table["touch_swap_xy"]
    cfg.TOUCH_CHROME_BAND_PX = table["chrome_band"]
    cfg.GUTTER_W = table["gutter_w"]
    cfg.ORIENT = mode
    try:
        import gc

        free = gc.mem_free()
    except Exception:
        free = -1
    # Serial only — no flash I/O before FB reserve / display import.
    print(
        "ORIENT apply",
        mode,
        cfg.WIDTH,
        "x",
        cfg.HEIGHT,
        "madctl",
        hex(cfg.MADCTL),
        "free",
        free,
    )
    return mode
