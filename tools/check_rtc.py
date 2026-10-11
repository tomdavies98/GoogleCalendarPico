import subprocess
import sys
import time

import serial
from serial.tools import list_ports

ports = [p.device for p in list_ports.comports() if "2E8A" in (p.hwid or "")]
if not ports:
    raise SystemExit("no pico")
port = ports[0]
print("port", port)

code = r"""
import time, timeutil
print("epoch", time.time())
print("gm", time.gmtime()[:6])
print("sane", timeutil.rtc_is_sane())
mon = timeutil.monday_midnight_utc()
print("week0", timeutil.format_week_label(mon))
print("week1", timeutil.format_week_label(mon + 7 * 86400))
print("today", timeutil.format_day_short(timeutil.local_midnight_utc()))
try:
    print("stamp", open("rtc_stamp.txt").read())
except Exception as e:
    print("no stamp", e)
"""
subprocess.run([sys.executable, "-m", "mpremote", "connect", port, "exec", code])
subprocess.run([sys.executable, "-m", "mpremote", "connect", port, "reset"])
time.sleep(2.5)
s = serial.Serial(port, 115200, timeout=0.4)
deadline = time.time() + 16
while time.time() < deadline:
    chunk = s.read(4096)
    if chunk:
        print(chunk.decode("utf-8", errors="replace"), end="")
s.close()
