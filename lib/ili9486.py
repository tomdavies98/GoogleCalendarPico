# ILI9486 driver for Waveshare Pico-ResTouch-LCD-3.5 (SPI + shift register).
# Adapted from peterhinch/micropython-nano-gui (MIT).
# Sync-only: asyncio refresh path removed for lighter Pico W use.

from time import sleep_ms
import gc
import framebuf
from boolpalette import BoolPalette


@micropython.viper
def _lcopy(dest: ptr16, source: ptr8, lut: ptr16, length: int, gscale: bool):
    n = 0
    x = 0
    while length:
        c = source[x]
        p = c >> 4
        q = c & 0x0F
        if gscale:
            dest[n] = p >> 1 | p << 4 | p << 9 | ((p & 0x01) << 15)
            n += 1
            dest[n] = q >> 1 | q << 4 | q << 9 | ((q & 0x01) << 15)
            n += 1
        else:
            dest[n] = lut[p]
            n += 1
            dest[n] = lut[q]
            n += 1
        x += 1
        length -= 1


@micropython.viper
def _lscopy(dest: ptr16, source: ptr8, lut: ptr16, ch: int, gscale: bool):
    col = ch & 0x1FF
    height = (ch >> 9) & 0x1FF
    wbytes = ch >> 19
    n = 0
    clsb = col & 1
    idx = col >> 1
    while height:
        if clsb:
            c = source[idx] & 0x0F
        else:
            c = source[idx] >> 4
        dest[n] = (
            c >> 1 | c << 4 | c << 9 | ((c & 0x01) << 15) if gscale else lut[c]
        )
        n += 1
        idx += wbytes
        height -= 1


class ILI9486(framebuf.FrameBuffer):
    lut = bytearray(32)
    COLOR_INVERT = 0

    @classmethod
    def rgb(cls, r, g, b):
        return cls.COLOR_INVERT ^ (
            (r & 0xF8) | ((g & 0xE0) >> 5) | ((g & 0x1C) << 11) | ((b & 0xF8) << 5)
        )

    def __init__(
        self,
        spi,
        cs,
        dc,
        rst,
        height=320,
        width=480,
        usd=False,
        mirror=False,
        madctl=None,
        init_spi=False,
        buf=None,
    ):
        self._spi = spi
        self._cs = cs
        self._dc = dc
        self._rst = rst
        self.height = height
        self.width = width
        self._long = max(height, width)
        self._short = min(height, width)
        self._spi_init = init_spi
        self._gscale = False
        self.mode = framebuf.GS4_HMSB
        self.palette = BoolPalette(self.mode)
        need = height * width // 2
        if buf is None:
            gc.collect()
            buf = bytearray(need)
        elif len(buf) < need:
            raise ValueError("frame buf too small")
        self._buf = buf
        self.mvb = memoryview(buf)
        super().__init__(buf, width, height, self.mode)
        self._linebuf = bytearray(self._short * 2)

        self._rst(0)
        sleep_ms(50)
        self._rst(1)
        sleep_ms(50)
        if self._spi_init:
            self._spi_init(spi)

        self._wcmd(b"\x01")
        sleep_ms(100)
        self._wcmd(b"\x11")
        sleep_ms(20)
        self._wcd(b"\x3a", b"\x55")
        if self._short != 320:
            self._wcd(b"\x2a", int.to_bytes(self._short - 1, 4, "big"))
        if self._long != 480:
            self._wcd(b"\x2b", int.to_bytes(self._long - 1, 4, "big"))
        if madctl is None:
            madctl = 0x48 if usd else 0x88
            if mirror:
                madctl ^= 0x80
        self._wcd(b"\x36", int(madctl).to_bytes(1, "big"))
        self._wcmd(b"\x11")
        self._wcmd(b"\x29")

    def _wcmd(self, command):
        self._dc(0)
        self._cs(0)
        self._spi.write(command)
        self._cs(1)

    def _wcd(self, command, data):
        self._dc(0)
        self._cs(0)
        self._spi.write(command)
        self._cs(1)
        self._dc(1)
        self._cs(0)
        self._spi.write(data)
        self._cs(1)

    def greyscale(self, gs=None):
        if gs is not None:
            self._gscale = gs
        return self._gscale

    def show(self):
        clut = ILI9486.lut
        lb = self._linebuf
        buf = self.mvb
        cm = self._gscale
        if self._spi_init:
            self._spi_init(self._spi)
        self._wcmd(b"\x2c")
        self._dc(1)
        self._cs(0)
        if self.width < self.height:
            wd = self.width // 2
            ht = self.height
            for start in range(0, wd * ht, wd):
                _lcopy(lb, buf[start:], clut, wd, cm)
                self._spi.write(lb)
        else:
            width = self.width
            wd = width - 1
            cargs = (self.height << 9) + (width << 18)
            for col in range(width):
                _lscopy(lb, buf, clut, wd - col + cargs, cm)
                self._spi.write(lb)
        self._cs(1)
