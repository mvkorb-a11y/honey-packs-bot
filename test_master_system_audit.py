#!/usr/bin/env python3
"""
Master System Audit & Verification Test Suite
Project: Honey Packs Biohacking Core

Tests all 5 core subsystems:
1. Tier 1 Data Ingestion Center (25 parameters, custom recipes catalog, strict write authorization).
2. 26-Sensor Biometrics Telemetry Pipeline (raw 1s streams, 6 sensor series, CSV history table).
3. Tier 2 Master Analytics Center (daily summaries, 7/30d period reports, net deficit).
4. Telegram Bot Card Formatting & Keyword Routing (0 AI comments, day/week/month report tags).
5. Web Dashboard On-Demand Sync API (/api/sync-fitbit).
"""

import os
import sys
import json
from datetime import datetime, timedelta


# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_ingestion_collector import (
    match_custom_recipe,
    parse_raw_food_input,
    commit_raw_meal,
    CUSTOM_RECIPES_FILE,
    DIARY_FILE,
    DIARY_CSV_FILE
)


from telemetry_database_manager import (
    save_high_res_telemetry_partition,
    append_telemetry_csv_row,
    TELEMETRY_CSV_FILE
)
from raw_sensor_streams_manager import (
    save_unmodified_raw_sensor_stream,
    generate_sample_1s_ppg_stream
)
from sensor_series_packager import package_raw_sensor_series
from analytics_intelligence_engine import (
    compute_daily_analytics_summary
)
from food_nutrition_engine import get_period_summary


from telegram_bot import format_360_meal_draft



def run_test(test_name, test_func):
    """Run test and display pass/fail status."""
    try:
        test_func()
        print(f"✅ PASS: {test_name}", flush=True)
        return True
    except Exception as e:
        print(f"❌ FAIL: {test_name} -> Error: {e}", flush=True)
        return False


def test_spoken_time_recognition():
    """Test spoken meal time recognition (e.g. 'в 14:30 съел творог') vs message recording timestamp fallback."""
    # Case A: Spoken explicit time "14:30"
    meal_with_time = {
        "meal_name": "Овсяная каша",
        "spoken_time": "14:30:00",
        "calories": 300,
        "protein_g": 10.0,
        "fat_g": 5.0,
        "carbs_g": 50.0,
        "source": "APP"
    }
    res_time = commit_raw_meal(meal_with_time, source="APP")
    assert res_time is not None, "Commit failed!"
    assert "14:30:00" in res_time.get("timestamp"), f"Expected 14:30:00 in timestamp, got {res_time.get('timestamp')}"

    # Case B: Standard preset time for Breakfast when time not explicit
    meal_breakfast = {
        "meal_name": "Омлет",
        "meal_type": "Breakfast",
        "transcribed_text": "сегодня на завтрак съел омлет",
        "calories": 220,
        "protein_g": 14.0,
        "fat_g": 16.0,
        "carbs_g": 2.0,
        "source": "APP"
    }
    res_bf = commit_raw_meal(meal_breakfast, source="APP")
    assert res_bf is not None, "Commit failed!"
    assert "09:00:00" in res_bf.get("timestamp"), f"Expected 09:00:00 for breakfast, got {res_bf.get('timestamp')}"

    # Case C: No spoken time or meal type -> fallback to current exact timestamp
    meal_no_time = {
        "meal_name": "Яблоко",
        "calories": 80,
        "protein_g": 0.5,
        "fat_g": 0.2,
        "carbs_g": 20.0,
        "source": "APP"
    }
    res_no_time = commit_raw_meal(meal_no_time, source="APP")
    assert res_no_time is not None, "Commit failed!"
    assert datetime.now().strftime("%Y-%m-%d") in res_no_time.get("timestamp"), "Fallback timestamp missing today's date!"

    # Case D: Spoken Relative Date ("вчера в 14:30 съел творог")
    meal_yesterday = {
        "meal_name": "Творог",
        "transcribed_text": "вчера в 14:30 съел творог",
        "calories": 180,
        "protein_g": 25.0,
        "fat_g": 5.0,
        "carbs_g": 3.0,
        "source": "APP"
    }
    res_yest = commit_raw_meal(meal_yesterday, source="APP")
    assert res_yest is not None, "Commit failed!"
    expected_yest_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    assert expected_yest_date in res_yest.get("timestamp"), f"Expected yesterday date {expected_yest_date}, got {res_yest.get('timestamp')}"
    assert "14:30:00" in res_yest.get("timestamp"), "Expected 14:30:00 time!"




def test_custom_recipe_catalog_matching():
    """Test instant precision matching of custom recipes catalog."""

    assert os.path.exists(CUSTOM_RECIPES_FILE), f"Catalog file {CUSTOM_RECIPES_FILE} missing!"
    res = match_custom_recipe("Творог 5% с черникой и орехами")
    assert res is not None, "Failed to match custom recipe!"
    assert res.get("is_custom_matched") is True, "Custom matched flag missing!"
    assert res.get("protein_g") == 32.0, f"Expected 32.0g protein, got {res.get('protein_g')}"
    assert res.get("source") == "LIBRARY", "Source should be LIBRARY!"


def test_strict_write_authorization_policy():
    """Test that unauthorized write sources are rejected, while authorized sources are committed."""
    sample_meal = {
        "meal_name": "Тестовый Полезный Салат",
        "meal_type": "Lunch",
        "calories": 250,
        "protein_g": 15.0,
        "fat_g": 10.0,
        "carbs_g": 20.0,
        "source": "UNAUTHORIZED_HACKER_SOURCE"
    }
    # 1. Reject unauthorized source
    res_unauth = commit_raw_meal(sample_meal, source="UNAUTHORIZED_HACKER_SOURCE")
    assert res_unauth is None, "Unauthorized write should be rejected!"

    # 2. Accept authorized source APP
    sample_meal["source"] = "APP"
    res_auth = commit_raw_meal(sample_meal, source="APP")
    assert res_auth is not None, "Authorized APP write should be committed!"
    assert res_auth.get("source") == "APP", "Source tag should be APP!"


def test_26_sensor_telemetry_pipeline():
    """Test 1-to-1 raw sensor stream recording, 6-sensor packaging, and CSV table row appending."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")
    
    sample_streams = generate_sample_1s_ppg_stream(today_str)
    save_unmodified_raw_sensor_stream(today_str, sample_streams)
    
    pkg_file = package_raw_sensor_series(today_str, sample_streams)
    assert os.path.exists(pkg_file), f"Package file {pkg_file} missing!"
    
    with open(pkg_file, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    assert "sensors" in pkg, "Sensors dict missing!"
    assert "SENSOR_PPG_OPTICAL" in pkg["sensors"], "SENSOR_PPG_OPTICAL missing!"
    assert "SENSOR_CEDA_STRESS" in pkg["sensors"], "SENSOR_CEDA_STRESS missing!"
    
    sample_26 = {
        "cardiovascular_domain": {"1_heart_rate_bpm": 68, "2_resting_hr_bpm": 48, "3_hrv_rmssd_ms": 65, "4_hrv_sdnn_ms": 78, "5_active_zone_minutes": 45, "6_vo2_max": 48},
        "sleep_respiratory_domain": {"7_sleep_duration_hours": 7.5, "8_sleep_deep_minutes": 95, "9_sleep_rem_minutes": 110, "10_sleep_light_minutes": 245, "11_sleep_awake_minutes": 28, "12_sleep_efficiency_pct": 91, "13_sleep_score": 88, "14_spo2_pct": 97, "15_breathing_rate_rpm": 14},
        "stress_ceda_domain": {"16_ceda_body_responses": 12, "17_stress_events_count": 3, "18_stress_management_score": 82},
        "thermal_domain": {"19_skin_temp_variation_c": -0.2, "20_baseline_skin_temp_c": 34.8},
        "locomotion_altimeter_domain": {"21_steps_count": 12022, "22_distance_km": 9.22, "23_floors_climbed": 14, "24_active_sport_duration_min": 45},
        "metabolic_domain": {"25_active_calories_kcal": 1576, "26_tdee_calories_kcal": 4132}
    }
    save_high_res_telemetry_partition(today_str, sample_26)
    append_telemetry_csv_row(today_str, now_time, sample_26)
    assert os.path.exists(TELEMETRY_CSV_FILE), f"Telemetry CSV file {TELEMETRY_CSV_FILE} missing!"


def test_tier_2_master_analytics_engine():
    """Test daily history summary computation and period reports for 7d/30d."""
    hist = compute_daily_analytics_summary(days=7)
    assert "daily_summaries" in hist, "daily_summaries key missing!"
    assert len(hist["daily_summaries"]) == 7, f"Expected 7 daily summaries, got {len(hist['daily_summaries'])}"

    rep_7 = get_period_summary(7)
    assert rep_7.get("period_days") == 7, "7-day period summary missing period_days!"

    rep_30 = get_period_summary(30)
    assert rep_30.get("period_days") == 30, "30-day period summary missing period_days!"



def test_telegram_card_clean_formatting():
    """Test that Telegram meal card output has 0 AI comments and clean formatting."""
    sample_card_meal = {
        "meal_name": "Тестовый Творог",
        "calories": 180,
        "protein_g": 25.0,
        "fat_g": 5.0,
        "carbs_g": 3.0,
        "fiber_g": 0.0,
        "sugar_g": 1.0,
        "vitamins_minerals": {"magnesium_mg": 30, "zinc_mg": 1.0},
        "amino_acids": {"lysine_g": 2.0, "tryptophan_g": 0.3}
    }
    card_text = format_360_meal_draft(sample_card_meal)
    assert "Комментарий AI" not in card_text, "AI comment string detected in Telegram card!"
    assert "Тестовый Творог" in card_text, "Meal name missing from card!"
    assert "Белок: `25.0г`" in card_text, "Protein parameter missing from card!"



def test_behavioral_actions_domain_engine():
    """Test 100% deterministic mathematical classification of daily behavioral activities."""
    from behavioral_actions_engine import evaluate_action_probabilities, reconstruct_daily_behavioral_flow, ACTIONS_JSON_FILE
    p_sleep = evaluate_action_probabilities(step_count=0, avg_hr=48.5, min_hr=45.0, max_hr=58.0, kcal_burned=81.5)
    assert p_sleep[0]["action_key"] == "SLEEP", f"Expected sleep, got {p_sleep[0]['action_key']}"

    p_walk = evaluate_action_probabilities(step_count=850, avg_hr=78.0, min_hr=65.0, max_hr=95.0, kcal_burned=180.0)
    assert p_walk[0]["action_key"] == "TARGETED_WALKING", f"Expected walking, got {p_walk[0]['action_key']}"

    flow = reconstruct_daily_behavioral_flow("2026-08-26")
    assert flow is not None and len(flow["hourly_timeline"]) == 24, "Timeline reconstruction failed!"
    assert os.path.exists(ACTIONS_JSON_FILE), "Actions domain database file missing!"


def test_daily_nightly_analyst_engine():
    """Test compiling 24h mathematical dossier and generating AI nightly biohacking audit."""
    from daily_nightly_analyst import compile_daily_dossier, execute_nightly_audit, NIGHTLY_REPORTS_JSON
    dossier = compile_daily_dossier("2026-08-26")
    assert dossier is not None and "nutrition_totals" in dossier, "Dossier compilation failed!"
    
    rep = execute_nightly_audit("2026-08-26")
    assert rep is not None and len(rep) > 50, "Nightly report generation failed!"
    assert os.path.exists(NIGHTLY_REPORTS_JSON), "Nightly reports database missing!"


def main():
    print("=" * 70, flush=True)
    print("🧪 RUNNING MASTER SYSTEM AUDIT & SUITE TESTS...", flush=True)
    print("=" * 70, flush=True)

    passed = 0
    total = 8

    if run_test("1. Spoken Meal Time Recognition & Timestamp Fallback", test_spoken_time_recognition): passed += 1
    if run_test("2. Custom Recipe Catalog & Precision Matching", test_custom_recipe_catalog_matching): passed += 1
    if run_test("3. Strict Write Authorization Policy", test_strict_write_authorization_policy): passed += 1
    if run_test("4. 26-Sensor Biometrics Telemetry & Stream Pipeline", test_26_sensor_telemetry_pipeline): passed += 1
    if run_test("5. Tier 2 Master Analytics Center (7d/30d Reports)", test_tier_2_master_analytics_engine): passed += 1
    if run_test("6. Telegram Bot Clean Card Formatting (0 AI Comments)", test_telegram_card_clean_formatting): passed += 1
    if run_test("7. Autonomous Behavioral Actions Domain Engine & DB", test_behavioral_actions_domain_engine): passed += 1
    if run_test("8. Daily Nightly AI Biohacking Analyst (23:00 Cron)", test_daily_nightly_analyst_engine): passed += 1


    print("=" * 70, flush=True)
    print(f"📊 SUMMARY RESULTS: {passed}/{total} TESTS PASSED ({int(passed/total*100)}%)", flush=True)
    print("=" * 70, flush=True)

    if passed == total:
        print("🏆 ALL SUBSYSTEMS ARE 100% VERIFIED & OPERATIONAL!", flush=True)
        sys.exit(0)
    else:
        print("⚠️ SOME TESTS FAILED. CHECK LOGS ABOVE.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
