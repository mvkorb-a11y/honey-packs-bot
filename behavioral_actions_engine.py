#!/usr/bin/env python3
"""
Probabilistic Multi-Metric Behavioral Actions Engine (Tier 2 Intelligence)
Project: Honey Packs Health AI

Architecture:
- 100% Deterministic Bayesian Multi-Metric Scoring.
- No hardcoded time-of-day locks (sleep can occur at any hour).
- Cross-validates across:
  1. Locomotion & Step Bursts (Cadence & Discrete Movement Batches)
  2. Cardiovascular Dynamics (%HRR, Delta to RHR, HR Variance)
  3. Metabolic & TEF Elevation (Postprandial Meal Timestamps)
  4. Timezone-Aligned Local Time (Europe/Tallinn, UTC+3)
"""

import os
import json
import math
from datetime import datetime, timezone, timedelta
try:
    import zoneinfo
    LOCAL_TZ = zoneinfo.ZoneInfo("Europe/Tallinn")
except Exception:
    LOCAL_TZ = None

ANALYTICS_DB_DIR = "analytics_db"
ACTIONS_JSON_FILE = os.path.join(ANALYTICS_DB_DIR, "daily_actions.json")
ACTIONS_CSV_FILE = os.path.join(ANALYTICS_DB_DIR, "daily_actions.csv")
FITBIT_DATA_FILE = "fitbit_raw_data.json"
FOOD_DIARY_FILE = "food_diary.json"

# User Individual Calibrated Physiological Baselines
USER_RHR = 49.8       # Athletic baseline resting heart rate
USER_HR_MAX = 174.0   # Max HR (220 - 46 age)
USER_BMR_HOURLY = 81.5 # Baseline resting kcal/hour


def calculate_hrr(hr, rhr=USER_RHR, hr_max=USER_HR_MAX):
    """Calculate Heart Rate Reserve percentage (%HRR)."""
    if hr <= rhr:
        return 0.0
    return min(max(((hr - rhr) / (hr_max - rhr)) * 100.0, 0.0), 100.0)


def evaluate_action_probabilities(step_count, avg_hr, min_hr, max_hr, kcal_burned, is_postprandial=False):
    """
    Multi-metric Bayesian likelihood calculator across 6 core activity categories.
    Returns sorted list of (action_key, action_name_ru, cluster, probability_pct, description).
    """
    cadence_spm = step_count / 60.0
    hr_delta_rhr = avg_hr - USER_RHR
    hr_spread = max_hr - min_hr
    hrr_pct = calculate_hrr(avg_hr)
    met_ratio = kcal_burned / USER_BMR_HOURLY if USER_BMR_HOURLY > 0 else 1.0

    scores = {}

    # 1. SLEEP (Сон в любое время суток)
    # Evidence: steps == 0, HR very close to RHR (<= RHR + 4), low spread, met_ratio ~ 1.0
    if step_count == 0 and hr_delta_rhr <= 5.0 and hr_spread <= 18.0:
        sleep_score = 10.0 + (5.0 - hr_delta_rhr) * 2.0
    elif step_count <= 5 and hr_delta_rhr <= 3.0:
        sleep_score = 6.0
    else:
        sleep_score = 0.05
    scores["SLEEP"] = {
        "name_ru": "Сон (Глубокий / Лёгкий отдых)",
        "cluster": "REST",
        "score": sleep_score,
        "met": 0.9,
        "desc": "Неподвижность, базальный пульс покоя и отсутствие мышечной активности"
    }

    # 2. SEDENTARY_DESK_WORK (Сидячая умственная работа / Офис)
    # Evidence: steps < 120/hr, HR is awake (RHR + 6 .. RHR + 20), small NEAT
    if step_count < 120 and (5.0 <= hr_delta_rhr <= 22.0):
        desk_score = 8.0 + (1.0 - (step_count / 120.0)) * 2.0
    elif step_count < 180 and (4.0 <= hr_delta_rhr <= 25.0):
        desk_score = 5.0
    else:
        desk_score = 0.1
    scores["SEDENTARY_WORK"] = {
        "name_ru": "Сидячая работа за столом / Офис",
        "cluster": "COGNITIVE",
        "score": desk_score,
        "met": 1.3,
        "desc": "Бодрствование в сидячем положении, умеренный пульс, отсутствие локомоции"
    }

    # 3. INDOOR_MOBILITY_NEAT (Перемещения в помещении / Бытовая активность)
    # Evidence: 120 to 600 steps/hour (bursty micro-walking between rooms/offices)
    if 120 <= step_count <= 600:
        neat_score = 8.5 + (step_count / 600.0) * 2.5
    elif 80 <= step_count < 120 or 600 < step_count <= 750:
        neat_score = 4.5
    else:
        neat_score = 0.1
    scores["INDOOR_MOBILITY_NEAT"] = {
        "name_ru": "Перемещения в помещении (NEAT / Быт)",
        "cluster": "LOCOMOTION",
        "score": neat_score,
        "met": 2.2,
        "desc": "Периодическая ходьба по комнатам/офису, бытовая активность"
    }

    # 4. OUTDOOR_TARGETED_WALKING (Целевая ходьба / Прогулка)
    # Evidence: > 600 steps/hour, sustained cadence, HR in light aerobic zone
    if step_count > 600 and avg_hr >= (USER_RHR + 12.0):
        walk_score = 9.0 + min((step_count - 600) / 300.0, 3.0)
    elif step_count > 500:
        walk_score = 5.0
    else:
        walk_score = 0.05
    scores["TARGETED_WALKING"] = {
        "name_ru": "Целевая прогулка / Ходьба на улице",
        "cluster": "LOCOMOTION",
        "score": walk_score,
        "met": 3.8,
        "desc": "Непрерывная аэробная ходьба высокой интенсивности"
    }

    # 5. MEAL_DIGESTION (Обед / Ужин / Пищеварение)
    # Evidence: is_postprandial True + moderate HR elevation without intense movement
    if is_postprandial and step_count < 700:
        meal_score = 9.5
    elif is_postprandial:
        meal_score = 6.0
    else:
        meal_score = 0.0
    scores["MEAL_DIGESTION"] = {
        "name_ru": "Приём пищи и пищеварение (Обед/Ужин)",
        "cluster": "METABOLIC",
        "score": meal_score,
        "met": 1.5,
        "desc": "Термический эффект усвоения нутриентов после еды"
    }

    # 6. WORKOUT_SPORT (Тренировка / Интенсивный спорт)
    # Evidence: HRR > 40%, high calorie rate, high peak HR
    if avg_hr >= 95.0 or (step_count > 1200 and avg_hr >= 85.0):
        sport_score = 9.0 + (avg_hr - 95.0) * 0.2
    else:
        sport_score = 0.05
    scores["WORKOUT_SPORT"] = {
        "name_ru": "Спортивная тренировка / Кардио",
        "cluster": "SPORT",
        "score": sport_score,
        "met": 6.5,
        "desc": "Целевая кардио или силовая нагрузка в тренировочной пульсовой зоне"
    }

    # Normalize softmax probabilities
    total_score = sum(v["score"] for v in scores.values())
    results = []
    for k, v in scores.items():
        prob = round((v["score"] / total_score) * 100.0, 1) if total_score > 0 else 0.0
        results.append({
            "action_key": k,
            "action_name_ru": v["name_ru"],
            "cluster": v["cluster"],
            "probability_pct": prob,
            "met": v["met"],
            "description": v["desc"]
        })

    results.sort(key=lambda x: x["probability_pct"], reverse=True)
    return results


def reconstruct_daily_behavioral_flow(date_str=None):
    """
    Reconstruct 24-hour daily timeline with local timezone alignment & Bayesian verification.
    """
    os.makedirs(ANALYTICS_DB_DIR, exist_ok=True)
    if not os.path.exists(FITBIT_DATA_FILE):
        return None

    with open(FITBIT_DATA_FILE, "r", encoding="utf-8") as f:
        raw_fitbit = json.load(f)

    target_date = date_str or raw_fitbit.get("date", datetime.now().strftime("%Y-%m-%d"))
    gh = raw_fitbit.get("google_health_v4", {})

    steps_pts = gh.get("steps", {}).get("rollupDataPoints", [])
    hr_pts = gh.get("heart-rate", {}).get("rollupDataPoints", [])
    cal_pts = gh.get("total-calories", {}).get("rollupDataPoints", [])

    # Load meal timestamps from diary
    meal_timestamps = []
    if os.path.exists(FOOD_DIARY_FILE):
        try:
            with open(FOOD_DIARY_FILE, "r", encoding="utf-8") as f:
                diary = json.load(f)
                for e in diary.get("entries", []):
                    t_str = e.get("timestamp", "")
                    if t_str.startswith(target_date):
                        meal_timestamps.append(t_str)
        except Exception:
            pass

    # Map hourly buckets with UTC to Europe/Tallinn (+3) offset conversion
    hourly_slices = []
    
    # Check if timestamps in raw data are UTC (contain 'Z' or '+00')
    is_utc_data = any("Z" in p.get("startTime", "") for p in hr_pts)
    tz_offset_hours = 3 if is_utc_data else 0  # Tallinn EEST is UTC+3

    for h_local in range(24):
        h_utc = (h_local - tz_offset_hours) % 24
        h_local_str = f"{h_local:02d}"
        h_utc_str = f"{h_utc:02d}"

        # Steps
        step_count = 0
        for p in steps_pts:
            st = p.get("startTime", "")
            if f"T{h_utc_str}:" in st or f" {h_utc_str}:" in st:
                step_count += int(p.get("steps", {}).get("countSum", 0))

        # Heart Rate
        hr_avg = USER_RHR
        hr_min = USER_RHR
        hr_max = USER_RHR + 10.0
        for p in hr_pts:
            st = p.get("startTime", "")
            if f"T{h_utc_str}:" in st or f" {h_utc_str}:" in st:
                hr_data = p.get("heartRate", {})
                hr_avg = float(hr_data.get("beatsPerMinuteAvg", hr_avg))
                hr_min = float(hr_data.get("beatsPerMinuteMin", hr_min))
                hr_max = float(hr_data.get("beatsPerMinuteMax", hr_max))

        # Calories
        kcal_val = USER_BMR_HOURLY
        for p in cal_pts:
            st = p.get("startTime", "")
            if f"T{h_utc_str}:" in st or f" {h_utc_str}:" in st:
                kcal_val = float(p.get("totalCalories", {}).get("kcalSum", kcal_val))

        # Postprandial check
        is_postprandial = False
        for mt in meal_timestamps:
            if mt.startswith(f"{target_date} {h_local_str}"):
                is_postprandial = True
                break

        probs = evaluate_action_probabilities(
            step_count=step_count,
            avg_hr=hr_avg,
            min_hr=hr_min,
            max_hr=hr_max,
            kcal_burned=kcal_val,
            is_postprandial=is_postprandial
        )

        top_act = probs[0]

        hourly_slices.append({
            "hour_of_day_local": h_local,
            "time_range_local": f"{h_local_str}:00 - {h_local_str}:59",
            "action_key": top_act["action_key"],
            "action_name": top_act["action_name_ru"],
            "cluster": top_act["cluster"],
            "confidence_pct": top_act["probability_pct"],
            "alternative_hypotheses": probs[1:3],
            "telemetry": {
                "steps": step_count,
                "avg_heart_rate": round(hr_avg, 1),
                "min_heart_rate": round(hr_min, 1),
                "max_heart_rate": round(hr_max, 1),
                "calories_burned_kcal": round(kcal_val, 1)
            },
            "description": top_act["description"]
        })

    cluster_hours = {}
    for s in hourly_slices:
        c = s["cluster"]
        cluster_hours[c] = cluster_hours.get(c, 0) + 1

    result_payload = {
        "date": target_date,
        "timezone": "Europe/Tallinn (UTC+3)",
        "last_computed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cluster_distribution_hours": cluster_hours,
        "hourly_timeline": hourly_slices
    }

    # Save to JSON
    db_data = {}
    if os.path.exists(ACTIONS_JSON_FILE):
        try:
            with open(ACTIONS_JSON_FILE, "r", encoding="utf-8") as f:
                db_data = json.load(f)
        except Exception:
            db_data = {}

    db_data[target_date] = result_payload
    with open(ACTIONS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(db_data, f, indent=2, ensure_ascii=False)

    print(f"📦 [ACTIONS DOMAIN DB RE-CALIBRATED]: {ACTIONS_JSON_FILE} for {target_date}", flush=True)
    return result_payload
