"""Upload key firmware files when mpremote cannot enter raw REPL cleanly."""
import pathlib
import sys
import time

import serial
from serial.tools import list_ports

PORT = "COM3"
ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = [
    ("main.py", "main.py"),
    ("display/calendar_ui.py", "display/calendar_ui.py"),
    ("config.py", "config.py"),
    ("gcal.py", "gcal.py"),
]


def wait_port(name, timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        ports = [p.device for p in list_ports.comports()]
        if name in ports:
            return True
        time.sleep(0.2)
    return False


def read_all(s, wait=0.05):
    time.sleep(wait)
    out = b""
    while s.in_waiting:
        out += s.read(s.in_waiting)
        time.sleep(0.02)
    return out


def hard_usb_kick():
    """Close/reopen with DTR dance to force MicroPython restart."""
    try:
        s = serial.Serial(PORT, 115200, timeout=0.2)
        s.dtr = False
        s.rts = True
        time.sleep(0.15)
        s.close()
    except Exception as e:
        print("kick1", e)
    time.sleep(1.5)
    wait_port(PORT)
    try:
        s = serial.Serial(PORT, 115200, timeout=0.5)
        # Drain boot banner
        time.sleep(1.0)
        banner = read_all(s, 0.2)
        print("banner", banner[-200:])
        s.close()
        return banner
    except Exception as e:
        print("kick2", e)
        return b""


def enter_raw(s):
    # Multiple interrupt attempts then raw REPL
    for _ in range(5):
        s.write(b"\r\x03")
        time.sleep(0.1)
    read_all(s)
    s.write(b"\x01")
    time.sleep(0.4)
    r = read_all(s)
    if b"raw REPL" in r:
        return r
    # Soft reboot then raw
    s.write(b"\x04")
    time.sleep(2.0)
    read_all(s, 0.3)
    for _ in range(3):
        s.write(b"\x03")
        time.sleep(0.1)
    s.write(b"\x01")
    time.sleep(0.5)
    return read_all(s)


def exec_cmd(s, cmd, timeout=6):
    data = cmd.encode("utf-8") if isinstance(cmd, str) else cmd
    s.write(data)
    s.write(b"\x04")
    t0 = time.time()
    out = b""
    while time.time() - t0 < timeout:
        chunk = s.read(s.in_waiting or 1)
        if chunk:
            out += chunk
            if b"\x04>" in out:
                break
        else:
            time.sleep(0.02)
    return out


def main():
    print("usb kick...")
    hard_usb_kick()
    time.sleep(0.5)
    s = serial.Serial(PORT, 115200, timeout=0.25, write_timeout=2)
    print("opened", PORT)
    r = enter_raw(s)
    print("raw:", r[:200])
    if b"raw REPL" not in r:
        print("FAILED to enter raw REPL — unplug Pico USB and retry")
        s.close()
        sys.exit(2)

    out = exec_cmd(
        s,
        "import os\n"
        "try:\n"
        " os.mkdir('display')\n"
        "except OSError:\n"
        " pass\n",
    )
    print("mkdir", b"OK" in out, out[-60:])

    for local, remote in FILES:
        content = (ROOT / local).read_bytes()
        print("writing", remote, len(content))
        out = exec_cmd(s, "f=open(%r,'wb')\n" % remote)
        if b"OK" not in out:
            print("open fail", out)
            sys.exit(1)
        chunk = 180
        for i in range(0, len(content), chunk):
            part = content[i : i + chunk]
            hx = part.hex()
            cmd = "f.write(bytes.fromhex(%r))\n" % hx
            out = exec_cmd(s, cmd, timeout=8)
            if b"OK" not in out:
                print("chunk fail at", i, out[-120:])
                sys.exit(1)
        out = exec_cmd(s, "f.close()\n")
        print(" closed", remote, b"OK" in out)

    exec_cmd(s, "import machine; machine.reset()\n", timeout=2)
    try:
        s.close()
    except Exception:
        pass
    print("ALL DONE")


if __name__ == "__main__":
    main()
