# Hardware stubs for unix MicroPython / on-device reset interception.
# Import and call install() before app code that may soft-reset.
# Avoids `import types` (not present on all Pico firmware builds).

import sys

_installed = False
reset_calls = []


class _Pin:
    IN = 0
    OUT = 1
    PULL_UP = 2

    def __init__(self, *a, **k):
        self._v = 1

    def __call__(self, v=None):
        if v is None:
            return self._v
        self._v = v
        return None

    def value(self, v=None):
        return self.__call__(v)

    def init(self, *a, **k):
        pass


class _SPI:
    def __init__(self, *a, **k):
        pass

    def init(self, *a, **k):
        pass

    def write(self, buf):
        pass

    def read(self, n, write=0):
        return bytes(n)

    def write_readinto(self, w, r):
        for i in range(len(r)):
            r[i] = 0


class _PWM:
    def __init__(self, *a, **k):
        pass

    def freq(self, *a, **k):
        pass

    def duty_u16(self, *a, **k):
        pass


class _RTC:
    def datetime(self, t=None):
        return None


class _WLAN:
    STA_IF = 0

    def __init__(self, *a, **k):
        pass

    def active(self, *a, **k):
        return False

    def isconnected(self):
        return False

    def status(self):
        return 0

    def connect(self, *a, **k):
        pass

    def disconnect(self):
        pass

    def ifconfig(self):
        return ("0.0.0.0", "0.0.0.0", "0.0.0.0", "0.0.0.0")

    def config(self, *a, **k):
        pass


class _Module:
    """Lightweight stand-in for types.ModuleType on firmware without `types`."""

    pass


def _make_module(name):
    try:
        import types

        return types.ModuleType(name)
    except ImportError:
        return _Module()


def trigger_reset():
    """Stand-in for machine.reset() — frozen machine modules often block setattr."""
    reset_calls.append(1)
    raise SystemExit("RESET")


def install():
    """Stub network/ntptime if missing; prepare reset interception."""
    global _installed

    try:
        import machine as real_machine

        # Prefer setattr; if frozen, scenarios call fake_hw.trigger_reset() instead.
        try:
            real_machine.reset = trigger_reset
        except (AttributeError, TypeError, OSError):
            pass
        machine = real_machine
    except ImportError:
        machine = _make_module("machine")
        machine.Pin = _Pin
        machine.SPI = _SPI
        machine.PWM = _PWM
        machine.RTC = _RTC
        machine.reset = trigger_reset
        sys.modules["machine"] = machine

    if "network" not in sys.modules:
        network = _make_module("network")
        network.WLAN = _WLAN
        network.STA_IF = 0
        sys.modules["network"] = network

    if "ntptime" not in sys.modules:
        ntptime = _make_module("ntptime")

        def settime():
            return None

        ntptime.settime = settime
        ntptime.host = "pool.ntp.org"
        sys.modules["ntptime"] = ntptime

    _installed = True
    reset_calls[:] = []
    return machine


def reset_was_called():
    return len(reset_calls) > 0
