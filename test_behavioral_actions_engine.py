#!/usr/bin/env python3
"""
Test Suite: Probabilistic Multi-Metric Behavioral Actions Engine (Tier 2 Intelligence)
Project: Honey Packs Health AI

Verifies:
1. Multi-metric Bayesian probability evaluation.
2. Cross-sensor state classification (Sleep, Sedentary Desk, Indoor NEAT, Targeted Walking, Meal Digestion).
3. Reconstructing 24-hour daily timeline calibrated to real telemetry.
4. Isolated domain database creation in `analytics_db/daily_actions.json`.
"""

import os
import sys
import json
from behavioral_actions_engine import (
    evaluate_action_probabilities,
    reconstruct_daily_behavioral_flow,
    ACTIONS_JSON_FILE
)


def run_test(name, func):
    try:
        func()
        print(f"✅ PASS: {name}", flush=True)
        return True
    except Exception as e:
        print(f"❌ FAIL: {name} -> Error: {e}", flush=True)
        return False


def test_probabilistic_classification():
    """Test multi-metric classification with cross-sensor consensus."""
    # 1. Deep Sleep: 0 steps, 48.5 BPM (close to RHR), low spread
    p_sleep = evaluate_action_probabilities(step_count=0, avg_hr=48.5, min_hr=45.0, max_hr=58.0, kcal_burned=81.5)
    assert p_sleep[0]["action_key"] == "SLEEP", f"Expected SLEEP, got {p_sleep[0]['action_key']}"
    assert p_sleep[0]["probability_pct"] > 80.0, f"Probability too low: {p_sleep[0]['probability_pct']}%"

    # 2. Sedentary Desk Work: 30 steps/hr, 59 BPM
    p_desk = evaluate_action_probabilities(step_count=30, avg_hr=59.0, min_hr=53.0, max_hr=68.0, kcal_burned=89.0)
    assert p_desk[0]["action_key"] == "SEDENTARY_WORK", f"Expected SEDENTARY_WORK, got {p_desk[0]['action_key']}"

    # 3. Indoor NEAT Mobility: 350 steps/hr, 63 BPM
    p_neat = evaluate_action_probabilities(step_count=350, avg_hr=63.0, min_hr=55.0, max_hr=88.0, kcal_burned=117.0)
    assert p_neat[0]["action_key"] == "INDOOR_MOBILITY_NEAT", f"Expected INDOOR_MOBILITY_NEAT, got {p_neat[0]['action_key']}"

    # 4. Targeted Outdoor Walking: 850 steps/hr, 78 BPM
    p_walk = evaluate_action_probabilities(step_count=850, avg_hr=78.0, min_hr=65.0, max_hr=95.0, kcal_burned=180.0)
    assert p_walk[0]["action_key"] == "TARGETED_WALKING", f"Expected TARGETED_WALKING, got {p_walk[0]['action_key']}"

    # 5. Meal Digestion: is_postprandial=True, 150 steps/hr, 64 BPM
    p_meal = evaluate_action_probabilities(step_count=150, avg_hr=64.0, min_hr=55.0, max_hr=80.0, kcal_burned=100.0, is_postprandial=True)
    assert p_meal[0]["action_key"] == "MEAL_DIGESTION", f"Expected MEAL_DIGESTION, got {p_meal[0]['action_key']}"


def test_daily_flow_timeline_reconstruction():
    """Test full 24-hour daily timeline reconstruction from real telemetry dataset."""
    flow = reconstruct_daily_behavioral_flow("2026-08-26")
    assert flow is not None, "Failed to reconstruct daily behavioral flow!"
    assert len(flow["hourly_timeline"]) == 24, f"Expected 24 hourly slices, got {len(flow['hourly_timeline'])}"
    
    # Check domain database existence
    assert os.path.exists(ACTIONS_JSON_FILE), f"Database file {ACTIONS_JSON_FILE} missing!"

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

    if run_test("1. Multi-Metric Probabilistic Classification", test_probabilistic_classification): passed += 1
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
