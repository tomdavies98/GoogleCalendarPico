# Wi-Fi connect and NTP sync for Pico W (CYW43).

import time
import network
import ntptime
import config as cfg

# Pico W / CYW43 link statuses (network.WLAN.status):
#   0 DOWN, 1 JOIN, 2 NOIP, 3 UP
#  -1 FAIL, -2 NONET, -3 BADAUTH
_STAT_NAMES = {
    0: "DOWN",
    1: "JOIN",
    2: "NOIP",
    3: "UP",
    -1: "FAIL",
    -2: "NONET",
    -3: "BADAUTH",
}


def _clean(s):
    if s is None:
        return None
    # Strip quotes/whitespace people paste into secrets.py
    s = str(s).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def connect(ssid, password, timeout_ms=None, retries=5):
    if timeout_ms is None:
        timeout_ms = cfg.WIFI_TIMEOUT_MS
    ssid = _clean(ssid)
    password = _clean(password)
    if not ssid:
        raise OSError("Wi-Fi SSID empty")

    wlan = network.WLAN(network.STA_IF)
    last_status = None

    for attempt in range(retries):
        try:
            # Full radio bounce — CYW43 often needs a long settle after soft-reset
            wlan.active(False)
            time.sleep_ms(400)
            wlan.active(True)
            time.sleep_ms(600)
            try:
                wlan.config(pm=0xA11140)  # keep awake while connecting
            except Exception:
                pass

            if wlan.isconnected():
                print("Wi-Fi already up:", wlan.ifconfig())
                return wlan

            print("Wi-Fi attempt", attempt + 1, "SSID=", repr(ssid))
            wlan.connect(ssid, password or "")
            start = time.ticks_ms()
            while not wlan.isconnected():
                st = wlan.status()
                if st != last_status:
                    print("WLAN status:", _STAT_NAMES.get(st, st))
                    last_status = st
                # Hard failures are negative on CYW43
                if isinstance(st, int) and st < 0:
                    break
                if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                    break
                time.sleep_ms(250)

            if wlan.isconnected():
                print("Wi-Fi OK:", wlan.ifconfig())
                return wlan
        except Exception as e:
            print("Wi-Fi attempt error:", e)

        try:
            wlan.disconnect()
        except Exception:
            pass
        wlan.active(False)
        time.sleep_ms(800)

    st = wlan.status()
    raise OSError(
        "WiFi fail {}".format(_STAT_NAMES.get(st, st))
    )


def is_connected():
    try:
        wlan = network.WLAN(network.STA_IF)
        return wlan.active() and wlan.isconnected()
    except Exception:
        return False


def radio_off():
    """Power down STA to reclaim driver/LWIP heap before large allocs."""
    try:
        wlan = network.WLAN(network.STA_IF)
        try:
            if wlan.active():
                wlan.active(False)
        except Exception:
            pass
    except Exception as e:
        print("radio_off:", e)


def sync_ntp(host=None, retries=4):
    if host is None:
        host = cfg.NTP_HOST
    ntptime.host = host
    last = None
    for _ in range(retries):
        try:
            ntptime.settime()
            try:
                import timeutil

                timeutil.persist_time()
            except Exception as e:
                print("persist_time", e)
            print("NTP OK", __import__("time").gmtime())
            return True
        except Exception as e:
            last = e
            time.sleep_ms(700)
    raise OSError("NTP failed: {}".format(last))
