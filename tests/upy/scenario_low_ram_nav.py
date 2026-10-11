# Stress Week/Day under heap pre-fragmented toward desk levels (~25-35KB free).

import sys

for _p in (".", "lib", "tests/upy", "upy_test"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gc
import mem_harness as H


def _eat_heap_until(target_free, chunks):
    """Allocate until free RAM is near target_free. Returns list of buffers held."""
    held = []
    gc.collect()
    while gc.mem_free() > target_free + 2000:
        size = 2048
        if gc.mem_free() - size < target_free:
            size = max(256, gc.mem_free() - target_free)
        try:
            held.append(bytearray(size))
        except MemoryError:
            break
        chunks.append(len(held))
        if len(held) > 200:
            break
    gc.collect()
    return held


def main():
    ui, ssd, writer, bus = H.bringup_ui(H.sample_events())
    chunks = []
    held = _eat_heap_until(32000, chunks)
    free0 = gc.mem_free()
    print("LOW RAM primed free", free0, "blocks", len(held))
    if free0 > 45000:
        print("WARN could not fragment enough; continuing anyway")

    H.tap(ui, "week")
    assert ui.mode == "week"
    H.tap(ui, "day")
    assert ui.mode == "day"
    H.tap(ui, "week")
    assert ui.mode == "week"
    assert ui.needs_fetch is False

    held[:] = []
    gc.collect()
    print("PASS scenario_low_ram_nav free0", free0)


try:
    main()
except MemoryError as e:
    print("FAIL MemoryError", e, "free", gc.mem_free())
    raise SystemExit(1)
except SystemExit:
    raise
except Exception as e:
    print("FAIL", e)
    try:
        sys.print_exception(e)
    except Exception:
        pass
    raise SystemExit(1)
