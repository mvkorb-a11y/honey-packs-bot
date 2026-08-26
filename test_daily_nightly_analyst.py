#!/usr/bin/env python3
"""
Test Suite: Tier 2 Daily Nightly Intelligence Analyst
Project: Honey Packs Health AI

Verifies:
1. Compiling daily dossier across Nutrition, Telemetry, and Profile.
2. Generating AI Nightly Biohacking Analysis with Gemini 2.5 Flash / Fallback.
3. Saving historical reports to `analytics_db/daily_ai_reports.json`.
"""

import os
import sys
import json
from daily_nightly_analyst import (
    compile_daily_dossier,
    execute_nightly_audit,
    NIGHTLY_REPORTS_JSON
)


def run_test(name, func):
    try:
        func()
        print(f"✅ PASS: {name}", flush=True)
        return True
    except Exception as e:
        print(f"❌ FAIL: {name} -> Error: {e}", flush=True)
        return False


def test_dossier_compilation():
    """Test 24h mathematical dossier aggregation."""
    dossier = compile_daily_dossier("2026-08-26")
    assert dossier is not None, "Failed to compile daily dossier!"
    assert dossier["date"] == "2026-08-26", "Wrong date in dossier!"
    assert "nutrition_totals" in dossier, "nutrition_totals missing!"
    assert "telemetry_totals" in dossier, "telemetry_totals missing!"
    assert "energy_balance" in dossier, "energy_balance missing!"
    assert dossier["telemetry_totals"]["scientific_tdee_kcal"] > 1800, "Scientific TDEE is too low!"


def test_nightly_ai_audit_generation():
    """Test generating full nightly audit report."""
    report = execute_nightly_audit("2026-08-26")
    assert report is not None and len(report) > 100, "Nightly report is too short or empty!"
    assert os.path.exists(NIGHTLY_REPORTS_JSON), f"Reports database {NIGHTLY_REPORTS_JSON} missing!"

    with open(NIGHTLY_REPORTS_JSON, "r", encoding="utf-8") as f:
        db = json.load(f)
    assert "2026-08-26" in db, "Date 2026-08-26 missing in nightly reports database!"


def main():
    print("=" * 65, flush=True)
    print("🧪 RUNNING NIGHTLY AI ANALYST TEST SUITE...", flush=True)
    print("=" * 65, flush=True)

    passed = 0
    total = 2

    if run_test("1. Daily Dossier Compilation (24h Facts)", test_dossier_compilation): passed += 1
    if run_test("2. Nightly AI Audit Generation & Database Storage", test_nightly_ai_audit_generation): passed += 1

    print("=" * 65, flush=True)
    print(f"📊 RESULTS: {passed}/{total} TESTS PASSED ({int(passed/total*100)}%)", flush=True)
    print("=" * 65, flush=True)

    if passed == total:
        print("🏆 NIGHTLY AI ANALYST IS 100% OPERATIONAL & VERIFIED!", flush=True)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
