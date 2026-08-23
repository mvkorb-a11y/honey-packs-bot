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
from datetime import datetime, timedelta


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

    is_google = "googleusercontent.com" in client_id

    if is_google:
        scopes = "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly https://www.googleapis.com/auth/googlehealth.sleep.readonly https://www.googleapis.com/auth/googlehealth.profile.readonly"


        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
            f"scope={urllib.parse.quote(scopes)}&"
            f"code_challenge={challenge}&"
            f"code_challenge_method=S256&"
            f"access_type=offline&"
            f"prompt=consent"
        )

        token_url = "https://oauth2.googleapis.com/token"
    else:
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
        token_url = "https://api.fitbit.com/oauth2/token"

    print("\n🌐 Opening browser for Health Authorization...")
    print(f"If browser does not open automatically, click this link:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Start local HTTP server to capture authorization code
    server_address = ("localhost", 8080)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    print("⏳ Waiting for authorization in browser...")
    while OAuthCallbackHandler.author_code is None:
        httpd.handle_request()

    code = OAuthCallbackHandler.author_code
    print("✅ Authorization code received!")

    # Exchange code for tokens
    if is_google:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": client_id.strip(),
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code.strip(),
            "code_verifier": verifier
        }
        if client_secret and len(client_secret.strip()) > 0:
            data["client_secret"] = client_secret.strip()


    else:
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
    tokens["is_google"] = is_google
    
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)

    print(f"✅ Tokens successfully acquired and saved to {TOKENS_FILE}")
    return tokens


def refresh_tokens(client_id, client_secret, refresh_token):
    """Refresh expired access token using refresh_token."""
    is_google = True if "googleusercontent.com" in client_id else False

    if is_google:
        token_url = "https://oauth2.googleapis.com/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
    else:
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

    new_tokens = res.json()
    new_tokens["expires_at"] = time.time() + new_tokens.get("expires_in", 28800)
    new_tokens["is_google"] = is_google
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token

    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(new_tokens, f, indent=2)

    return new_tokens



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


def fetch_fitbit_telemetry(date_str=None):
    """Fetch complete daily biometric telemetry from Google Fitness or Fitbit API."""
    if not date_str or date_str == "today":
        date_str = datetime.now().strftime("%Y-%m-%d")

    token = get_valid_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    is_google = tokens.get("is_google", False)
    raw_data = {"date": date_str, "is_google": is_google}

    print(f"\n📡 Fetching Biometric Telemetry for date: [{date_str}]...")

    if is_google:
        # Fetch Google Health API v4 Telemetry
        headers["Content-Type"] = "application/json"
        
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_iso = dt.strftime("%Y-%m-%dT00:00:00Z")
        end_iso = (dt + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

        body = {
            "range": {
                "startTime": start_iso,
                "endTime": end_iso
            },
            "windowSize": "3600s"
        }

        health_data = {}
        data_types = ["heart-rate", "total-calories", "steps", "active-minutes"]

        for dtype in data_types:
            url = f"https://health.googleapis.com/v4/users/me/dataTypes/{dtype}/dataPoints:rollUp"
            try:
                r = requests.post(url, headers=headers, json=body)
                if r.status_code == 200:
                    health_data[dtype] = r.json()
                    print(f"  ✓ GOOGLE HEALTH API v4 [{dtype}]: Data fetched successfully (200 OK)")
                else:
                    print(f"  ⚠️ GOOGLE HEALTH API v4 [{dtype}]: Status {r.status_code}")
            except Exception as e:
                print(f"  ❌ [{dtype}] Exception: {e}")

        # Fetch profile
        try:
            r_prof = requests.get("https://health.googleapis.com/v4/users/me/profile", headers=headers)
            if r_prof.status_code == 200:
                health_data["profile"] = r_prof.json()
        except Exception:
            pass

        raw_data["google_health_v4"] = health_data

    else:
        # Fetch Fitbit API endpoints
        endpoints = {
            "profile": "https://api.fitbit.com/1/user/-/profile.json",
            "summary": f"https://api.fitbit.com/1/user/-/activities/date/{date_str}.json",
            "heart_rate": f"https://api.fitbit.com/1/user/-/activities/heart/date/{date_str}/1d.json",
            "sleep": f"https://api.fitbit.com/1.2/user/-/sleep/date/{date_str}.json",
        }

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
        json.dump(raw_data, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Saved full raw telemetry to: {RAW_DATA_FILE}")
    return raw_data


def analyze_and_print_audit(raw_data):
    """Parse raw telemetry and print structured Health & Recovery Audit."""
    print("\n" + "=" * 65)
    print("📊 FITBIT / GOOGLE HEALTH BIOMETRIC AUDIT")
    print("=" * 65)

    is_google = raw_data.get("is_google", False)
    date_str = raw_data.get("date", datetime.now().strftime("%Y-%m-%d"))

    steps = 0
    total_calories = 0
    resting_hr = "N/A"
    avg_hr = "N/A"
    sleep_mins = 0

    if is_google and "google_health_v4" in raw_data:
        gh_data = raw_data["google_health_v4"]
        
        # Profile
        prof = gh_data.get("profile", {})
        age = prof.get("age", "N/A")
        print(f"👤 Google Health Profile: Age {age} | Account ID: {prof.get('name', '').split('/')[-2] if '/' in prof.get('name', '') else 'Active'}")

        # Heart Rate rollups
        hr_rollups = gh_data.get("heart-rate", {}).get("rollupDataPoints", [])
        hr_avg_list = []
        for pt in hr_rollups:
            hr_info = pt.get("heartRate", {})
            if "beatsPerMinuteAvg" in hr_info:
                hr_avg_list.append(hr_info["beatsPerMinuteAvg"])
        if hr_avg_list:
            avg_hr = int(sum(hr_avg_list) / len(hr_avg_list))
            resting_hr = int(min(hr_avg_list))

        # Total Calories & Active Calories
        cal_rollups = gh_data.get("total-calories", {}).get("rollupDataPoints", [])
        for pt in cal_rollups:
            total_calories += int(pt.get("totalCalories", {}).get("kcalSum", 0))

        active_cal_rollups = gh_data.get("active-energy-burned", {}).get("rollupDataPoints", [])
        active_calories = 0
        for pt in active_cal_rollups:
            active_calories += int(pt.get("activeEnergyBurned", {}).get("kcalSum", 0))

        # Steps & Distance
        step_rollups = gh_data.get("steps", {}).get("rollupDataPoints", [])
        for pt in step_rollups:
            steps += int(pt.get("steps", {}).get("countSum", 0))

        dist_rollups = gh_data.get("distance", {}).get("rollupDataPoints", [])
        distance_meters = 0
        for pt in dist_rollups:
            distance_meters += int(pt.get("distance", {}).get("millimetersSum", 0)) // 1000

        # Active Minutes
        active_mins_rollups = gh_data.get("active-minutes", {}).get("rollupDataPoints", [])
        active_minutes = 0
        for pt in active_mins_rollups:
            for lvl in pt.get("activeMinutes", {}).get("activeMinutesRollupByActivityLevel", []):
                active_minutes += int(lvl.get("activeMinutesSum", 0))

    else:
        # Fitbit API parser
        summary = raw_data.get("summary", {}).get("summary", {})
        total_calories = summary.get("caloriesOut", 0)
        active_calories = summary.get("activityCalories", 0)
        steps = summary.get("steps", 0)
        distance_meters = summary.get("distances", [{}])[0].get("distance", 0) * 1000
        active_minutes = summary.get("veryActiveMinutes", 0) + summary.get("fairlyActiveMinutes", 0)

        hr_data = raw_data.get("heart_rate", {}).get("activities-heart", [{}])[0].get("value", {})
        resting_hr = hr_data.get("restingHeartRate", "N/A")

    print(f"📅 Date: {date_str} | Source: {'Google Health API' if is_google else 'Fitbit API'}")
    print("\n🔥 CALORIES & PHYSICAL STRAIN:")
    print(f"  • Total Daily Calories Burned (TDEE): {total_calories} kcal")
    if 'active_calories' in locals() and active_calories > 0:
        print(f"  • Active Workout Calories:          {active_calories} kcal")
    print(f"  • Total Steps:                      {steps} steps ({distance_meters/1000:.2f} km)")
    if 'active_minutes' in locals() and active_minutes > 0:
        print(f"  • Active Workout Time:              {active_minutes} mins")

    print("\n❤️ HEART RATE & RECOVERY METRICS:")
    print(f"  • Resting Heart Rate (Пульс покоя): {resting_hr} bpm")
    if avg_hr != "N/A":
        print(f"  • Average Heart Rate (Средний пульс): {avg_hr} bpm")


    # Load food diary to compute Net Caloric Deficit
    try:
        from telegram_bot import load_food_diary
        diary = load_food_diary()
        today_diary = diary.get(date_str, [])
        consumed_cals = sum(item.get("calories", 0) for item in today_diary)
        
        if total_calories > 0:
            net_deficit = consumed_cals - total_calories
            print("\n⚖️ NET CALORIC BALANCE:")
            print(f"  • Consumed: {consumed_cals} kcal | Expended: {total_calories} kcal")
            print(f"  • Net Caloric Deficit/Surplus: {net_deficit:+d} kcal")
            if net_deficit < -800:
                print("  ⚠️ ALERT: High Caloric Deficit! Glycogen replenishment & +30g protein recommended.")
    except Exception as e:
        pass

    print("=" * 65 + "\n")



if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else "today"
    data = fetch_fitbit_telemetry(target_date)
    analyze_and_print_audit(data)
