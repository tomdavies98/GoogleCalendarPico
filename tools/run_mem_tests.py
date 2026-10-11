#!/usr/bin/env python3
"""
Run Pico-like memory / nav tests.

  python tools/run_mem_tests.py           # host pytest + unix MicroPython if available
  python tools/run_mem_tests.py --device  # also run scenarios on Pico via mpremote

Env:
  MICROPY   path to micropython binary (default: micropython on PATH)
  HEAPSIZE  unix -X heapsize= (default: 190000)
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_TESTS = ROOT / "tests" / "host"
UPY_DIR = ROOT / "tests" / "upy"
SCENARIOS = sorted(UPY_DIR.glob("scenario_*.py"))
DEFAULT_HEAP = 190000


def _run(cmd, cwd=None, env=None) -> subprocess.CompletedProcess:
    print("+", " ".join(str(c) for c in cmd))
    return subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def run_host_pytest() -> tuple[bool, str]:
    try:
        import pytest  # noqa: F401
    except ImportError:
        return False, "pytest not installed (skip host tests)"
    r = _run([sys.executable, "-m", "pytest", str(HOST_TESTS), "-q", "--tb=line"])
    out = (r.stdout or "") + (r.stderr or "")
    print(out, end="")
    return r.returncode == 0, out.strip() or ("ok" if r.returncode == 0 else "failed")


def find_micropython() -> str | None:
    env = os.environ.get("MICROPY")
    if env and Path(env).exists():
        return env
    return shutil.which("micropython")


def run_unix_scenario(mpy: str, scenario: Path, heap: int) -> tuple[bool, str, int | None]:
    env = os.environ.copy()
    # Prefer project modules
    env["MICROPYPATH"] = str(ROOT) + ":" + str(ROOT / "lib") + ":" + str(UPY_DIR)
    cmd = [mpy, "-X", "heapsize={}".format(heap), str(scenario)]
    r = _run(cmd, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    print(out, end="")
    free = None
    m = re.findall(r"FREE \S+ (\d+)", out)
    if m:
        free = min(int(x) for x in m)
    ok = r.returncode == 0 and "PASS scenario_" in out
    return ok, out.strip().splitlines()[-1] if out.strip() else "no output", free


def find_pico_port() -> str | None:
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    for p in list_ports.comports():
        if "2E8A" in (p.hwid or ""):
            return p.device
    return None


def run_device_scenarios(port: str) -> list[tuple[str, bool, str]]:
    results = []
    _run(
        [
            sys.executable,
            "-m",
            "mpremote",
            "connect",
            port,
            "mkdir",
            ":upy_test",
        ]
    )
    for name in ("fake_hw.py", "mem_harness.py"):
        src = UPY_DIR / name
        r = _run(
            [
                sys.executable,
                "-m",
                "mpremote",
                "connect",
                port,
                "cp",
                str(src),
                ":upy_test/{}".format(name),
            ]
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "")[-200:]
            results.append((name, False, "copy failed: " + err))
            return results

    for scenario in SCENARIOS:
        r = _run(
            [
                sys.executable,
                "-m",
                "mpremote",
                "connect",
                port,
                "run",
                str(scenario),
            ]
        )
        out = (r.stdout or "") + (r.stderr or "")
        print(out, end="")
        ok = r.returncode == 0 and "PASS scenario_" in out
        last = out.strip().splitlines()[-1] if out.strip() else "no output"
        results.append((scenario.name, ok, last))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--device",
        action="store_true",
        help="Also run scenarios on a connected Pico via mpremote",
    )
    ap.add_argument(
        "--heap",
        type=int,
        default=int(os.environ.get("HEAPSIZE", DEFAULT_HEAP)),
        help="unix MicroPython heapsize (default %(default)s)",
    )
    ap.add_argument("--skip-host", action="store_true", help="Skip CPython pytest")
    ap.add_argument("--skip-unix", action="store_true", help="Skip unix MicroPython")
    ap.add_argument(
        "--require-unix",
        action="store_true",
        help="Fail if unix MicroPython binary is missing",
    )
    args = ap.parse_args()

    rows = []
    failed = 0

    if not args.skip_host:
        ok, detail = run_host_pytest()
        skipped = "not installed" in detail.lower()
        rows.append(("host pytest", ok or skipped, detail[:80], None))
        if not ok and not skipped:
            failed += 1

    if not args.skip_unix:
        mpy = find_micropython()
        if not mpy:
            msg = "micropython not found (set MICROPY=...)"
            if args.require_unix:
                rows.append(("unix micropython", False, msg, None))
                failed += 1
            else:
                rows.append(("unix micropython", True, "SKIP " + msg, None))
                print("WARN:", msg)
        else:
            for sc in SCENARIOS:
                ok, detail, free = run_unix_scenario(mpy, sc, args.heap)
                rows.append((sc.name + " (unix)", ok, detail[:80], free))
                if not ok:
                    failed += 1

    if args.device:
        port = find_pico_port()
        if not port:
            rows.append(("device", False, "no Pico (VID 2E8A) on COM ports", None))
            failed += 1
        else:
            print("Using device", port)
            for name, ok, detail in run_device_scenarios(port):
                rows.append((name + " (device)", ok, detail[:80], None))
                if not ok:
                    failed += 1

    print()
    print("{:<36} {:<6} {:>8}  {}".format("TEST", "RESULT", "MINFREE", "DETAIL"))
    print("-" * 80)
    for name, ok, detail, free in rows:
        print(
            "{:<36} {:<6} {:>8}  {}".format(
                name,
                "PASS" if ok else "FAIL",
                free if free is not None else "-",
                detail,
            )
        )

    if failed:
        print("\n{} test(s) failed".format(failed))
        return 1
    print("\nAll tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
