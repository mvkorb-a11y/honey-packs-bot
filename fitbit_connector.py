#!/usr/bin/env python3
"""
Fitbit Web API Biometric Connector & Health Analyzer
Project: Honey Packs Health AI

This script connects to Fitbit Web API via OAuth 2.0 (PKCE / Personal App),
fetches full daily health telemetry (Sleep, Heart Rate, HRV/Resting HR, Calories Burned),
saves raw JSON telemetry, and outputs a formatted Health & Recovery Audit.
"""

import os
import sys
import json
import time
import base64
import hashlib
import secrets
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

CONFIG_FILE = "fitbit_config.json"
TOKENS_FILE = "fitbit_tokens.json"
RAW_DATA_FILE = "fitbit_raw_data.json"
REDIRECT_URI = "http://localhost:8080/callback"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Local HTTP Server to catch OAuth authorization code automatically."""
    author_code = None

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if "code" in query_params:
            OAuthCallbackHandler.author_code = query_params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            success_html = """
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: #f8fafc;">
                    <h1 style="color: #22c55e;">Authorization Successful! 🎉</h1>
                    <p style="font-size: 18px;">Fitbit successfully connected to Honey Packs Health Engine.</p>
                    <p>You can close this browser tab and return to the terminal.</p>
                </body>
            </html>
            """
            self.wfile.write(success_html.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization failed. No code found.")

    def log_message(self, format, *args):
        return  # Suppress default server access logs


def get_credentials():
    """Load client_id and client_secret from config or prompt user."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            if config.get("client_id") and config.get("client_secret"):
                return config["client_id"], config["client_secret"]

    print("\n" + "=" * 65)
    print("🔑 FITBIT DEVELOPER APP SETUP REQUIRED")
    print("=" * 65)
    print("To fetch data from your Fitbit, we need your free Developer App keys.")
    print("Follow these 3 quick steps (takes 1 minute):\n")
    print("1. Go to: https://dev.fitbit.com/apps/new")
    print("2. Fill in the fields:")
    print("   - Application Name: Honey Packs Health")
    print("   - Description: Personal Health Tracker")
    print("   - Application Website: http://localhost:8080")
    print("   - Organization: Self")
    print("   - OAuth 2.0 Application Type: PERSONAL (CRITICAL for Heart Rate & Sleep!)")
    print(f"   - Callback URL: {REDIRECT_URI}")
    print("   - Default Access Scope: Select ALL (Activity, Heart Rate, Sleep, Profile, etc.)")
    print("3. Click 'Save' and copy your OAuth 2.0 Client ID & Client Secret.\n")

    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()

    if not client_id or not client_secret:
        print("❌ Error: Client ID and Client Secret are required.")
        sys.exit(1)

    config = {"client_id": client_id, "client_secret": client_secret}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Config saved to {CONFIG_FILE}")
    return client_id, client_secret


def generate_pkce_pair():
    """Generate PKCE code_verifier and code_challenge for OAuth2 security."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").replace("=", "")
    return verifier, challenge


def authorize_fitbit(client_id, client_secret):
    """Perform OAuth 2.0 PKCE flow to acquire access and refresh tokens."""
    verifier, challenge = generate_pkce_pair()
    scopes = "activity heartrate location nutrition profile settings sleep social weight"

    auth_url = (
        f"https://www.fitbit.com/oauth2/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"scope={urllib.parse.quote(scopes)}&"
        f"code_challenge={challenge}&"
        f"code_challenge_method=S256"
    )

    print("\n🌐 Opening browser for Fitbit Authorization...")
    print(f"If browser does not open automatically, click this link:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Start local HTTP server to capture authorization code
    server_address = ("localhost", 8080)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    print("⏳ Waiting for Fitbit authorization in browser...")
    while OAuthCallbackHandler.author_code is None:
        httpd.handle_request()

    code = OAuthCallbackHandler.author_code
    print("✅ Authorization code received!")

    # Exchange code for tokens
    token_url = "https://api.fitbit.com/oauth2/token"
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "client_id": client_id,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code,
        "code_verifier": verifier
    }

    res = requests.post(token_url, headers=headers, data=data)
    if res.status_code != 200:
        print(f"❌ Token exchange failed ({res.status_code}): {res.text}")
        sys.exit(1)

    tokens = res.json()
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 28800)
    
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)

    print(f"✅ Tokens successfully acquired and saved to {TOKENS_FILE}")
    return tokens


def refresh_tokens(client_id, client_secret, refresh_token):
    """Refresh expired access token using refresh_token."""
    token_url = "https://api.fitbit.com/oauth2/token"
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    res = requests.post(token_url, headers=headers, data=data)
    if res.status_code != 200:
        print(f"❌ Token refresh failed: {res.text}")
        return None

    tokens = res.json()
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 28800)
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)

    return tokens


def get_valid_access_token():
    """Retrieve or refresh valid access token."""
    client_id, client_secret = get_credentials()

    if not os.path.exists(TOKENS_FILE):
        tokens = authorize_fitbit(client_id, client_secret)
        return tokens["access_token"]

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    if time.time() > tokens.get("expires_at", 0) - 300:
        print("🔄 Token expired. Refreshing token...")
        tokens = refresh_tokens(client_id, client_secret, tokens.get("refresh_token"))
        if not tokens:
            print("🔄 Re-authorizing...")
            tokens = authorize_fitbit(client_id, client_secret)

    return tokens["access_token"]


def fetch_fitbit_telemetry(date_str="today"):
    """Fetch complete daily biometric telemetry from Fitbit API."""
    token = get_valid_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    endpoints = {
        "profile": "https://api.fitbit.com/1/user/-/profile.json",
        "summary": f"https://api.fitbit.com/1/user/-/activities/date/{date_str}.json",
        "heart_rate": f"https://api.fitbit.com/1/user/-/activities/heart/date/{date_str}/1d.json",
        "sleep": f"https://api.fitbit.com/1.2/user/-/sleep/date/{date_str}.json",
    }

    raw_data = {}
    print(f"\n📡 Fetching Fitbit Biometric Telemetry for date: [{date_str}]...")

    for key, url in endpoints.items():
        try:
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                raw_data[key] = r.json()
                print(f"  ✓ {key.upper()}: Data fetched successfully (200 OK)")
            else:
                print(f"  ⚠️ {key.upper()}: Status {r.status_code} - {r.text}")
                raw_data[key] = {"error": r.status_code, "msg": r.text}
        except Exception as e:
            print(f"  ❌ {key.upper()} exception: {e}")
            raw_data[key] = {"error": str(e)}

    # Save raw telemetry JSON for analysis
    with open(RAW_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2)

    print(f"\n💾 Saved full raw telemetry to: {RAW_DATA_FILE}")
    return raw_data


def analyze_and_print_audit(raw_data):
    """Parse raw telemetry and print structured Health & Recovery Audit."""
    print("\n" + "=" * 65)
    print("📊 FITBIT HEALTH & RECOVERY BIOMETRIC AUDIT")
    print("=" * 65)

    # 1. Profile
    profile = raw_data.get("profile", {}).get("user", {})
    user_name = profile.get("displayName", "User")
    age = profile.get("age", "N/A")
    gender = profile.get("gender", "N/A")
    print(f"👤 User: {user_name} | Age: {age} | Gender: {gender}")

    # 2. Activity & Calories (TDEE)
    summary = raw_data.get("summary", {}).get("summary", {})
    total_calories = summary.get("caloriesOut", 0)
    active_calories = summary.get("activityCalories", 0)
    steps = summary.get("steps", 0)
    floors = summary.get("floors", 0)
    sedentary_mins = summary.get("sedentaryMinutes", 0)

    print("\n🔥 CALORIES & PHYSICAL STRAIN:")
    print(f"  • Total Daily Calories Burned (TDEE): {total_calories} kcal")
    print(f"  • Active Activity Calories:        {active_calories} kcal")
    print(f"  • Total Steps:                      {steps} steps")
    print(f"  • Sedentary Time:                   {sedentary_mins // 60}h {sedentary_mins % 60}m")

    # 3. Heart Rate & Resting HR
    hr_data = raw_data.get("heart_rate", {}).get("activities-heart", [{}])[0].get("value", {})
    resting_hr = hr_data.get("restingHeartRate", "N/A")
    hr_zones = hr_data.get("heartRateZones", [])

    print("\n❤️ HEART RATE & RECOVERY METRICS:")
    print(f"  • Resting Heart Rate (Пульс покоя): {resting_hr} bpm")
    for zone in hr_zones:
        z_name = zone.get("name", "Zone")
        z_min = zone.get("min", 0)
        z_max = zone.get("max", 0)
        z_mins = zone.get("minutes", 0)
        print(f"    - {z_name} ({z_min}-{z_max} bpm): {z_mins} mins")

    # 4. Sleep Architecture
    sleep_summary = raw_data.get("sleep", {})
    sleep_records = sleep_summary.get("sleep", [])
    
    print("\n🌙 SLEEP ARCHITECTURE & RECOVERY:")
    if sleep_records:
        main_sleep = sleep_records[0]
        total_sleep_mins = main_sleep.get("minutesAsleep", 0)
        sleep_efficiency = main_sleep.get("efficiency", 0)
        stages = main_sleep.get("levels", {}).get("summary", {})

        deep_mins = stages.get("deep", {}).get("minutes", 0)
        rem_mins = stages.get("rem", {}).get("minutes", 0)
        light_mins = stages.get("light", {}).get("minutes", 0)
        wake_mins = stages.get("wake", {}).get("minutes", 0)

        print(f"  • Total Duration Asleep: {total_sleep_mins // 60}h {total_sleep_mins % 60}m")
        print(f"  • Sleep Efficiency:      {sleep_efficiency}%")
        print(f"  • Deep Sleep (Глубокий): {deep_mins} mins ({round(deep_mins/total_sleep_mins*100 if total_sleep_mins else 0)}%)")
        print(f"  • REM Sleep (Быстрый):   {rem_mins} mins ({round(rem_mins/total_sleep_mins*100 if total_sleep_mins else 0)}%)")
        print(f"  • Light Sleep (Легкий):  {light_mins} mins")
        print(f"  • Awake Time (Пробуждения): {wake_mins} mins")
    else:
        print("  • No sleep record logged for today yet.")

    # 5. Energy Battery Calculation
    # Formula: Baseline 100% - (Physical Strain) + (Sleep Quality)
    sleep_bonus = 30 if sleep_records else 15
    energy_battery = max(10, min(100, 100 - (active_calories // 35) + sleep_bonus))

    print("\n⚡ RECOVERY ENERGY BATTERY:")
    print(f"  • Estimated Energy Battery: [{energy_battery}%]")
    if energy_battery > 70:
        print("  • Status: HIGH ENERGY 🟢 (Ready for intense workout & heavy tasks)")
    elif energy_battery > 40:
        print("  • Status: MODERATE ENERGY 🟡 (Balanced day, need regular nutrients)")
    else:
        print("  • Status: LOW RECOVERY 🔴 (High fatigue, prioritize rest & hydration)")

    print("=" * 65 + "\n")


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else "today"
    data = fetch_fitbit_telemetry(target_date)
    analyze_and_print_audit(data)
