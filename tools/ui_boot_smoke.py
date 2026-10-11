import gc
import sys

sys.path.append("lib")
gc.collect()
print("boot", gc.mem_free())
import fb_slab

fb_slab.reserve()
from display.lcd import create_lcd
from display.touch import Touch
from display.calendar_ui import CalendarUI

bus, ssd, writer = create_lcd(buf=fb_slab.get())
print("LCD OK", gc.mem_free())
ui = CalendarUI(ssd, writer, Touch(bus))
ui.set_events([])
ui.set_status("smoke ok")
ui.draw_if_dirty()
print("UI OK", gc.mem_free())
