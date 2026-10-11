"""Wait for BOOTSEL or a live REPL, then flash + deploy."""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]
UF2 = ROOT / "tools" / "RPI_PICO_W-20260824-v1.29.0.uf2"
DEPLOY = ROOT / "tools" / "deploy_to_pico.py"


def find_bootsel() -> Path | None:
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = Path(f"{letter}:/")
        if (root / "INFO_UF2.TXT").exists():
            return root
    return None


def probe() -> bool:
    ports = [p.device for p in list_ports.comports() if "2E8A" in (p.hwid or "")]
    if not ports:
        return False
    try:
        s = serial.Serial(ports[0], 115200, timeout=0.35)
        time.sleep(0.15)
        s.reset_input_buffer()
        s.write(b"\x03\x03\x01")
        time.sleep(0.5)
        rx = s.read(4096)
        s.close()
        if b"raw REPL" in rx or b"MicroPython" in rx or b">>>" in rx:
            print("REPL_OK", ports[0], repr(rx[:120]))
            return True
    except Exception as exc:
        print("probe", exc)
    return False


def flash_and_wait(drive: Path) -> None:
    info = (drive / "INFO_UF2.TXT").read_text(errors="replace")
    print("BOOTSEL", drive)
    print(info[:300])
    shutil.copy2(UF2, drive / UF2.name)
    print("UF2 copied, waiting reboot")
    for _ in range(80):
        time.sleep(0.5)
        if not (drive / "INFO_UF2.TXT").exists():
            break
    time.sleep(4)
    for _ in range(50):
        if any("2E8A" in (p.hwid or "") for p in list_ports.comports()):
            break
        time.sleep(0.4)
    time.sleep(2)


def main() -> int:
    wait_s = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    print(f"Watching {wait_s}s for BOOTSEL or live REPL...")
    deadline = time.time() + wait_s
    last = 0
    while time.time() < deadline:
        drive = find_bootsel()
        if drive:
            flash_and_wait(drive)
            r = subprocess.run([sys.executable, str(DEPLOY)])
            print("deploy exit", r.returncode)
            return r.returncode
        if probe():
            r = subprocess.run([sys.executable, str(DEPLOY)])
            print("deploy exit", r.returncode)
            return r.returncode
        now = int(time.time())
        if now - last >= 15:
            ports = [
                p.device
                for p in list_ports.comports()
                if "2E8A" in (p.hwid or "")
            ]
            left = int(deadline - time.time())
            print(f"...still waiting ({left}s left) ports={ports}")
            last = now
        time.sleep(0.5)
    print("TIMEOUT")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
