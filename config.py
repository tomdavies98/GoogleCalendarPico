# Hardware and app configuration for Pico-ResTouch-LCD-3.5 calendar.

# Display / SPI pins (Waveshare Pico-ResTouch-LCD-3.5)
PIN_LCD_DC = 8
PIN_LCD_CS = 9
PIN_LCD_CLK = 10
PIN_LCD_MOSI = 11
PIN_LCD_MISO = 12
PIN_LCD_BL = 13
PIN_LCD_RST = 15
PIN_TP_CS = 16
PIN_TP_IRQ = 17

SPI_ID = 1
SPI_BAUD_DISPLAY = 30_000_000
SPI_BAUD_TOUCH = 2_500_000

# Active dims — mutated at boot by orient.apply() from ORIENT_* tables.
WIDTH = 480
HEIGHT = 320
ORIENT = "L"  # "L" landscape | "P" portrait
MADCTL = 0x48

# Touch calibration — Waveshare Pico-ResTouch-LCD-3.5
# Base formula from Waveshare demo (MADCTL 0x28). Landscape uses MADCTL 0x48.
TOUCH_RAW_MIN = 430
TOUCH_RAW_SPAN = 3270
TOUCH_FLIP_X = False
TOUCH_FLIP_Y = True
TOUCH_SWAP_XY = False  # True: D0→X / D90→Y (portrait MADCTL with MV)
DEBUG_TOUCH = False  # True floods serial/SPI and can freeze the UI on low RAM
DEBUG_DRAW = False  # True logs every full redraw (costs RAM; leave off for desk use)
DEBUG_ORIENT = True  # breadcrumb prints + orient_log.txt (survives soft-reset)
ROT_GRACE_MS = 5000  # ignore Rot taps after boot (stops mis-hit reboot loops)

# Gesture tuning (tap-only — no drag scroll)
TOUCH_TAP_SLOP_PX = 100
TOUCH_TAP_MAX_MS = 1800
TOUCH_HIT_SLOP = 24
# Top/bottom bands count as toolbar even if Y mapping is off
TOUCH_CHROME_BAND_PX = 160
MANUAL_FOLLOW_TIMEOUT_MS = 30_000  # after Up/Down, snap back to now
WIFI_RETRY_MS = 45_000  # retry sync after Wi-Fi failure while UI is up

# Per-orientation tables (orient.apply / boot inline apply mutate live fields).
# Landscape MADCTL 0x48 is the known-good desk setting (MX|BGR).
# Portrait keeps the *same* MADCTL — do NOT use 0x28 (MV): that is Waveshare's
# horizontal addressing and only looked like a 180° flip. True vertical layout
# comes from WIDTH/HEIGHT 320x480 so ili9486.show() uses the portrait blit path.
ORIENT_LANDSCAPE = {
    "width": 480,
    "height": 320,
    "madctl": 0x48,
    "touch_flip_x": False,
    "touch_flip_y": True,
    "touch_swap_xy": False,
    "chrome_band": 160,
    "gutter_w": 52,
}
ORIENT_PORTRAIT = {
    "width": 320,
    "height": 480,
    "madctl": 0x48,
    "touch_flip_x": True,
    "touch_flip_y": False,
    "touch_swap_xy": True,
    "chrome_band": 96,
    "gutter_w": 40,
}

# Timeline UI
HEADER_H = 36
TOOLBAR_H = 28
ALLDAY_H = 22
GUTTER_W = 52
PPM = 1.2  # pixels per minute (day view)
DAY_MINUTES = 24 * 60
SCROLL_STEP_MINUTES = 90  # Up/Down step in day view
AUTO_FOLLOW_BIAS = 0.33  # NOW line position in viewport (0=top, 1=bottom)
WEEK_ROW_H = 34  # event row height in week agenda columns
DEFAULT_VIEW = "day"  # "day" or "week"

# Google Calendar
CALENDAR_ID = "primary"
POLL_INTERVAL_MS = 300_000  # 5 min — refresh uses soft-reset, keep this gentle
MAX_EVENTS = 12  # day-sized fetches
MAX_EVENTS_WEEK = 25  # keep small — must free LCD (~77KB) around TLS
GCAL_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

# Timezone: Europe/London approximated with UK DST (last Sun Mar / last Sun Oct).
# Set TZ_FORCE_OFFSET_MINUTES to a fixed offset to skip DST logic (e.g. 0 or 60).
TZ_FORCE_OFFSET_MINUTES = None
TZ_NAME = "Europe/London"

# Wi-Fi / HTTP
WIFI_TIMEOUT_MS = 45_000
HTTP_TIMEOUT_S = 20
NTP_HOST = "pool.ntp.org"
