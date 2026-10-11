# Repeated full redraws; free after gc.collect must not trend down hard.
# micropython -X heapsize=190000 tests/upy/scenario_draw_loop.py

import sys

for _p in (".", "lib", "tests/upy", "upy_test"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gc
import mem_harness as H


def main():
    ui, ssd, writer, bus = H.bringup_ui(H.sample_events())
    frees = []
    for i in range(10):
        ui._dirty = True
        ui.draw_if_dirty()
        gc.collect()
        free = gc.mem_free()
        frees.append(free)
        print("DRAW loop", i, "free", free)
    # Allow small jitter; fail if last is much worse than first
    if frees[-1] < H.MIN_FREE_AFTER_UI:
        raise AssertionError("final free {} < {}".format(frees[-1], H.MIN_FREE_AFTER_UI))
    if frees[-1] + 8000 < frees[0]:
        raise AssertionError(
            "free trend leak: first={} last={}".format(frees[0], frees[-1])
        )
    print("PASS scenario_draw_loop", frees)


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
