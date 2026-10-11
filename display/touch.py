# XPT2046 resistive touch for Waveshare Pico-ResTouch-LCD-3.5.
# Tap-only: no drag/fling (toolbar buttons + event taps).

import time
import config as cfg


GESTURE_NONE = 0
GESTURE_TAP = 3
GESTURE_DOWN = 4
GESTURE_UP = 5


class Touch:
    def __init__(self, bus):
        self.bus = bus
        self.csn = bus.tp_cs
        self.irq = bus.tp_irq

        self._down = False
        self._sx = 0
        self._sy = 0
        self._lx = 0
        self._ly = 0
        self._t0 = 0
        self._use_irq = True
        self._irq_hits = 0
        self._polls = 0
        self._dbg_last = 0

    def _spi_touch(self):
        self.bus.cs(1)
        self.bus.spi.init(baudrate=cfg.SPI_BAUD_TOUCH)

    def _spi_display(self):
        self.csn(1)
        self.bus.spi.init(baudrate=cfg.SPI_BAUD_DISPLAY)

    def _read_axis(self, cmd):
        spi = self.bus.spi
        buf = bytearray(3)
        buf[0] = cmd
        try:
            spi.write_readinto(buf, buf)
            return ((buf[1] << 8) | buf[2]) >> 3
        except Exception:
            spi.write(bytearray([cmd]))
            data = spi.read(2)
            return ((data[0] << 8) | data[1]) >> 3

    def _is_idle_rail(self, raw_x, raw_y):
        return (raw_x <= 30 or raw_x >= 4060) and (raw_y <= 30 or raw_y >= 4060)

    def _sample_raw(self):
        self._polls += 1
        irq_low = self.irq.value() == 0
        if irq_low:
            self._irq_hits += 1

        if self._use_irq and self._polls > 40 and self._irq_hits == 0:
            print("TOUCH: no IRQ — ADC idle detection")
            self._use_irq = False

        if self._use_irq and not irq_low:
            return None

        self._spi_touch()
        self.csn(0)

        raw_x = self._read_axis(0xD0)
        raw_y = self._read_axis(0x90)
        if self._is_idle_rail(raw_x, raw_y):
            self.csn(1)
            self._spi_display()
            return None

        x_sum = raw_x
        y_sum = raw_y
        for _ in range(2):
            x_sum += self._read_axis(0xD0)
            y_sum += self._read_axis(0x90)
        self.csn(1)
        self._spi_display()

        raw_x = x_sum // 3
        raw_y = y_sum // 3

        if cfg.DEBUG_TOUCH:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._dbg_last) > 300:
                self._dbg_last = now
                x, y = self._map(raw_x, raw_y)
                print("TOUCH", raw_x, raw_y, "->", x, y, "irq", int(irq_low))

        return raw_x, raw_y

    def _map(self, raw_d0, raw_d90):
        # Landscape: D90→X, D0→Y with base Y invert (MADCTL 0x48 desk calib).
        # Portrait: same panel MADCTL; UI axes follow the 90° physical hold, so
        # swap ADC→screen pairing (TOUCH_SWAP_XY) instead of using MV in MADCTL.
        if getattr(cfg, "TOUCH_SWAP_XY", False):
            x = int((raw_d0 - cfg.TOUCH_RAW_MIN) * cfg.WIDTH / cfg.TOUCH_RAW_SPAN)
            y = cfg.HEIGHT - int(
                (raw_d90 - cfg.TOUCH_RAW_MIN) * cfg.HEIGHT / cfg.TOUCH_RAW_SPAN
            )
        else:
            x = int((raw_d90 - cfg.TOUCH_RAW_MIN) * cfg.WIDTH / cfg.TOUCH_RAW_SPAN)
            y = cfg.HEIGHT - int(
                (raw_d0 - cfg.TOUCH_RAW_MIN) * cfg.HEIGHT / cfg.TOUCH_RAW_SPAN
            )
        if cfg.TOUCH_FLIP_X:
            x = cfg.WIDTH - 1 - x
        if cfg.TOUCH_FLIP_Y:
            y = cfg.HEIGHT - 1 - y
        if x < 0:
            x = 0
        elif x >= cfg.WIDTH:
            x = cfg.WIDTH - 1
        if y < 0:
            y = 0
        elif y >= cfg.HEIGHT:
            y = cfg.HEIGHT - 1
        return x, y

    def _sample(self):
        raw = self._sample_raw()
        if raw is None:
            return None
        return self._map(raw[0], raw[1])

    def _evt(self, kind, x, y):
        return {
            "kind": kind,
            "x": x,
            "y": y,
            "sx": self._sx,
            "sy": self._sy,
        }

    def poll(self):
        now = time.ticks_ms()
        pt = self._sample()
        if pt is None:
            if self._down:
                self._down = False
                elapsed = time.ticks_diff(now, self._t0)
                dist = abs(self._ly - self._sy) + abs(self._lx - self._sx)
                if elapsed <= cfg.TOUCH_TAP_MAX_MS and dist <= cfg.TOUCH_TAP_SLOP_PX:
                    if cfg.DEBUG_TOUCH:
                        print("TAP", self._sx, self._sy, "dist", dist)
                    return self._evt(GESTURE_TAP, self._sx, self._sy)
                return self._evt(GESTURE_UP, self._lx, self._ly)
            return None

        x, y = pt
        if not self._down:
            self._down = True
            self._sx = self._lx = x
            self._sy = self._ly = y
            self._t0 = now
            return self._evt(GESTURE_DOWN, x, y)

        self._lx = x
        self._ly = y
        return None
