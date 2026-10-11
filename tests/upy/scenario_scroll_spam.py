# Up/Down scroll spam with redraws under Pico-like heap.
# micropython -X heapsize=190000 tests/upy/scenario_scroll_spam.py

import sys

for _p in (".", "lib", "tests/upy", "upy_test"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gc
import mem_harness as H


def main():
    ui, ssd, writer, bus = H.bringup_ui(H.sample_events())
    frees = []
    for i in range(8):
        action = "down" if (i % 2) == 0 else "up"
        H.tap(ui, action)
        gc.collect()
        frees.append(gc.mem_free())
    print("scroll frees", frees)
    # After collect, free should not collapse toward zero
    if min(frees) < H.MIN_FREE_DURING_NAV:
        raise AssertionError("scroll free floor broken: {}".format(min(frees)))
    print("PASS scenario_scroll_spam")


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
