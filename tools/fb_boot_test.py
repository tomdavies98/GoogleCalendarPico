# mpremote run tools/fb_boot_test.py
import gc
import sys

sys.path.append("lib")
gc.collect()
print("bare", gc.mem_free())

try:
    import network

    w = network.WLAN(network.STA_IF)
    w.active(False)
except Exception:
    pass
gc.collect()
print("radio off", gc.mem_free())

import config as cfg
import fb_slab

fb_slab.reserve()
print("after reserve", gc.mem_free())

from display.lcd import create_lcd, release_lcd, collect_after_lcd_release

print("after lcd import", gc.mem_free())
bus, ssd, writer = create_lcd(buf=fb_slab.get())
print("LCD ok", gc.mem_free())
ssd, writer = release_lcd(ssd, writer)
collect_after_lcd_release()
fb_slab.release()
print("done", gc.mem_free())
