"""
Deploy GoogleCalendarPico to a Pico W.

Usage:
  1) Close Thonny
  2) Hold BOOTSEL, plug USB, release (RPI-RP2 drive appears)  OR just plug if already running
  3) python tools/deploy_to_pico.py
"""
from __future__ import annotations

import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
UF2 = ROOT / "tools" / "RPI_PICO_W-20260824-v1.29.0.uf2"
UF2_URL = "https://micropython.org/resources/firmware/RPI_PICO_W-20260824-v1.29.0.uf2"

# Project files for the Pico filesystem (not PC-only tools)
UPLOAD = [
    "main.py",
    "config.py",
    "secrets.py",
    "orient.py",
    "gcal.py",
    "timeutil.py",
    "wifiutil.py",
    "event_cache.py",
    "fb_slab.py",
    "display/__init__.py",
    "display/lcd.py",
    "display/touch.py",
    "display/calendar_ui.py",
    "lib/__init__.py",
    "lib/ili9486.py",
    "lib/writer.py",
    "lib/boolpalette.py",
    "lib/fonts/__init__.py",
    "lib/fonts/arial10.py",
]


def find_rp2_drive():
    from string import ascii_uppercase

    for letter in ascii_uppercase:
        root = pathlib.Path(f"{letter}:/")
        info = root / "INFO_UF2.TXT"
        if info.exists():
            try:
                text = info.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "UF2" in text or "RP2" in text:
                return root
    return None


def ensure_uf2():
    if UF2.exists() and UF2.stat().st_size > 1_000_000:
        return UF2
    import urllib.request

    print("Downloading", UF2_URL)
    UF2.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(UF2_URL, UF2)
    return UF2


def flash_uf2(drive: pathlib.Path):
    uf2 = ensure_uf2()
    dest = drive / uf2.name
    print(f"Flashing {uf2.name} -> {drive}")
    shutil.copy2(uf2, dest)
    print("UF2 copied — waiting for reboot...")
    # Drive disappears when reboot starts
    for _ in range(40):
        time.sleep(0.5)
        if not (drive / "INFO_UF2.TXT").exists():
            break
    time.sleep(2)


def wait_com(timeout=40):
    import serial.tools.list_ports as lp

    t0 = time.time()
    while time.time() - t0 < timeout:
        for p in lp.comports():
            if p.vid == 0x2E8A and p.device.upper() != "COM1":
                return p.device
        time.sleep(0.5)
    return None


def mpremote_upload(port: str):
    import subprocess

    def run(args):
        cmd = [sys.executable, "-m", "mpremote", "connect", port, *args]
        print("+", " ".join(cmd))
        subprocess.check_call(cmd, cwd=ROOT)

    run(
        [
            "exec",
            "import os\n"
            "def ensure(p):\n"
            "  try:\n"
            "    os.mkdir(p)\n"
            "  except OSError:\n"
            "    pass\n"
            "ensure('display')\n"
            "ensure('lib')\n"
            "ensure('lib/fonts')\n",
        ]
    )
    for rel in UPLOAD:
        src = ROOT / rel
        if not src.exists():
            print("SKIP missing", rel)
            continue
        run(["cp", str(src), f":{rel}"])
    run(["reset"])
    print("Deploy complete.")


def main():
    print("Looking for RPI-RP2 (BOOTSEL) or running Pico W...")
    drive = find_rp2_drive()
    if drive:
        print("Found bootloader at", drive)
        flash_uf2(drive)
    else:
        print("No RPI-RP2 drive — assuming MicroPython already running.")

    port = wait_com()
    if not port:
        print("ERROR: No Pico serial port (2e8a:****).")
        print("Hold BOOTSEL, plug USB, release, then re-run this script.")
        sys.exit(1)
    print("Using", port)
    # Give CDC a moment after flash
    time.sleep(2)
    try:
        mpremote_upload(port)
    except Exception as e:
        print("Upload failed:", e)
        print("Open Thonny, connect once (Ctrl+C at prompt), close Thonny, re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
