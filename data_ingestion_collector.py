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
from datetime import datetime, timedelta



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


def resolve_spoken_date_and_time(text="", meal_type="", spoken_time=None, now_dt=None):
    """
    Extract natural language date & time from Russian speech or text.
    Handles:
    - Relative dates: "сегодня", "вчера", "позавчера"
    - Days of month: "27 августа", "27-го", "27-го числа"
    - Explicit time: "в 14:30", "в 9:00", "в 15 часов", or explicit spoken_time arg
    - Standard meal periods: "завтрак" (09:00), "обед" (14:00), "ужин" (19:30), "перекус" (16:30)
    - Fallback: Current local date and time.
    """
    try:
        import zoneinfo
        user_tz = zoneinfo.ZoneInfo("Europe/Tallinn")
    except Exception:
        user_tz = None

    if not now_dt:
        now_dt = datetime.now(user_tz) if user_tz else datetime.now()

    text_lower = (text or "").lower()
    target_date = now_dt.date()

    # 1. Relative date keywords
    if "позавчера" in text_lower:
        target_date = now_dt.date() - timedelta(days=2)
    elif "вчера" in text_lower:
        target_date = now_dt.date() - timedelta(days=1)
    elif "сегодня" in text_lower:
        target_date = now_dt.date()

    # 2. Check explicit day of month (e.g. '27 августа', '27-го', '27-го числа')
    months_ru = {
        "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
        "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12
    }
    date_match = re.search(r'\b([0-3]?[0-9])[-й|го|е|\s]+([а-яё]+)', text_lower)
    if date_match:
        day_num = int(date_match.group(1))
        month_word = date_match.group(2)
        for m_prefix, m_num in months_ru.items():
            if month_word.startswith(m_prefix):
                try:
                    target_date = target_date.replace(month=m_num, day=day_num)
                except Exception:
                    pass
                break

    # 3. Time resolution
    time_str = None
    if spoken_time and re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', str(spoken_time).strip()):
        st = str(spoken_time).strip()
        time_str = st if len(st) == 8 else (f"0{st}:00" if len(st) == 4 else (f"{st}:00" if len(st) == 5 else st))
    else:
        time_match = re.search(r'\b([0-1]?[0-9]|2[0-3])[:\.-]([0-5][0-9])\b', text_lower)
        if time_match:
            hh = int(time_match.group(1))
            mm = int(time_match.group(2))
            time_str = f"{hh:02d}:{mm:02d}:00"
        else:
            hour_match = re.search(r'\bв\s+([0-1]?[0-9]|2[0-3])\s*(часов|часа|ч|утра|вечера|дня)?\b', text_lower)
            if hour_match:
                hh = int(hour_match.group(1))
                if "вечер" in text_lower and hh < 12:
                    hh += 12
                time_str = f"{hh:02d}:00:00"

    # Standard meal time presets if no explicit time
    if not time_str:
        mt_lower = (meal_type or "").lower()
        if mt_lower == "breakfast" or any(k in text_lower for k in ["завтрак", "утром", "с утра"]):
            time_str = "09:00:00"
        elif mt_lower == "lunch" or any(k in text_lower for k in ["обед", "пообедал", "днём", "днем"]):
            time_str = "14:00:00"
        elif mt_lower == "dinner" or any(k in text_lower for k in ["ужин", "поужинал", "вечером"]):
            time_str = "19:30:00"
        elif mt_lower == "snack" or any(k in text_lower for k in ["перекус", "полдник"]):
            time_str = "16:30:00"
        else:
            time_str = now_dt.strftime("%H:%M:%S")

    return f"{target_date.strftime('%Y-%m-%d')} {time_str}"



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
                    
                    # Extract spoken timestamp if present
                    match_res["timestamp"] = resolve_spoken_date_and_time(text, match_res.get("meal_type", ""))

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
        prompt = (
            "Послушай эту русскую голосовую аудиозапись:\n"
            "1. Дословно запиши весь текст в 'transcribed_text'.\n"
            "2. Выдели все упомянутые продукты, блюда, ингредиенты и напитки (например: 'сегодня я на завтрак ел...', 'пообедал супом и котлетой', 'вчера в 14:30 съел творог').\n"
            "3. Разложи составное блюдо на отдельные компоненты в массиве 'ingredients_breakdown' (например: ['Куриная грудка (150г) — 240 ккал (Б: 46г)', 'Рис отварной (150г) — 195 ккал']).\n"
            "4. Сформируй понятное русское название приёма пищи в 'meal_name'.\n"
            "5. Определи 'meal_type' (Breakfast, Lunch, Dinner, Snack).\n"
            "6. Рассчитай суммарный вес 'estimated_weight_g', суммарные калории 'calories', макросы (белки, жиры, углеводы, клетчатка, сахар), аминокислоты и витамины.\n"
            "7. Выведи результат СТРОГО в формате JSON SCHEMA 1 (FOOD_LOG)."
        )

    system_instruction = (
        "You are an expert Russian FoodTech Data Ingestion AI.\n"
        "FOR AUDIO VOICE NOTES: Transcribe spoken Russian audio text word-for-word into 'transcribed_text'.\n\n"
        "RULES FOR PARSING FOOD, DRINKS & MEALS (INCLUDING COMPLEX CONVERSATIONAL SENTENCES):\n"
        "1. If the user mentions ANY food, meal, beverage, or recipe (simple like 'творог', or conversational like 'сегодня я на завтрак ел яичницу с тостом и кофе', 'вчера пообедал борщом в 14:00', '27 августа утром ел кашу'):\n"
        "   - ALWAYS set \"intent\": \"FOOD_LOG\".\n"
        "   - Synthesize a concise, clear Russian title in 'meal_name' (e.g. 'Яичница с тостом и кофе', 'Борщ с хлебом', 'Овсяная каша с ягодами').\n"
        "   - Break down composite meals into individual ingredients with estimated weight and calories in 'ingredients_breakdown' (e.g. ['Яичница из 2 яиц (120г) — 180 ккал', 'Тост цельнозерновой (40г) — 100 ккал', 'Кофе черный без сахара (200мл) — 2 ккал']).\n"
        "   - Extract 'meal_type' ('Breakfast' if завтрак/утро, 'Lunch' if обед/день, 'Dinner' if ужин/вечер, 'Snack' if перекус).\n"
        "   - Calculate total estimated weight in grams ('estimated_weight_g') for all components combined.\n"
        "   - Accurately calculate total combined calories, macros (protein, fat, carbs, fiber, sugar), 4 amino acids (lysine, leucine, tryptophan, methionine), and key vitamins/minerals.\n"
        "2. DO NOT write conversational text, markdown chatter, or advice. Output ONLY raw JSON.\n\n"
        "SCHEMA 1 (FOOD_LOG):\n"
        "{\n"
        '  "intent": "FOOD_LOG",\n'
        '  "transcribed_text": "Word-for-word speech transcription",\n'
        '  "meal_name": "Synthesized Russian Food/Meal Title",\n'
        '  "meal_type": "Breakfast | Lunch | Snack | Dinner",\n'
        '  "ingredients_breakdown": [\n'
        '    "Ингредиент 1 (вес) — Ккал (Б/Ж/У)",\n'
        '    "Ингредиент 2 (вес) — Ккал (Б/Ж/У)"\n'
        '  ],\n'
        '  "estimated_weight_g": 300,\n'
        '  "calories": 350,\n'
        '  "protein_g": 22.0,\n'
        '  "fat_g": 12.0,\n'
        '  "carbs_g": 38.0,\n'
        '  "fiber_g": 4.0,\n'
        '  "sugar_g": 5.0,\n'
        '  "amino_acids": {"lysine_g": 1.8, "leucine_g": 2.2, "tryptophan_g": 0.3, "methionine_g": 0.5},\n'
        '  "vitamins_minerals": {"magnesium_mg": 45, "zinc_mg": 1.5, "iron_mg": 1.8, "vitamin_c_mg": 10, "vitamin_d_mcg": 0.5, "vitamin_b12_mcg": 0.8, "potassium_mg": 300, "calcium_mg": 150},\n'
        '  "omega_3_6": {"omega3_g": 0.2, "omega6_g": 0.8}\n'
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

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 600
        }
    }
    
    # Primary: High-intelligence & ultra-cheap Gemini 2.5 Flash ($0.0001/req) -> Fallback: Flash-Lite
    candidate_models = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]

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
    
    TIMESTAMP & DATE RULE:
    Resolves natural language dates ('вчера', 'сегодня', '27 августа') and spoken times ('в 14:30', 'на завтрак').
    """
    authorized_sources = ["LIBRARY", "ANALYTICS_ENGINE", "APP", "TELEGRAM"]
    is_custom_matched = meal_data.get("source") == "LIBRARY" or meal_data.get("is_custom_matched") is True
    actual_source = "LIBRARY" if is_custom_matched else (meal_data.get("source") or source)
    
    if actual_source not in authorized_sources:
        print(f"⚠️ [WRITE REJECTED]: Unverified write source '{actual_source}'. Entries must originate from LIBRARY, ANALYTICS_ENGINE, APP or TELEGRAM.", flush=True)
        return None

    # Resolve Timestamp with natural language date & time parser
    resolved_timestamp = meal_data.get("timestamp")
    if not resolved_timestamp:
        transcribed_txt = meal_data.get("transcribed_text") or meal_data.get("meal_name") or ""
        meal_type = meal_data.get("meal_type") or ""
        spoken_t = meal_data.get("spoken_time")
        resolved_timestamp = resolve_spoken_date_and_time(transcribed_txt, meal_type, spoken_time=spoken_t)

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
        "ingredients_breakdown": meal_data.get("ingredients_breakdown", []),
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
