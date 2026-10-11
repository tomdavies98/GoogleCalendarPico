#!/usr/bin/env python3
"""
One-time helper (run on a PC) to obtain a Google OAuth refresh token
for the Pico calendar app.

Prerequisites:
  pip install -r requirements-pc.txt
  Enable Google Calendar API in Google Cloud Console.
  Create an OAuth client ID of type "Desktop app".
  Download client secrets JSON, or paste client id/secret when prompted.

Usage:
  python tools/get_refresh_token.py
  python tools/get_refresh_token.py --secrets path/to/client_secret.json
"""

from __future__ import annotations

import argparse
import json
import sys

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--secrets",
        help="Path to Google OAuth desktop client JSON",
        default=None,
    )
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Install deps first: pip install -r requirements-pc.txt", file=sys.stderr)
        return 1

    if args.secrets:
        flow = InstalledAppFlow.from_client_secrets_file(args.secrets, SCOPES)
        client_id = None
        client_secret = None
        with open(args.secrets, encoding="utf-8") as f:
            data = json.load(f)
        installed = data.get("installed") or data.get("web") or {}
        client_id = installed.get("client_id")
        client_secret = installed.get("client_secret")
    else:
        client_id = input("OAuth client ID: ").strip()
        client_secret = input("OAuth client secret: ").strip()
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    # Fixed port so it matches Authorized redirect URIs in Cloud Console.
    # If you see Error 400: redirect_uri_mismatch, either:
    #   A) Recreate the OAuth client as type "Desktop app" (recommended), or
    #   B) For a "Web application" client, add these Authorized redirect URIs:
    #        http://localhost:8080/
    #        http://127.0.0.1:8080/
    port = 8080
    print(f"Opening browser; callback expects http://localhost:{port}/")
    creds = flow.run_local_server(
        port=port,
        access_type="offline",
        prompt="consent",
        open_browser=True,
    )
    if not creds.refresh_token:
        print(
            "No refresh_token returned. Revoke prior app access and retry with prompt=consent.",
            file=sys.stderr,
        )
        return 1

    print("\nAdd these lines to secrets.py on the Pico:\n")
    print(f'GOOGLE_CLIENT_ID = "{client_id or creds.client_id}"')
    print(f'GOOGLE_CLIENT_SECRET = "{client_secret or creds.client_secret}"')
    print(f'GOOGLE_REFRESH_TOKEN = "{creds.refresh_token}"')
    print('GOOGLE_CALENDAR_ID = "primary"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
