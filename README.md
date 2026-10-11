# Google Calendar Pico

MicroPython desk calendar for a **Raspberry Pi Pico W** seated on a **[Waveshare Pico-ResTouch-LCD-3.5](https://www.waveshare.com/pico-restouch-lcd-3.5.htm)**.

- Day and week agenda views with a GS4 framebuffer (~77 KB — fits Pico W RAM)
- Google Calendar sync over Wi‑Fi (soft-reset between network and UI)
- Toolbar: Day / Week / scroll / **V**↔**H** orientation / Now
- Works in **demo mode** without secrets (sample events)

## Hardware

| Item | Notes |
|------|--------|
| Raspberry Pi Pico W | MicroPython with `network` + SSL |
| Waveshare Pico-ResTouch-LCD-3.5 | Seat Pico with USB toward the microSD slot |

| Signal | GPIO |
|--------|------|
| LCD_DC | 8 |
| LCD_CS | 9 |
| CLK / MOSI / MISO | 10 / 11 / 12 |
| Backlight | 13 |
| RST | 15 |
| TP_CS / TP_IRQ | 16 / 17 |

## Repo layout

| Path | Where it runs |
|------|----------------|
| `main.py`, `config.py`, `orient.py`, `gcal.py`, … | **Pico** firmware |
| `display/`, `lib/` | **Pico** |
| `secrets.example.py` → copy to `secrets.py` | **Pico** (local only; gitignored) |
| `tools/` | **PC** helpers (deploy, OAuth, tests) |
| `tests/` | **PC** / optional device harness — do not copy for normal desk use |

## 1. Flash MicroPython

1. Download a recent **Pico W** UF2 from [micropython.org/download](https://micropython.org/download/RPI_PICO_W/).
2. Hold **BOOTSEL**, plug USB, release — an `RPI-RP2` drive appears.
3. Copy the `.uf2` onto that drive; the board reboots into MicroPython.

Optional one-shot helper (downloads UF2 if needed, then uploads project files):

```bash
pip install -r requirements-pc.txt
# Close Thonny first
python tools/deploy_to_pico.py
```

## 2. Files to copy onto the Pico

Copy these to the board root with [Thonny](https://thonny.org/) or `mpremote` (keep folder structure):

```text
main.py
config.py
secrets.py          # create from secrets.example.py — see below
orient.py
gcal.py
timeutil.py
wifiutil.py
event_cache.py
fb_slab.py
display/
  __init__.py
  lcd.py
  touch.py
  calendar_ui.py
lib/
  __init__.py
  ili9486.py
  writer.py
  boolpalette.py
  fonts/
    __init__.py
    arial10.py
```

**Do not** copy to the Pico for normal use: `tools/`, `tests/`, `README.md`, `LICENSE`, `requirements-pc.txt`, `*.uf2`, `client_secret.json`.

Example with `mpremote` (adjust COM port):

```bash
python -m mpremote connect COM3 mkdir :display
python -m mpremote connect COM3 mkdir :lib
python -m mpremote connect COM3 mkdir :lib/fonts
python -m mpremote connect COM3 cp main.py :main.py
python -m mpremote connect COM3 cp config.py :config.py
python -m mpremote connect COM3 cp secrets.py :secrets.py
python -m mpremote connect COM3 cp orient.py :orient.py
python -m mpremote connect COM3 cp gcal.py :gcal.py
python -m mpremote connect COM3 cp timeutil.py :timeutil.py
python -m mpremote connect COM3 cp wifiutil.py :wifiutil.py
python -m mpremote connect COM3 cp event_cache.py :event_cache.py
python -m mpremote connect COM3 cp fb_slab.py :fb_slab.py
python -m mpremote connect COM3 cp display/__init__.py :display/__init__.py
python -m mpremote connect COM3 cp display/lcd.py :display/lcd.py
python -m mpremote connect COM3 cp display/touch.py :display/touch.py
python -m mpremote connect COM3 cp display/calendar_ui.py :display/calendar_ui.py
python -m mpremote connect COM3 cp lib/__init__.py :lib/__init__.py
python -m mpremote connect COM3 cp lib/ili9486.py :lib/ili9486.py
python -m mpremote connect COM3 cp lib/writer.py :lib/writer.py
python -m mpremote connect COM3 cp lib/boolpalette.py :lib/boolpalette.py
python -m mpremote connect COM3 cp lib/fonts/__init__.py :lib/fonts/__init__.py
python -m mpremote connect COM3 cp lib/fonts/arial10.py :lib/fonts/arial10.py
python -m mpremote connect COM3 reset
```

Or use `python tools/deploy_to_pico.py` after `secrets.py` exists locally.

## 3. Google Calendar setup (PC)

The Pico uses an OAuth **refresh token** (no browser on-device). Do this once on a computer:

### A. Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create (or select) a project.
3. Enable **Google Calendar API** for that project.
4. **APIs & Services → OAuth consent screen**
   - User type: **External** is fine for personal use.
   - While the app is in **Testing**, add your Google account under **Test users**.
5. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Download the JSON (often named like `client_secret_….json`).

### B. Get a refresh token

```bash
pip install -r requirements-pc.txt
python tools/get_refresh_token.py --secrets path/to/client_secret.json
```

Sign in when the browser opens, accept Calendar read-only access. The script prints:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

Keep the downloaded JSON **off** the Pico and **out of git** (already gitignored as `client_secret*.json`).

### C. Create `secrets.py`

```bash
cp secrets.example.py secrets.py
```

Edit `secrets.py`:

```python
WIFI_SSID = "Your_Network_Name"
WIFI_PASSWORD = "Your_WiFi_Password"

GOOGLE_CLIENT_ID = "….apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-…"
GOOGLE_REFRESH_TOKEN = "1//…"
GOOGLE_CALENDAR_ID = "primary"   # or another calendar id / email
```

Upload `secrets.py` to the Pico. Without it, the app runs **demo mode** with sample events.

## 4. First boot

1. Close Thonny / disconnect any REPL that holds the serial port.
2. Power or reset the Pico.
3. Typical flow: Wi‑Fi → NTP → fetch week → soft-reset → UI from cache.
4. Soft-reset drops the serial session briefly; that is normal.

If the screen stays black, reconnect with `mpremote` / serial and check for `MemoryError` or Wi‑Fi errors. Ensure all firmware files above are present (especially `orient.py` and `fb_slab.py`).

## UI

| Control | Action |
|---------|--------|
| **Day** / **Week** | Switch agenda layouts |
| **^** / **v** | Scroll |
| **V** / **H** | Vertical (portrait 320×480) ↔ horizontal (landscape 480×320); soft-reboots |
| **Now** | Jump to today / this week |
| Tap weekday header (week) | Open that day |
| Tap event | Detail overlay |

Orientation is stored in `orient.flag`. After boot, orientation changes are ignored for a few seconds (`ROT_GRACE_MS`) so a mis-hit cannot reboot-loop.

## Config knobs

Edit [`config.py`](config.py) on the Pico (or locally, then re-upload):

| Setting | Purpose |
|---------|---------|
| `POLL_INTERVAL_MS` | How often a background sync is scheduled (soft-reset) |
| `TZ_FORCE_OFFSET_MINUTES` | Fixed UTC offset; `None` = UK BST heuristic |
| `TOUCH_*` / `ORIENT_*` | Touch mapping and landscape/portrait tables |
| `DEBUG_ORIENT` | Extra orientation breadcrumbs + `orient_log.txt` |
| `MAX_EVENTS` / `MAX_EVENTS_WEEK` | Cap event count if RAM is tight |

## RAM notes

A full 480×320 RGB565 buffer (~307 KB) does not fit. This project uses a **4-bit GS4** buffer (~77 KB). Network/TLS runs **without** the framebuffer; the UI boots from flash cache after a soft-reset.

## Development tests (PC)

```bash
pip install -r requirements-pc.txt
python -m pytest tests/host -q

# Optional: unix MicroPython heap scenarios + device scenarios
python tools/run_mem_tests.py
python tools/run_mem_tests.py --device
```

Do not copy `tests/` to the Pico for desk use; `--device` stages helpers under `upy_test/` only for that run.

## License

MIT — see [LICENSE](LICENSE).

`lib/ili9486.py`, `lib/boolpalette.py`, `lib/writer.py`, and `lib/fonts/arial10.py` are adapted from [peterhinch/micropython-nano-gui](https://github.com/peterhinch/micropython-nano-gui) (MIT).
