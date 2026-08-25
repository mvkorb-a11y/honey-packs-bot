#!/usr/bin/env python3
"""
Raw Hardware Sensor Series Packager (Tier 1 Ingestion Engine)
Project: Honey Packs Health AI

Pure 0-calculation packaging of raw time series streams into standardized
Sensor Series payloads for Tier 2 Analytics Engine to query cleanly.
"""

import os
import json
from datetime import datetime

SENSOR_PACKAGES_DIR = os.path.join("telemetry_logs", "sensor_series")


def ensure_sensor_packages_dir():
    """Create directory for packaged raw sensor series."""
    os.makedirs(SENSOR_PACKAGES_DIR, exist_ok=True)


def package_raw_sensor_series(date_str, raw_streams):
    """
    Package raw time series streams into 6 standardized Hardware Sensor Series.
    0 Calculations. Pure packaging with standardized sensor IDs and keys.
    """
    ensure_sensor_packages_dir()

    packaged_sensors = {
        "date": date_str,
        "packaged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hardware_platform": "Fitbit Air (Google Health API v4 / Wear OS)",
        "sensor_series_count": 6,
        "sensors": {

            # Sensor Series 1: PPG Optical Heart Rate (1Hz Sampling)
            "SENSOR_PPG_OPTICAL": {
                "sensor_id": "ppg_green_ir_leds",
                "sensor_name": "PPG Optical Heart Rate & HRV Pulse Sensor",
                "sampling_frequency": "1Hz (1 sample per second)",
                "unit": "BPM & Milliseconds",
                "data_points_count": len(raw_streams.get("ppg_1s_intraday_stream", [])),
                "raw_time_series": raw_streams.get("ppg_1s_intraday_stream", [])
            },

            # Sensor Series 2: cEDA Electrodermal Activity (Continuous Micro-Amps)
            "SENSOR_CEDA_STRESS": {
                "sensor_id": "ceda_microamperage_electrodes",
                "sensor_name": "cEDA Continuous Electrodermal Activity Sensor",
                "sampling_frequency": "Continuous Micro-Amp Event Stream",
                "unit": "Micro-Siemens (\u03bcS)",
                "data_points_count": len(raw_streams.get("ceda_continuous_events", [])),
                "raw_time_series": raw_streams.get("ceda_continuous_events", [])
            },

            # Sensor Series 3: Infrared Skin Thermometer (1m Sampling)
            "SENSOR_INFRARED_TEMP": {
                "sensor_id": "ir_skin_thermometer",
                "sensor_name": "Infrared Surface Skin Temperature Sensor",
                "sampling_frequency": "1 sample per minute",
                "unit": "Celsius (\u00b0C)",
                "data_points_count": len(raw_streams.get("infrared_temp_1m_array", [])),
                "raw_time_series": raw_streams.get("infrared_temp_1m_array", [])
            },

            # Sensor Series 4: 3-Axis Accelerometer & Gyroscope (50Hz Epochs)
            "SENSOR_ACCELEROMETER": {
                "sensor_id": "accel_3axis_gyro",
                "sensor_name": "3-Axis Motion Accelerometer & Gyroscope",
                "sampling_frequency": "50Hz Motion Epochs",
                "unit": "Steps Delta & Movement Vectors",
                "data_points_count": len(raw_streams.get("accel_motion_epochs", [])),
                "raw_time_series": raw_streams.get("accel_motion_epochs", [])
            },

            # Sensor Series 5: Barometric Altimeter (1Hz Pressure Deltas)
            "SENSOR_BAROMETRIC_ALTIMETER": {
                "sensor_id": "barometric_altimeter_pressure",
                "sensor_name": "Barometric Altitude & Pressure Sensor",
                "sampling_frequency": "1Hz Event-driven Elevation Deltas",
                "unit": "Floors & Meters Altitude",
                "data_points_count": len(raw_streams.get("altimeter_events", [])),
                "raw_time_series": raw_streams.get("altimeter_events", [])
            },

            # Sensor Series 6: GPS & GLONASS Outdoor Locomotion (1Hz)
            "SENSOR_GPS_LOCOMOTION": {
                "sensor_id": "gps_glonass_locomotion",
                "sensor_name": "GPS / GLONASS Outdoor Locomotion & Speed Sensor",
                "sampling_frequency": "1Hz (1 sample per second on active sports)",
                "unit": "Coordinates, Speed (Knots/KMH) & Elevation",
                "data_points_count": len(raw_streams.get("gps_1s_locomotion_stream", [])),
                "raw_time_series": raw_streams.get("gps_1s_locomotion_stream", [])
            }
        }
    }

    target_file = os.path.join(SENSOR_PACKAGES_DIR, f"{date_str}_sensor_package.json")
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(packaged_sensors, f, indent=2, ensure_ascii=False)

    print(f"📦 [SENSOR SERIES PACKAGED]: Saved 6 raw sensor series to {target_file}", flush=True)
    return target_file


if __name__ == "__main__":
    today_str = datetime.now().strftime("%Y-%m-%d")
    sample_raw = {
        "ppg_1s_intraday_stream": [{"time": "00:00:01", "bpm": 68}, {"time": "00:00:02", "bpm": 69}],
        "ceda_continuous_events": [{"time": "08:14:22.104", "micro_siemens": 4.25}],
        "infrared_temp_1m_array": [{"time": "02:01:00", "skin_temp_c": 34.6}],
        "accel_motion_epochs": [{"time": "12:00:00", "steps_delta": 15}],
        "altimeter_events": [{"time": "14:10:05", "altitude_m": 12.5}],
        "gps_1s_locomotion_stream": [{"time": "16:00:01", "speed_knots": 22.4}]
    }
    package_raw_sensor_series(today_str, sample_raw)
