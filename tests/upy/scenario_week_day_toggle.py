# Day -> Week -> Day redraw under Pico-like heap.
# micropython -X heapsize=190000 tests/upy/scenario_week_day_toggle.py

import sys

for _p in (".", "lib", "tests/upy", "upy_test"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gc
import mem_harness as H


def main():
    ui, ssd, writer, bus = H.bringup_ui(H.sample_events())
    H.tap(ui, "week")
    assert ui.mode == "week", ui.mode
    H.assert_free(H.MIN_FREE_DURING_NAV, "after week")
    H.tap(ui, "day")
    assert ui.mode == "day", ui.mode
    H.assert_free(H.MIN_FREE_DURING_NAV, "after day")
    # Extra redraw (toolbar highlight change path)
    ui._dirty = True
    ui.draw_if_dirty()
    gc.collect()
    H.assert_free(H.MIN_FREE_AFTER_UI, "final")
    print("PASS scenario_week_day_toggle")


try:
    main()
except MemoryError as e:
    print("FAIL MemoryError", e, "free", gc.mem_free())
    raise SystemExit(1)
except Exception as e:
    print("FAIL", e)
    try:
        sys.print_exception(e)
    except Exception:
        pass
    raise SystemExit(1)
