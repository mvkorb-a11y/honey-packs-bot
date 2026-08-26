#!/usr/bin/env python3
"""
Test Suite: Autonomous Behavioral Actions Engine (Tier 2 Intelligence)
Project: Honey Packs Health AI

Verifies:
1. Mathematical signature distance calculation.
2. Classification of distinct states (Sleep, Office Work, Targeted Walking, Jogging, Postprandial).
3. Reconstructing 24-hour daily timeline from real telemetry dataset.
4. Isolated domain database creation in `analytics_db/daily_actions.json` and `analytics_db/daily_actions.csv`.
"""

import os
import sys
import json
from activity_signatures_registry import ACTIVITY_SIGNATURES, calculate_hrr_percentage
from behavioral_actions_engine import (
    classify_time_slice,
    reconstruct_daily_behavioral_flow,
    ACTIONS_JSON_FILE,
    ACTIONS_CSV_FILE
)


def run_test(name, func):
    try:
        func()
        print(f"✅ PASS: {name}", flush=True)
        return True
    except Exception as e:
        print(f"❌ FAIL: {name} -> Error: {e}", flush=True)
        return False


def test_signature_math_classification():
    """Test classification of distinct activities based on mathematical thresholds."""
    # 1. Deep Sleep: 0 cadence, 48 BPM
    key, sig, conf = classify_time_slice(cadence_spm=0, avg_hr=48.0)
    assert key in ["SLEEP_DEEP", "SLEEP_REM_LIGHT"], f"Expected sleep state, got {key}"
    assert conf > 0.7, f"Confidence too low: {conf}"

    # 2. Sedentary Office Work: 2 SPM, 62 BPM
    key, sig, conf = classify_time_slice(cadence_spm=2, avg_hr=62.0)
    assert key in ["SEDENTARY_WORK", "PASSIVE_REST"], f"Expected sedentary office, got {key}"

    # 3. Targeted Walking: 75 SPM, 82 BPM
    key, sig, conf = classify_time_slice(cadence_spm=75, avg_hr=82.0)
    assert key in ["TARGETED_WALKING", "LIGHT_NEAT_MOVEMENT"], f"Expected walking, got {key}"

    # 4. Running / High Intensity Cardio: 155 SPM, 130 BPM
    key, sig, conf = classify_time_slice(cadence_spm=155, avg_hr=130.0)
    assert key == "RUNNING_JOGGING", f"Expected running, got {key}"

    # 5. Postprandial Digestion: 1 SPM, 68 BPM with is_postprandial=True
    key, sig, conf = classify_time_slice(cadence_spm=1, avg_hr=68.0, is_postprandial=True)
    assert key == "MEAL_DIGESTION", f"Expected meal digestion, got {key}"


def test_daily_flow_timeline_reconstruction():
    """Test full 24-hour daily timeline reconstruction from real telemetry logs."""
    flow = reconstruct_daily_behavioral_flow("2026-08-26")
    assert flow is not None, "Failed to reconstruct daily behavioral flow!"
    assert len(flow["hourly_timeline"]) == 24, f"Expected 24 hourly slices, got {len(flow['hourly_timeline'])}"
    
    # Check domain database existence
    assert os.path.exists(ACTIONS_JSON_FILE), f"Database file {ACTIONS_JSON_FILE} missing!"
    assert os.path.exists(ACTIONS_CSV_FILE), f"Database file {ACTIONS_CSV_FILE} missing!"

    # Verify JSON database content
    with open(ACTIONS_JSON_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)
    assert "2026-08-26" in db, "Date 2026-08-26 missing in daily actions database!"


def main():
    print("=" * 65, flush=True)
    print("🧪 RUNNING BEHAVIORAL ACTIONS ENGINE TEST SUITE...", flush=True)
    print("=" * 65, flush=True)

    passed = 0
    total = 2

    if run_test("1. Mathematical Signature Classification", test_signature_math_classification): passed += 1
    if run_test("2. 24-Hour Timeline & Domain DB Generation", test_daily_flow_timeline_reconstruction): passed += 1

    print("=" * 65, flush=True)
    print(f"📊 RESULTS: {passed}/{total} TESTS PASSED ({int(passed/total*100)}%)", flush=True)
    print("=" * 65, flush=True)

    if passed == total:
        print("🏆 BEHAVIORAL ACTIONS ENGINE IS 100% OPERATIONAL & VERIFIED!", flush=True)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
