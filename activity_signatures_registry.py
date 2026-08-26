#!/usr/bin/env python3
"""
Activity Signatures Registry & Metric Thresholds
Project: Honey Packs Health AI - Tier 2 Analytics Engine

Defines 24 physiological & kinematic activity signatures in multi-dimensional feature space:
- Cadence (SPM - Steps Per Minute)
- Heart Rate Reserve Zone (%HRR)
- Acceleration Magnitude (g)
- Spatial Velocity (km/h)
- Physiological/Metabolic Markers (cEDA, TEF)
"""

# Reference physiological maximums
DEFAULT_AGE = 46
DEFAULT_RHR = 49.8
DEFAULT_HR_MAX = 220 - DEFAULT_AGE  # 174 BPM


ACTIVITY_SIGNATURES = {
    # CLUSTER 1: Static & Deep Rest
    "SLEEP_DEEP": {
        "id": "ACT_01",
        "name_ru": "Глубокий ночной сон",
        "cluster": "REST",
        "cadence_min": 0, "cadence_max": 0,
        "hrr_min_pct": 0, "hrr_max_pct": 6,
        "accel_g": 0.02,
        "speed_kmh": 0.0,
        "met_score": 0.9,
        "description": "Глубокое восстановление и медленноволновой сон"
    },
    "SLEEP_REM_LIGHT": {
        "id": "ACT_02",
        "name_ru": "Быстрый / Лёгкий сон",
        "cluster": "REST",
        "cadence_min": 0, "cadence_max": 0,
        "hrr_min_pct": 3, "hrr_max_pct": 9,
        "accel_g": 0.04,
        "speed_kmh": 0.0,
        "met_score": 0.95,
        "description": "Фаза сновидений и нейропластического восстановления"
    },
    "MEDITATION_RELAX": {
        "id": "ACT_03",
        "name_ru": "Медитация / Релаксация",
        "cluster": "REST",
        "cadence_min": 0, "cadence_max": 1,
        "hrr_min_pct": 4, "hrr_max_pct": 10,
        "accel_g": 0.03,
        "speed_kmh": 0.0,
        "met_score": 1.0,
        "description": "Осознанное дыхание, дневной отдых или медитация"
    },
    "PASSIVE_REST": {
        "id": "ACT_04",
        "name_ru": "Пассивный отдых (чтение / кино)",
        "cluster": "REST",
        "cadence_min": 0, "cadence_max": 3,
        "hrr_min_pct": 6, "hrr_max_pct": 14,
        "accel_g": 0.05,
        "speed_kmh": 0.0,
        "met_score": 1.2,
        "description": "Спокойное сидение / лежание в вечернее время"
    },

    # CLUSTER 2: Cognitive, Mental & Postprandial
    "SEDENTARY_WORK": {
        "id": "ACT_05",
        "name_ru": "Сидячая умственная работа (Офис)",
        "cluster": "COGNITIVE",
        "cadence_min": 0, "cadence_max": 8,
        "hrr_min_pct": 9, "hrr_max_pct": 24,
        "accel_g": 0.05,
        "speed_kmh": 0.0,
        "met_score": 1.3,
        "description": "Работа за компьютером, анализ данных, документация"
    },

    "COGNITIVE_STRESS": {
        "id": "ACT_06",
        "name_ru": "Умственный стресс / Переговоры",
        "cluster": "COGNITIVE",
        "cadence_min": 0, "cadence_max": 10,
        "hrr_min_pct": 25, "hrr_max_pct": 48,
        "accel_g": 0.08,
        "speed_kmh": 0.0,
        "met_score": 1.5,
        "description": "Высокая ментальная нагрузка, симпатический спайк без движения"
    },
    "MEAL_DIGESTION": {
        "id": "ACT_08",
        "name_ru": "Приём пищи и пищеварение (TEF)",
        "cluster": "METABOLIC",
        "cadence_min": 0, "cadence_max": 15,
        "hrr_min_pct": 15, "hrr_max_pct": 30,
        "accel_g": 0.06,
        "speed_kmh": 0.0,
        "met_score": 1.4,
        "description": "Термический эффект пищи, усвоение нутриентов"
    },

    # CLUSTER 3: Passive Locomotion & Vehicles
    "COMMUTE_DRIVING": {
        "id": "ACT_09",
        "name_ru": "Вождение автомобиля",
        "cluster": "TRANSPORT",
        "cadence_min": 0, "cadence_max": 4,
        "hrr_min_pct": 12, "hrr_max_pct": 32,
        "accel_g": 0.12,
        "speed_kmh": 45.0,
        "met_score": 1.5,
        "description": "Управление автотранспортом (нулевой каденс + вибрация)"
    },
    "HORSE_RIDING": {
        "id": "ACT_12",
        "name_ru": "Верховая езда",
        "cluster": "TRANSPORT",
        "cadence_min": 0, "cadence_max": 10,
        "hrr_min_pct": 30, "hrr_max_pct": 60,
        "accel_g": 0.55,
        "speed_kmh": 18.0,
        "met_score": 4.5,
        "description": "Ритмические вертикальные колебания туловища при верховой езде"
    },

    # CLUSTER 4: Locomotion & NEAT
    "LIGHT_NEAT_MOVEMENT": {
        "id": "ACT_13",
        "name_ru": "Бытовая микроактивность (NEAT)",
        "cluster": "LOCOMOTION",
        "cadence_min": 10, "cadence_max": 35,
        "hrr_min_pct": 15, "hrr_max_pct": 28,
        "accel_g": 0.18,
        "speed_kmh": 1.5,
        "met_score": 2.0,
        "description": "Перемещения по дому/офису, мелкие бытовые задачи"
    },
    "TARGETED_WALKING": {
        "id": "ACT_14",
        "name_ru": "Целевая прогулка / Ходьба",
        "cluster": "LOCOMOTION",
        "cadence_min": 50, "cadence_max": 105,
        "hrr_min_pct": 25, "hrr_max_pct": 45,
        "accel_g": 0.35,
        "speed_kmh": 5.0,
        "met_score": 3.5,
        "description": "Непрерывная аэробная ходьба на свежем воздухе"
    },
    "STAIR_CLIMBING": {
        "id": "ACT_15",
        "name_ru": "Подъём по лестнице / В гору",
        "cluster": "LOCOMOTION",
        "cadence_min": 40, "cadence_max": 90,
        "hrr_min_pct": 45, "hrr_max_pct": 75,
        "accel_g": 0.45,
        "speed_kmh": 2.5,
        "met_score": 6.0,
        "description": "Вертикальное преодоление гравитации с резким ростом пульса"
    },

    # CLUSTER 5: Aerobic Sports
    "RUNNING_JOGGING": {
        "id": "ACT_17",
        "name_ru": "Бег / Кардиотренировка",
        "cluster": "SPORT",
        "cadence_min": 120, "cadence_max": 185,
        "hrr_min_pct": 50, "hrr_max_pct": 85,
        "accel_g": 0.95,
        "speed_kmh": 9.5,
        "met_score": 8.5,
        "description": "Ритмический бег, высокая аэробная мощность"
    },
    "CYCLING": {
        "id": "ACT_19",
        "name_ru": "Езда на велосипеде",
        "cluster": "SPORT",
        "cadence_min": 0, "cadence_max": 15,  # Steps cadence is 0 on bike
        "hrr_min_pct": 40, "hrr_max_pct": 75,
        "accel_g": 0.25,
        "speed_kmh": 22.0,
        "met_score": 6.8,
        "description": "Велосипедная нагрузка (высокая скорость, пульс при нуле шагов)"
    },

    # CLUSTER 6: Strength & Resistance
    "STRENGTH_WORKOUT": {
        "id": "ACT_22",
        "name_ru": "Силовая тренировка / ОФП",
        "cluster": "SPORT",
        "cadence_min": 0, "cadence_max": 25,
        "hrr_min_pct": 35, "hrr_max_pct": 80,
        "accel_g": 0.65,
        "speed_kmh": 0.0,
        "met_score": 5.5,
        "description": "Интервальная силовая работа с отягощениями или весом тела"
    }
}


def calculate_hrr_percentage(current_hr, rhr=DEFAULT_RHR, hr_max=DEFAULT_HR_MAX):
    """Calculate Heart Rate Reserve percentage (%HRR) using Karvonen formula."""
    if current_hr <= rhr:
        return 0.0
    hrr_val = ((current_hr - rhr) / (hr_max - rhr)) * 100.0
    return min(max(hrr_val, 0.0), 100.0)
