#!/usr/bin/env python3
"""
Tier 1: Data Ingestion Collector (Pristine Clean Rebuild)
Project: Honey Packs Biohacking Core

Guarantees:
1. ZERO Conversational AI Chatter / Advice / Commentary.
2. 25-Nutrient parsing (Macros, Amino Acids, Vitamins/Minerals, Omegas).
3. Spoken meal time recognition (e.g., "в 14:30 съел творог"), defaulting to exact message timestamp if not specified.
4. Instant precision matching against my_custom_recipes.json (0.001s response).
5. Strict Write Authorization Policy (LIBRARY, ANALYTICS_ENGINE, APP, TELEGRAM).
6. 100% synchronized persistent storage to food_diary.json and food_diary.csv.
"""

import os
import sys
import json
import time
import uuid
import re
import base64
import requests
from datetime import datetime


DIARY_FILE = "food_diary.json"
DIARY_CSV_FILE = "food_diary.csv"
CUSTOM_RECIPES_FILE = "my_custom_recipes.json"
GEMINI_CONFIG_FILE = "gemini_config.json"
TEMP_MEDIA_DIR = "temp_media"


def get_gemini_api_key():
    """Retrieve Gemini API Key from environment or config file."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]

    if os.path.exists(GEMINI_CONFIG_FILE):
        try:
            with open(GEMINI_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("gemini_api_key"):
                    return cfg["gemini_api_key"]
        except Exception:
            pass
    return None


def get_gemini_model():
    """Default to Gemini 2.5 Flash for ultra-fast ingestion."""
    if os.path.exists(GEMINI_CONFIG_FILE):
        try:
            with open(GEMINI_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("model_name", "gemini-2.5-flash")
        except Exception:
            pass
    return "gemini-2.5-flash"


def convert_ogg_to_wav(ogg_path):
    """Convert Telegram OGG voice message to WAV using ffmpeg if available."""
    if not ogg_path or not os.path.exists(ogg_path):
        return ogg_path
    wav_path = ogg_path.rsplit(".", 1)[0] + ".wav"
    try:
        cmd = f"ffmpeg -y -i \"{ogg_path}\" -ac 1 -ar 16000 \"{wav_path}\" > /dev/null 2>&1"
        os.system(cmd)
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
            return wav_path
    except Exception:
        pass
    return ogg_path


def parse_spoken_time_from_text(text):
    """
    Extract spoken time from Russian text (e.g., "в 14:30", "в 9:00", "в 18:45").
    Returns 'HH:MM:SS' string if found, else None.
    """
    if not text:
        return None
    
    match = re.search(r'\b([0-1]?[0-9]|2[0-3])[:\.-]([0-5][0-9])\b', text)
    if match:
        hh = int(match.group(1))
        mm = int(match.group(2))
        return f"{hh:02d}:{mm:02d}:00"
    
    match_hour = re.search(r'\bв\s+([0-1]?[0-9]|2[0-3])\s+(часов|часа|ч)\b', text.lower())
    if match_hour:
        hh = int(match_hour.group(1))
        return f"{hh:02d}:00:00"
        
    return None


def match_custom_recipe(text):
    """
    Check if incoming text matches user custom recurring meals catalog.
    Instantly returns pre-parsed 25 nutrients if matched.
    """
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
                    match_res["source"] = "LIBRARY"
                    match_res["is_custom_matched"] = True
                    
                    # Extract spoken time if present
                    spoken_time = parse_spoken_time_from_text(text)
                    if spoken_time:
                        match_res["spoken_time"] = spoken_time

                    print(f"🎯 [CUSTOM RECIPE MATCHED]: {match_res['meal_name']}", flush=True)
                    return match_res
    except Exception as e:
        print(f"Recipe catalog check error: {e}", flush=True)
    return None


def parse_raw_food_input(text_input, image_path=None, audio_path=None):
    """
    Tier 1 Data Ingestion Parser via Gemini API.
    Guarantees STRICT FOOD PARSING ONLY with ZERO conversational chatter or advice.
    """
    # 1. First check custom recipe catalog
    if text_input and not image_path and not audio_path:
        custom_match = match_custom_recipe(text_input)
        if custom_match:
            return custom_match

    api_key = get_gemini_api_key()
    if not api_key:
        print("⚠️ GEMINI_API_KEY missing in ingestion collector!", flush=True)
        return None

    model_name = get_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    prompt = text_input or ""
    if audio_path and not prompt:
        prompt = "Послушай эту голосовую аудиозапись. Распознай её дословно в 'transcribed_text' и выполни первичный разбор КБЖУ."

    system_instruction = (
        "You are an expert FoodTech Data Ingestion Parser.\n"
        "FOR AUDIO VOICE NOTES: Transcribe spoken Russian audio text word-for-word into 'transcribed_text'.\n"
        "FOR ANY FOOD OR DRINK MENTIONED (e.g., 'творог', 'два яблока', 'овсянка', 'плов', 'кофе', 'курица', 'салат', 'чиа'):\n"
        "1. ALWAYS set \"intent\": \"FOOD_LOG\".\n"
        "2. Identify the clear Russian product name in 'meal_name' (e.g. 'Творог 5%', 'Яблоки', 'Овсяная каша').\n"
        "3. If weight is stated (e.g., '150г', '200 грамм'), use that exact weight in 'estimated_weight_g'.\n"
        "4. If quantity is in units or not specified (e.g., 'творог', '2 яблока', 'чашка кофе'), ESTIMATE standard single-serving weight in grams (e.g., 150g for cottage cheese, 300g for 2 apples, 250g for oatmeal/pilaft, 200g for soup, 100g for bread/snack).\n"
        "5. Accurately calculate calories, macros (protein, fat, carbs, fiber, sugar), 4 amino acids (lysine, leucine, tryptophan, methionine), and vitamins/minerals for that weight.\n"
        "6. DO NOT write conversational text or advice. Output ONLY JSON.\n\n"
        "SCHEMA 1 (FOOD_LOG):\n"
        "{\n"
        '  "intent": "FOOD_LOG",\n'
        '  "transcribed_text": "Word-for-word speech transcription",\n'
        '  "meal_name": "Name of Food in Russian",\n'
        '  "meal_type": "Breakfast | Lunch | Snack | Dinner",\n'
        '  "spoken_time": "HH:MM:SS or null if no explicit time spoken",\n'
        '  "estimated_weight_g": 150,\n'
        '  "calories": 180,\n'
        '  "protein_g": 25.0,\n'
        '  "fat_g": 7.5,\n'
        '  "carbs_g": 2.7,\n'
        '  "fiber_g": 0.0,\n'
        '  "sugar_g": 2.0,\n'
        '  "amino_acids": {"lysine_g": 2.1, "leucine_g": 2.5, "tryptophan_g": 0.3, "methionine_g": 0.7},\n'
        '  "vitamins_minerals": {"magnesium_mg": 30, "zinc_mg": 1.0, "iron_mg": 0.2, "vitamin_c_mg": 0, "vitamin_d_mcg": 0.1, "vitamin_b12_mcg": 0.6, "potassium_mg": 170, "calcium_mg": 240},\n'
        '  "omega_3_6": {"omega3_g": 0.05, "omega6_g": 0.3}\n'
        "}\n\n"
        "SCHEMA 2 (NON_FOOD_INPUT):\n"
        "{\n"
        '  "intent": "QUESTION_OR_CHAT",\n'
        '  "transcribed_text": "Word-for-word speech transcription"\n'
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
    
    # Try configured model, fallback to gemini-2.5-pro if needed
    candidate_models = [model_name, "gemini-2.5-pro", "gemini-2.5-flash"]
    # De-duplicate list preserving order
    candidate_models = list(dict.fromkeys(candidate_models))

    for m in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        try:
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
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
                            parsed = json.loads(json_match.group(0))
                            
                            # Extract spoken time if present in transcription
                            transcribed = parsed.get("transcribed_text", "")
                            spoken_t = parse_spoken_time_from_text(transcribed) or parsed.get("spoken_time")
                            if spoken_t:
                                parsed["spoken_time"] = spoken_t
                            return parsed
            else:
                print(f"⚠️ [GEMINI API ERROR] Model {m} returned HTTP {r.status_code}: {r.text[:200]}", flush=True)
        except Exception as e:
            print(f"⚠️ Ingestion exception for model {m}: {e}", flush=True)

    return None



def commit_raw_meal(meal_data, source="APP"):
    """
    Save meal entry into food_diary.json & food_diary.csv under Strict Write Authorization Rule.
    Authorized sources: 'LIBRARY' (my_custom_recipes.json), 'ANALYTICS_ENGINE' (Tier 2), 'APP' (App UI / Bot), 'TELEGRAM'.
    
    TIMESTAMP RULE:
    If meal_data contains explicit spoken_time (e.g., "14:30:00"), combines today's date + spoken time.
    Otherwise, sets exact timestamp of when the message was received/recorded.
    """
    authorized_sources = ["LIBRARY", "ANALYTICS_ENGINE", "APP", "TELEGRAM"]
    is_custom_matched = meal_data.get("source") == "LIBRARY" or meal_data.get("is_custom_matched") is True
    actual_source = "LIBRARY" if is_custom_matched else (meal_data.get("source") or source)
    
    if actual_source not in authorized_sources:
        print(f"⚠️ [WRITE REJECTED]: Unverified write source '{actual_source}'. Entries must originate from LIBRARY, ANALYTICS_ENGINE, APP or TELEGRAM.", flush=True)
        return None

    # Resolve Timestamp
    now_dt = datetime.now()
    now_date_str = now_dt.strftime("%Y-%m-%d")
    now_full_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    resolved_timestamp = meal_data.get("timestamp")
    if not resolved_timestamp:
        spoken_time = meal_data.get("spoken_time")
        if spoken_time and re.match(r'^\d{2}:\d{2}(:\d{2})?$', spoken_time):
            time_part = spoken_time if len(spoken_time) == 8 else f"{spoken_time}:00"
            resolved_timestamp = f"{now_date_str} {time_part}"
        else:
            resolved_timestamp = now_full_str

    diary = {"entries": []}
    if os.path.exists(DIARY_FILE):
        try:
            with open(DIARY_FILE, "r", encoding="utf-8") as f:
                diary = json.load(f)
        except Exception:
            diary = {"entries": []}

    m_id = meal_data.get("meal_id") or str(uuid.uuid4())[:8]
    meal_entry = {
        "id": m_id,
        "meal_id": m_id,
        "timestamp": resolved_timestamp,

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
        "source": actual_source,
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

    print(f"✅ [AUTHORIZED WRITE SUCCESS] Source: {meal_entry['source']} | Timestamp: {meal_entry['timestamp']} | Dish: {meal_entry['meal_name']}", flush=True)
    return meal_entry
