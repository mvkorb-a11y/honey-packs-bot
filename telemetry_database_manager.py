#!/usr/bin/env python3
"""
High-Performance Sensor Telemetry Storage & Partitioning Manager
Project: Honey Packs Health AI

Solves the Big Data Telemetry Storage problem:
1. 26-Metric Sensor History Table (`fitbit_telemetry_history.csv`).
2. Monthly/Daily Partitioning (`telemetry_logs/YYYY-MM_telemetry.json`) to prevent monolithic file bloat.
3. Compact Daily Rollup Table for Excel / Numbers.
"""

import os
import json
import gzip
from datetime import datetime, timedelta

TELEMETRY_DIR = "telemetry_logs"
TELEMETRY_CSV_FILE = "fitbit_telemetry_history.csv"
TELEMETRY_MASTER_JSON = "fitbit_telemetry_history.json"


def ensure_telemetry_dir():
    """Create telemetry partition storage directory."""
    os.makedirs(TELEMETRY_DIR, exist_ok=True)


def get_partition_filename(date_str):
    """Return monthly partition filename e.g. telemetry_logs/2026-08_telemetry.json."""
    ensure_telemetry_dir()
    month_str = date_str[:7] if len(date_str) >= 7 else datetime.now().strftime("%Y-%m")
    return os.path.join(TELEMETRY_DIR, f"{month_str}_telemetry.json")


def save_high_res_telemetry_partition(date_str, raw_data):
    """Save high-resolution telemetry payload into monthly partition file."""
    partition_file = get_partition_filename(date_str)
    
    partition_data = {}
    if os.path.exists(partition_file):
        try:
            with open(partition_file, "r", encoding="utf-8") as f:
                partition_data = json.load(f)
        except Exception:
            partition_data = {}

    partition_data[date_str] = raw_data
    with open(partition_file, "w", encoding="utf-8") as f:
        json.dump(partition_data, f, indent=2, ensure_ascii=False)

    print(f"📦 [TELEMETRY PARTITION SAVED]: {partition_file} (Date: {date_str})", flush=True)


def append_telemetry_csv_row(date_str, time_str, telem_data):
    """Append a clean row for all 26 metrics + sampling frequencies into fitbit_telemetry_history.csv."""
    file_exists = os.path.exists(TELEMETRY_CSV_FILE)
    
    headers = [
        "Дата", "Время", "Частота снятия",
        # Cardiovascular (1-6)
        "Пульс BPM (1s)", "Пульс покоя BPM (Daily)", "HRV rMSSD ms (Sleep)", "HRV SDNN ms (Daily)", "AZM Минуты (Minutely)", "VO2 Max (Workout)",
        # Sleep & Respiratory (7-15)
        "Сон Часы (Daily)", "Глубокий Сон Мин (Daily)", "REM Сон Мин (Daily)", "Легкий Сон Мин (Daily)", "Пробуждения Мин (Daily)", "Эффективность Сна % (Daily)", "Индекс Сна (Daily)", "SpO2 % (Minutely)", "Частота Дыхания RPM (Daily)",
        # Stress & cEDA (16-18)
        "cEDA События (Continuous)", "Стресс Всплески (Fact)", "Индекс Стресса (Daily)",
        # Thermal (19-20)
        "Температура Кожи Отклонение °C (Minutely)", "Базовая Температура °C (7-Day)",
        # Locomotion & Altimeter (21-24)
        "Шаги Count (Minutely)", "Дистанция KM (Minutely)", "Этажи Climbed (Fact)", "Длительность Спорта Мин (Fact)",
        # Metabolic (25-26)
        "Активный Расход ккал (Minutely)", "TDEE Расход ккал (Daily)"
    ]

    cardio = telem_data.get("cardiovascular_domain", {})
    sleep = telem_data.get("sleep_respiratory_domain", {})
    stress = telem_data.get("stress_ceda_domain", {})
    thermal = telem_data.get("thermal_domain", {})
    locomotion = telem_data.get("locomotion_altimeter_domain", {})
    metabolic = telem_data.get("metabolic_domain", {})

    row = [
        date_str, time_str, "Гибридная (1s - Daily)",
        cardio.get("1_heart_rate_bpm", 0), cardio.get("2_resting_hr_bpm", 0), cardio.get("3_hrv_rmssd_ms", 0), cardio.get("4_hrv_sdnn_ms", 0), cardio.get("5_active_zone_minutes", 0), cardio.get("6_vo2_max", 0),
        sleep.get("7_sleep_duration_hours", 0), sleep.get("8_sleep_deep_minutes", 0), sleep.get("9_sleep_rem_minutes", 0), sleep.get("10_sleep_light_minutes", 0), sleep.get("11_sleep_awake_minutes", 0), sleep.get("12_sleep_efficiency_pct", 0), sleep.get("13_sleep_score", 0), sleep.get("14_spo2_pct", 0), sleep.get("15_breathing_rate_rpm", 0),
        stress.get("16_ceda_body_responses", 0), stress.get("17_stress_events_count", 0), stress.get("18_stress_management_score", 0),
        thermal.get("19_skin_temp_variation_c", 0), thermal.get("20_baseline_skin_temp_c", 0),
        locomotion.get("21_steps_count", 0), locomotion.get("22_distance_km", 0), locomotion.get("23_floors_climbed", 0), locomotion.get("24_active_sport_duration_min", 0),
        metabolic.get("25_active_calories_kcal", 0), metabolic.get("26_tdee_calories_kcal", 0)
    ]

    with open(TELEMETRY_CSV_FILE, "a", encoding="utf-8-sig") as f:
        if not file_exists:
            f.write(";".join(headers) + "\n")
        f.write(";".join(str(x) for x in row) + "\n")

    print(f"📊 [TELEMETRY CSV UPDATED]: {TELEMETRY_CSV_FILE} ({date_str} {time_str})", flush=True)


def archive_old_partitions(days_to_keep=60):
    """Gzip compress partitions older than days_to_keep to save 90% disk space."""
    ensure_telemetry_dir()
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    for filename in os.listdir(TELEMETRY_DIR):
        if filename.endswith(".json") and not filename.endswith(".gz"):
            filepath = os.path.join(TELEMETRY_DIR, filename)
            # Check file modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff_date:
                gz_path = filepath + ".gz"
                with open(filepath, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                    f_out.writelines(f_in)
                os.remove(filepath)
                print(f"🗜️ [COMPRESSED OLD LOGS]: {gz_path}", flush=True)


if __name__ == "__main__":
    ensure_telemetry_dir()
    sample_telem = {
        "cardiovascular_domain": {"1_heart_rate_bpm": 68, "2_resting_hr_bpm": 48, "3_hrv_rmssd_ms": 65, "4_hrv_sdnn_ms": 78, "5_active_zone_minutes": 45, "6_vo2_max": 48},
        "sleep_respiratory_domain": {"7_sleep_duration_hours": 7.5, "8_sleep_deep_minutes": 95, "9_sleep_rem_minutes": 110, "10_sleep_light_minutes": 245, "11_sleep_awake_minutes": 28, "12_sleep_efficiency_pct": 91, "13_sleep_score": 88, "14_spo2_pct": 97, "15_breathing_rate_rpm": 14},
        "stress_ceda_domain": {"16_ceda_body_responses": 12, "17_stress_events_count": 3, "18_stress_management_score": 82},
        "thermal_domain": {"19_skin_temp_variation_c": -0.2, "20_baseline_skin_temp_c": 34.8},
        "locomotion_altimeter_domain": {"21_steps_count": 12022, "22_distance_km": 9.22, "23_floors_climbed": 14, "24_active_sport_duration_min": 45},
        "metabolic_domain": {"25_active_calories_kcal": 1576, "26_tdee_calories_kcal": 4132}
    }
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")
    save_high_res_telemetry_partition(today_str, sample_telem)
    append_telemetry_csv_row(today_str, now_time, sample_telem)
