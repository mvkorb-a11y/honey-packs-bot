#!/usr/bin/env python3
"""
Tier 1: Data Ingestion Center (Honey Packs Health AI)
Project: Honey Packs Health AI

Role:
- Light, fast, cost-effective ingestion of raw user data (Voice, Text, Photo, Fitbit API).
- Raw Speech-to-Text transcription via Gemini Flash / Wav converter.
- Basic food tagging & nutrition parsing.
- Direct JSON & Excel CSV writing (food_diary.json & food_diary.csv).
"""

import os
import sys
import json
import time
import base64
import re
import subprocess
import requests
from datetime import datetime

DIARY_FILE = "food_diary.json"
DIARY_CSV_FILE = "food_diary.csv"
GEMINI_CONFIG_FILE = "gemini_config.json"
USER_PROFILE_FILE = "user_profile.json"


def get_gemini_api_key():
    """Retrieve Gemini API Key from environment or config file."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]

    if os.path.exists(GEMINI_CONFIG_FILE):
        with open(GEMINI_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if cfg.get("gemini_api_key"):
                return cfg["gemini_api_key"]
    return None


def get_gemini_model():
    """Retrieve light model name for fast ingestion."""
    if os.path.exists(GEMINI_CONFIG_FILE):
        with open(GEMINI_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if cfg.get("model_name"):
                return cfg["model_name"]
    return "gemini-1.5-flash"


def convert_ogg_to_wav(ogg_path):
    """Convert Telegram OGG Opus audio file to WAV using ffmpeg if available."""
    if not os.path.exists(ogg_path):
        return ogg_path
    
    wav_path = ogg_path.rsplit(".", 1)[0] + ".wav"
    try:
        cmd = ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if res.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
            return wav_path
    except Exception:
        pass
    return ogg_path


CUSTOM_RECIPES_FILE = "my_custom_recipes.json"


def match_custom_recipe(text):
    """Check if incoming text matches user custom recurring meals catalog."""
    if not text or not os.path.exists(CUSTOM_RECIPES_FILE):
        return None
    
    try:
        with open(CUSTOM_RECIPES_FILE, "r", encoding="utf-8") as f:
            catalog = json.load(f)
            recipes = catalog.get("recipes", [])
            
        text_lower = text.lower().strip()
        for r in recipes:
            for kw in r.get("keywords", []):
                if kw.lower() in text_lower:
                    match_res = dict(r)
                    match_res["intent"] = "FOOD_LOG"
                    match_res["transcribed_text"] = text
                    print(f"🎯 [CUSTOM RECIPE MATCHED]: {match_res['meal_name']}", flush=True)
                    return match_res
    except Exception as e:
        print(f"Recipe catalog check error: {e}", flush=True)
    return None


def parse_raw_food_input(text_or_dict, image_path=None, audio_path=None):
    """Ingest raw user input via light Gemini Flash in 1 single call with custom recipe matching."""
    text_input = text_or_dict if isinstance(text_or_dict, str) else text_or_dict.get("text", "")
    
    # 1. Fast match against personal custom recipe catalog
    if text_input and not image_path and not audio_path:
        custom_match = match_custom_recipe(text_input)
        if custom_match:
            return custom_match

    api_key = get_gemini_api_key()
    if not api_key:
        return None

    model_name = get_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    prompt = text_input
    if audio_path and not prompt:
        prompt = "Послушай эту голосовую аудиозапись. Распознай её дословно в 'transcribed_text' и выполни первичный разбор КБЖУ."


    system_instruction = (
        "You are a fast FoodTech data ingestion parser.\n"
        "FOR AUDIO VOICE NOTES: Transcribe spoken audio text word-for-word into Russian in 'transcribed_text'.\n"
        "Respond ONLY with a JSON object in one of two schemas:\n\n"
        "SCHEMA 1 (FOOD_LOG):\n"
        "{\n"
        '  "intent": "FOOD_LOG",\n'
        '  "transcribed_text": "Word-for-word speech transcription",\n'
        '  "meal_name": "Name of Food in Russian",\n'
        '  "meal_type": "Breakfast | Lunch | Snack | Dinner",\n'
        '  "estimated_weight_g": 250,\n'
        '  "calories": 350,\n'
        '  "protein_g": 20.0,\n'
        '  "fat_g": 10.0,\n'
        '  "carbs_g": 40.0,\n'
        '  "fiber_g": 4.0,\n'
        '  "sugar_g": 8.0,\n'
        '  "amino_acids": {"lysine_g": 1.4, "leucine_g": 1.8, "tryptophan_g": 0.3, "methionine_g": 0.5},\n'
        '  "vitamins_minerals": {"magnesium_mg": 75, "zinc_mg": 2.5, "iron_mg": 2.2, "vitamin_c_mg": 10, "vitamin_d_mcg": 1.5, "vitamin_b12_mcg": 0.8, "potassium_mg": 350, "calcium_mg": 120},\n'
        '  "omega_3_6": {"omega3_g": 0.4, "omega6_g": 1.2}\n'
        "}\n\n"
        "SCHEMA 2 (QUESTION_OR_CHAT):\n"
        "{\n"
        '  "intent": "QUESTION_OR_CHAT",\n'
        '  "transcribed_text": "Word-for-word speech transcription",\n'
        '  "ai_reply": "Friendly response in Russian"\n'
        "}"
    )

    parts = [{"text": f"{system_instruction}\n\nUser Input: {prompt}"}]

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_data}})

    if audio_path and os.path.exists(audio_path):
        target_path = convert_ogg_to_wav(audio_path)
        mime_type = "audio/wav" if target_path.endswith(".wav") else "audio/ogg"
        with open(target_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")
        parts.append({"inline_data": {"mime_type": mime_type, "data": audio_data}})

    payload = {"contents": [{"parts": parts}]}
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if r.status_code == 200:
            res_json = r.json()
            candidates = res_json.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts_resp = candidates[0]["content"].get("parts", [])
                if parts_resp and "text" in parts_resp[0]:
                    text_resp = parts_resp[0]["text"].strip()
                    text_resp = re.sub(r"^```json\s*", "", text_resp)
                    text_resp = re.sub(r"^```\s*", "", text_resp)
                    text_resp = re.sub(r"\s*```$", "", text_resp).strip()
                    json_match = re.search(r"\{.*\}", text_resp, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(0))
    except Exception as e:
        print(f"Ingestion error: {e}", flush=True)

    return None


def commit_raw_meal(meal_data, source="LIBRARY"):
    """
    Save meal entry into food_diary.json & food_diary.csv under Strict Write Authorization Rule.
    Authorized sources: 'LIBRARY' (my_custom_recipes.json), 'ANALYTICS_ENGINE' (Tier 2), 'APP' (App UI).
    """
    authorized_sources = ["LIBRARY", "ANALYTICS_ENGINE", "APP"]
    is_custom_matched = meal_data.get("source") == "LIBRARY" or meal_data.get("is_custom_matched") is True
    
    if source not in authorized_sources and not is_custom_matched:
        print(f"⚠️ [WRITE REJECTED]: Unverified write source '{source}'. Entries must originate from LIBRARY, ANALYTICS_ENGINE or APP.", flush=True)
        return None

    diary = {"entries": []}
    if os.path.exists(DIARY_FILE):
        try:
            with open(DIARY_FILE, "r", encoding="utf-8") as f:
                diary = json.load(f)
        except Exception:
            diary = {"entries": []}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meal_entry = {
        "id": meal_data.get("meal_id", str(time.time())),
        "timestamp": meal_data.get("timestamp", now_str),
        "meal_name": meal_data.get("meal_name", "Приём пищи"),
        "meal_type": meal_data.get("meal_type", "Meal"),
        "estimated_weight_g": meal_data.get("estimated_weight_g", 250),
        "calories": meal_data.get("calories", 0),
        "protein_g": meal_data.get("protein_g", 0),
        "fat_g": meal_data.get("fat_g", 0),
        "carbs_g": meal_data.get("carbs_g", 0),
        "fiber_g": meal_data.get("fiber_g", 0),
        "sugar_g": meal_data.get("sugar_g", 0),
        "transcribed_text": meal_data.get("transcribed_text", ""),
        "source": "LIBRARY" if is_custom_matched else source,
        "amino_acids": meal_data.get("amino_acids", {}),
        "vitamins_minerals": meal_data.get("vitamins_minerals", {}),
        "omega_3_6": meal_data.get("omega_3_6", {})
    }

    diary.setdefault("entries", []).append(meal_entry)
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(diary, f, indent=2, ensure_ascii=False)

    # Write CSV row (UTF-8 BOM)
    file_exists = os.path.exists(DIARY_CSV_FILE)
    with open(DIARY_CSV_FILE, "a", encoding="utf-8-sig") as f:
        if not file_exists:
            f.write("Дата и время;ID;Источник;Название блюда;Калории (ккал);Белок (г);Жиры (г);Углеводы (г);Клетчатка (г);Магний (мг);Цинк (мг);Железо (мг);Витамин C (мг);Витамин D (мкг);Витамин B12 (мкг);Калий (мг);Кальций (мг);Лизин (г);Триптофан (г)\n")
        
        vm = meal_entry.get("vitamins_minerals", {})
        aa = meal_entry.get("amino_acids", {})
        line = f"{meal_entry['timestamp']};{meal_entry['id']};{meal_entry['source']};{meal_entry['meal_name']};{meal_entry['calories']};{meal_entry['protein_g']};{meal_entry['fat_g']};{meal_entry['carbs_g']};{meal_entry['fiber_g']};{vm.get('magnesium_mg', 0)};{vm.get('zinc_mg', 0)};{vm.get('iron_mg', 0)};{vm.get('vitamin_c_mg', 0)};{vm.get('vitamin_d_mcg', 0)};{vm.get('vitamin_b12_mcg', 0)};{vm.get('potassium_mg', 0)};{vm.get('calcium_mg', 0)};{aa.get('lysine_g', 0)};{aa.get('tryptophan_g', 0)}\n"
        f.write(line)

    print(f"✅ [AUTHORIZED WRITE SUCCESS] Source: {meal_entry['source']} | Dish: {meal_entry['meal_name']}", flush=True)
    return meal_entry


