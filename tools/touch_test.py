# Run on the Pico to verify touch mapping (upload then: import touch_test).
# Prints raw + mapped coords; draws a crosshair when pressed.

import sys
import time

sys.path.append("lib")

from display.lcd import create_lcd, BLACK, WHITE, RED, DARKBLUE
from display.touch import Touch
from writer import CWriter
import fonts.arial10 as font


def main():
    bus, ssd, writer = create_lcd()
    touch = Touch(bus)
    writer.setcolor(WHITE, DARKBLUE)
    print("Touch the screen. Ctrl+C to stop.")
    last = None
    while True:
        raw = touch._sample_raw()
        if raw is None:
            time.sleep_ms(50)
            continue
        x, y = touch._map(raw[0], raw[1])
        msg = "raw=({}, {}) -> ({}, {})".format(raw[0], raw[1], x, y)
        if msg != last:
            print(msg)
            last = msg
            ssd.fill(DARKBLUE)
            ssd.fill_rect(max(0, x - 4), y, 9, 1, RED)
            ssd.fill_rect(x, max(0, y - 4), 1, 9, RED)
            CWriter.set_textpos(ssd, 8, 8)
            writer.printstring("{},{}".format(x, y))
            ssd.show()
        time.sleep_ms(50)


if __name__ == "__main__":
    main()
