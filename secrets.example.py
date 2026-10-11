# Copy this file to secrets.py on the Pico and fill in real values:
#   cp secrets.example.py secrets.py
#
# secrets.py is gitignored — never commit real tokens or passwords.

WIFI_SSID = "Your_Network_Name"
WIFI_PASSWORD = "Your_WiFi_Password"

# From Google Cloud Desktop OAuth client + tools/get_refresh_token.py
GOOGLE_CLIENT_ID = "xxxx.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-xxxx"
GOOGLE_REFRESH_TOKEN = "1//xxxx"

# Usually "primary", or a calendar ID / email address
GOOGLE_CALENDAR_ID = "primary"
