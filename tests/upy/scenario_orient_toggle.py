# Toggle orient.flag L<->P, apply dims, bring up UI, tear down.
# micropython -X heapsize=190000 tests/upy/scenario_orient_toggle.py

import sys

for _p in (".", "lib", "tests/upy", "upy_test"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gc
import config as cfg
import orient
import mem_harness as H
import fake_hw


def main():
    fake_hw.install()
    orient.clear_log()
    orient.save(orient.LANDSCAPE)
    orient.apply(cfg)
    assert cfg.WIDTH == 480 and cfg.HEIGHT == 320

    ui, ssd, writer, bus = H.bringup_ui(H.sample_events())
    assert ui.needs_orient_reset is False

    # Grace blocks immediate rot after mark_boot
    orient.mark_boot()
    ui._do_action("rot")
    assert ui.needs_orient_reset is False
    assert orient.load() == orient.LANDSCAPE

    # Expire grace
    orient._boot_ms = 0
    ui._do_action("rot")
    assert ui.needs_orient_reset is True
    assert orient.load() == orient.PORTRAIT

    # Tear down FB like sync path, then portrait bring-up
    ssd, writer, bus = H.release_fb_for_sync(ui, ssd, writer, bus)
    try:
        gc.collect()
        gc.collect()
    except MemoryError:
        pass

    orient.apply(cfg)
    assert cfg.WIDTH == 320 and cfg.HEIGHT == 480
    ui2, ssd2, writer2, bus2 = H.bringup_ui(H.sample_events())
    assert ui2.viewport_h > 300  # taller portrait viewport
    spec = ui2._toolbar_spec()
    assert any(a == "rot" for _x, _w, _l, a in spec)

    orient.save(orient.LANDSCAPE)
    orient.apply(cfg)
    print("PASS scenario_orient_toggle")


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
