# LCD bring-up for Waveshare Pico-ResTouch-LCD-3.5 using ILI9486 GS4 driver.

import gc
import sys
from machine import Pin, SPI, PWM

import config as cfg

sys.path.append("lib")
from ili9486 import ILI9486  # noqa: E402
from writer import CWriter  # noqa: E402
import fonts.arial10 as font  # noqa: E402


# Palette indices (4-bit GS4 LUT)
BLACK = 0
GREEN = 1
RED = 2
LIGHTRED = 3
BLUE = 4
YELLOW = 5
GREY = 6
MAGENTA = 7
CYAN = 8
LIGHTGREEN = 9
DARKGREEN = 10
DARKBLUE = 11
ORANGE = 12
EVENT_A = 13
EVENT_B = 14
WHITE = 15


class DisplayBus:
    """Shared SPI1 with baud switching for LCD vs touch."""

    def __init__(self):
        self.bl = PWM(Pin(cfg.PIN_LCD_BL))
        self.bl.freq(1000)
        self.bl.duty_u16(50000)

        self.dc = Pin(cfg.PIN_LCD_DC, Pin.OUT, value=0)
        self.cs = Pin(cfg.PIN_LCD_CS, Pin.OUT, value=1)
        self.rst = Pin(cfg.PIN_LCD_RST, Pin.OUT, value=1)
        self.tp_cs = Pin(cfg.PIN_TP_CS, Pin.OUT, value=1)
        self.tp_irq = Pin(cfg.PIN_TP_IRQ, Pin.IN, Pin.PULL_UP)

        self.spi = SPI(
            cfg.SPI_ID,
            cfg.SPI_BAUD_TOUCH,
            sck=Pin(cfg.PIN_LCD_CLK),
            mosi=Pin(cfg.PIN_LCD_MOSI),
            miso=Pin(cfg.PIN_LCD_MISO),
        )
        self._display_baud = cfg.SPI_BAUD_DISPLAY
        self._touch_baud = cfg.SPI_BAUD_TOUCH

    def use_display(self):
        self.tp_cs(1)
        self.spi.init(baudrate=self._display_baud)

    def use_touch(self):
        self.cs(1)
        self.spi.init(baudrate=self._touch_baud)


def create_lcd(bus=None, buf=None):
    """Bring up ILI9486. Pass buf= from fb_slab to avoid a post-import alloc."""
    if bus is None:
        bus = DisplayBus()

    ILI9486.COLOR_INVERT = 0xFFFF
    gc.collect()
    if buf is None:
        free = gc.mem_free()
        if free < 82000:
            print("WARNING: low RAM before LCD alloc:", free)
    bus.use_display()

    def init_spi(spi):
        spi.init(baudrate=cfg.SPI_BAUD_DISPLAY)

    madctl = getattr(cfg, "MADCTL", 0x48)
    if getattr(cfg, "DEBUG_ORIENT", False):
        print(
            "LCD create",
            cfg.WIDTH,
            "x",
            cfg.HEIGHT,
            "madctl",
            hex(madctl),
            "orient",
            getattr(cfg, "ORIENT", "?"),
        )
    ssd = ILI9486(
        bus.spi,
        bus.cs,
        bus.dc,
        bus.rst,
        height=cfg.HEIGHT,
        width=cfg.WIDTH,
        madctl=madctl,
        init_spi=init_spi,
        buf=buf,
    )

    CWriter.create_color(ssd, BLACK, 0, 0, 0)
    CWriter.create_color(ssd, GREEN, 0, 200, 80)
    CWriter.create_color(ssd, RED, 220, 50, 50)
    CWriter.create_color(ssd, LIGHTRED, 180, 80, 80)
    CWriter.create_color(ssd, BLUE, 60, 120, 220)
    CWriter.create_color(ssd, YELLOW, 230, 200, 40)
    CWriter.create_color(ssd, GREY, 90, 90, 100)
    CWriter.create_color(ssd, MAGENTA, 200, 60, 180)
    CWriter.create_color(ssd, CYAN, 40, 190, 200)
    CWriter.create_color(ssd, LIGHTGREEN, 80, 160, 100)
    CWriter.create_color(ssd, DARKGREEN, 20, 60, 40)
    CWriter.create_color(ssd, DARKBLUE, 20, 30, 55)
    CWriter.create_color(ssd, ORANGE, 230, 140, 40)
    CWriter.create_color(ssd, EVENT_A, 50, 100, 180)
    CWriter.create_color(ssd, EVENT_B, 70, 90, 160)
    CWriter.create_color(ssd, WHITE, 240, 240, 245)

    writer = CWriter(ssd, font, fgcolor=WHITE, bgcolor=DARKBLUE, verbose=False)
    writer.set_clip(True, True, False)
    return bus, ssd, writer


def release_lcd(ssd, writer):
    """
    Break references into the ~77KB GS4 buffer and return (None, None).

    Important: the *caller* must rebind its ssd/writer names to the returned
    Nones, then gc.collect(). Collecting inside this function cannot free the
    FrameBuffer while the caller still holds it.
    """
    try:
        from writer import Writer

        Writer.state.clear()
    except Exception:
        pass

    if writer is not None:
        try:
            writer.device = None
        except Exception:
            pass
        try:
            writer.font = None
        except Exception:
            pass
        try:
            writer.glyph = None
        except Exception:
            pass

    if ssd is not None:
        try:
            ssd.mvb = None
        except Exception:
            pass
        try:
            ssd._buf = None
        except Exception:
            pass
        try:
            ssd._linebuf = None
        except Exception:
            pass
        try:
            ssd._spi = None
        except Exception:
            pass
        try:
            ssd.palette = None
        except Exception:
            pass

    return None, None


def collect_after_lcd_release():
    """Call after caller has dropped ssd/writer/ui refs."""
    gc.collect()
    gc.collect()
    free = gc.mem_free()
    print("free after LCD release:", free)
    return free
