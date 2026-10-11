# Run on Pico: mpremote run tools/mem_teardown_test.py
import gc
import sys

sys.path.append("lib")
gc.collect()
print("start free", gc.mem_free())

from display.lcd import create_lcd, release_lcd, collect_after_lcd_release

bus, ssd, writer = create_lcd()
print("with LCD", gc.mem_free())
ssd, writer = release_lcd(ssd, writer)
free = collect_after_lcd_release()
print("after release+collect", free)
assert free > 150000, "framebuffer still pinned"
bus = None
gc.collect()
print("ok after bus drop", gc.mem_free())
