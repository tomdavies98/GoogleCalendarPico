# writer.py — Writer / CWriter for bitmap fonts on FrameBuffer devices.
# Adapted from peterhinch/micropython-nano-gui (MIT).

import framebuf
from uctypes import bytearray_at, addressof

__version__ = (0, 5, 2)


class DisplayState:
    def __init__(self):
        self.text_row = 0
        self.text_col = 0


def _get_id(device):
    if not isinstance(device, framebuf.FrameBuffer):
        raise ValueError("Device must be derived from FrameBuffer.")
    return id(device)


class Writer:
    state = {}

    @staticmethod
    def set_textpos(device, row=None, col=None):
        devid = _get_id(device)
        if devid not in Writer.state:
            Writer.state[devid] = DisplayState()
        s = Writer.state[devid]
        if row is not None:
            if row < 0 or row >= device.height:
                raise ValueError("row is out of range")
            s.text_row = row
        if col is not None:
            if col < 0 or col >= device.width:
                raise ValueError("col is out of range")
            s.text_col = col
        return s.text_row, s.text_col

    def __init__(self, device, font, verbose=False):
        self.devid = _get_id(device)
        self.device = device
        if self.devid not in Writer.state:
            Writer.state[self.devid] = DisplayState()
        self.font = font
        if font.height() >= device.height or font.max_width() >= device.width:
            raise ValueError("Font too large for screen")
        if font.hmap():
            self.map = framebuf.MONO_HMSB if font.reverse() else framebuf.MONO_HLSB
        else:
            raise ValueError("Font must be horizontally mapped.")
        self.screenwidth = device.width
        self.screenheight = device.height
        self.bgcolor = 0
        self.fgcolor = 1
        self.row_clip = True
        self.col_clip = True
        self.wrap = False
        self.cpos = 0
        self.tab = 4
        self.glyph = None
        self.char_height = 0
        self.char_width = 0

    def _getstate(self):
        return Writer.state[self.devid]

    def _newline(self):
        s = self._getstate()
        height = self.font.height()
        s.text_row += height
        s.text_col = 0

    def set_clip(self, row_clip=None, col_clip=None, wrap=None):
        if row_clip is not None:
            self.row_clip = row_clip
        if col_clip is not None:
            self.col_clip = col_clip
        if wrap is not None:
            self.wrap = wrap
        return self.row_clip, self.col_clip, self.wrap

    @property
    def height(self):
        return self.font.height()

    def printstring(self, string, invert=False):
        for char in string:
            if char == "\n":
                self._printchar("\n")
            else:
                self._printchar(char, invert)

    def stringlen(self, string, oh=False):
        if not len(string):
            return 0
        sc = self._getstate().text_col
        wd = self.screenwidth
        l = 0
        for char in string[:-1]:
            _, _, char_width = self.font.get_ch(char)
            l += char_width
            if oh and l + sc > wd:
                return True
        char = string[-1]
        _, _, char_width = self.font.get_ch(char)
        l += char_width
        return l + sc > wd if oh else l

    def _get_char(self, char, recurse):
        if not recurse:
            if char == "\n":
                self.cpos = 0
            elif char == "\t":
                nspaces = self.tab - (self.cpos % self.tab)
                if nspaces == 0:
                    nspaces = self.tab
                while nspaces:
                    nspaces -= 1
                    self._printchar(" ", recurse=True)
                self.glyph = None
                return

        self.glyph = None
        if char == "\n":
            self._newline()
            return
        glyph, char_height, char_width = self.font.get_ch(char)
        s = self._getstate()
        if s.text_row + char_height > self.screenheight:
            if self.row_clip:
                return
            self._newline()
        if s.text_col + char_width - self.screenwidth > 0:
            if self.col_clip or self.wrap:
                return
            self._newline()
        self.glyph = glyph
        self.char_height = char_height
        self.char_width = char_width

    def _printchar(self, char, invert=False, recurse=False):
        s = self._getstate()
        self._get_char(char, recurse)
        if self.glyph is None:
            return
        buf = bytearray(self.glyph)
        if invert:
            for i, v in enumerate(buf):
                buf[i] = 0xFF & ~v
        fbc = framebuf.FrameBuffer(buf, self.char_width, self.char_height, self.map)
        self.device.blit(fbc, s.text_col, s.text_row)
        s.text_col += self.char_width
        self.cpos += 1

    def setcolor(self, *_):
        return self.fgcolor, self.bgcolor


class CWriter(Writer):
    @staticmethod
    def create_color(ssd, idx, r, g, b):
        c = ssd.rgb(r, g, b)
        if not hasattr(ssd, "lut"):
            return c
        if not 0 <= idx <= 15:
            raise ValueError("Color nos must be 0..15")
        x = idx << 1
        ssd.lut[x] = c & 0xFF
        ssd.lut[x + 1] = c >> 8
        return idx

    def __init__(self, device, font, fgcolor=None, bgcolor=None, verbose=False):
        if not hasattr(device, "palette"):
            raise OSError("Incompatible device driver.")
        super().__init__(device, font, verbose)
        if bgcolor is not None:
            self.bgcolor = bgcolor
        if fgcolor is not None:
            self.fgcolor = fgcolor
        self.def_bgcolor = self.bgcolor
        self.def_fgcolor = self.fgcolor

    def _printchar(self, char, invert=False, recurse=False):
        s = self._getstate()
        self._get_char(char, recurse)
        if self.glyph is None:
            return
        buf = bytearray_at(addressof(self.glyph), len(self.glyph))
        fbc = framebuf.FrameBuffer(buf, self.char_width, self.char_height, self.map)
        palette = self.device.palette
        palette.bg(self.fgcolor if invert else self.bgcolor)
        palette.fg(self.bgcolor if invert else self.fgcolor)
        self.device.blit(fbc, s.text_col, s.text_row, -1, palette)
        s.text_col += self.char_width
        self.cpos += 1

    def setcolor(self, fgcolor=None, bgcolor=None):
        if fgcolor is None and bgcolor is None:
            self.fgcolor = self.def_fgcolor
            self.bgcolor = self.def_bgcolor
        else:
            if fgcolor is not None:
                self.fgcolor = fgcolor
            if bgcolor is not None:
                self.bgcolor = bgcolor
        return self.fgcolor, self.bgcolor
