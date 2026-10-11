# Device / unix probe: bring up LCD+UI in both orientations and report free RAM.
#   mpremote run tools/orient_probe.py
#   micropython tools/orient_probe.py
#
# Does not soft-reset. Restores prior orient.flag when done.

import gc
import sys

for _p in (".", "lib", "tests/upy", "upy_test"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config as cfg
import orient
import fb_slab


def _step(label):
    gc.collect()
    free = gc.mem_free()
    print("PROBE", label, "free", free, "orient", getattr(cfg, "ORIENT", "?"), end="")
    print(" {}x{}".format(cfg.WIDTH, cfg.HEIGHT))
    orient.log("probe {} free={}".format(label, free))
    return free


def _bringup_once(mode):
    orient.save(mode)
    orient.apply(cfg)
    _step("after apply " + mode)
    if fb_slab.get() is None:
        fb_slab.reserve()
    _step("after FB " + mode)

    from display.lcd import create_lcd, release_lcd
    from display.touch import Touch
    from display.calendar_ui import CalendarUI

    _step("after import " + mode)
    bus, ssd, writer = create_lcd(buf=fb_slab.get())
    _step("after create_lcd " + mode)
    touch = None
    try:
        touch = Touch(bus)
    except Exception as e:
        print("PROBE touch skip", e)
    ui = CalendarUI(ssd, writer, touch)
    ui.set_events([])
    ui.draw_if_dirty()
    _step("after draw " + mode)
    print(
        "PROBE UI ok mode",
        ui.mode,
        "viewport",
        ui.viewport_h,
        "btns",
        len(ui._btn_rects),
    )
    # Teardown for next orientation
    ui.ssd = None
    ui.w = None
    ui.touch = None
    ssd, writer = release_lcd(ssd, writer)
    bus = None
    touch = None
    ui = None
    fb_slab.release()
    gc.collect()
    gc.collect()
    _step("after release " + mode)


def main():
    prev = orient.load()
    print("PROBE start prev", prev)
    orient.clear_log()
    fails = []
    for mode in (orient.LANDSCAPE, orient.PORTRAIT):
        try:
            print("====", mode, "====")
            _bringup_once(mode)
        except MemoryError as e:
            print("PROBE FAIL MemoryError", mode, e, "free", gc.mem_free())
            orient.log("probe OOM {} {}".format(mode, e))
            fails.append(mode)
            try:
                fb_slab.release()
            except Exception:
                pass
            gc.collect()
        except Exception as e:
            print("PROBE FAIL", mode, e)
            orient.log("probe FAIL {} {}".format(mode, e))
            try:
                sys.print_exception(e)
            except Exception:
                pass
            fails.append(mode)
            try:
                fb_slab.release()
            except Exception:
                pass
            gc.collect()

    orient.save(prev)
    orient.apply(cfg)
    orient.dump_log()
    if fails:
        print("FAIL orient_probe", fails)
        raise SystemExit(1)
    print("PASS orient_probe prev restored", prev)


try:
    main()
except SystemExit:
    raise
except Exception as e:
    print("FAIL orient_probe", e)
    try:
        sys.print_exception(e)
    except Exception:
        pass
    raise SystemExit(1)
