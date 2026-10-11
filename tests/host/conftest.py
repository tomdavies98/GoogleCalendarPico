"""CPython bootstrap: stub MicroPython-only modules before importing UI code."""
from __future__ import annotations

import gc
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

# CPython has no gc.mem_free
if not hasattr(gc, "mem_free"):
    gc.mem_free = lambda: 10**9  # type: ignore[attr-defined]
if not hasattr(gc, "mem_alloc"):
    gc.mem_alloc = lambda: 0  # type: ignore[attr-defined]


def _install_machine_stub():
    if "machine" in sys.modules:
        return
    machine = types.ModuleType("machine")

    class _RTC:
        def datetime(self, t=None):
            return None

    def reset():
        raise SystemExit("RESET")

    machine.RTC = _RTC
    machine.reset = reset
    machine.Pin = object
    machine.SPI = object
    machine.PWM = object
    sys.modules["machine"] = machine


def _install_lcd_colors_stub():
    """Avoid importing real display.lcd (needs SPI / ili9486 / viper)."""
    mod = types.ModuleType("display.lcd")
    for i, name in enumerate(
        [
            "BLACK",
            "GREEN",
            "RED",
            "LIGHTRED",
            "BLUE",
            "YELLOW",
            "GREY",
            "MAGENTA",
            "CYAN",
            "LIGHTGREEN",
            "DARKGREEN",
            "DARKBLUE",
            "ORANGE",
            "EVENT_A",
            "EVENT_B",
            "WHITE",
        ]
    ):
        setattr(mod, name, i)
    sys.modules["display.lcd"] = mod
    # Ensure package exists
    if "display" not in sys.modules:
        pkg = types.ModuleType("display")
        pkg.__path__ = [str(ROOT / "display")]  # type: ignore[attr-defined]
        sys.modules["display"] = pkg


def _install_writer_stub():
    mod = types.ModuleType("writer")

    class CWriter:
        @staticmethod
        def set_textpos(ssd, y, x):
            pass

        def __init__(self, *a, **k):
            pass

        def setcolor(self, *a, **k):
            return 0, 0

        def printstring(self, s):
            pass

    mod.CWriter = CWriter
    sys.modules["writer"] = mod


_install_machine_stub()
_install_lcd_colors_stub()
_install_writer_stub()
