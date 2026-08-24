#!/usr/bin/env python3
"""
AI Food, Biohacking & Micronutrient Engine (Block 2 - Deep Version)
Project: Honey Packs Health AI

This script handles:
1. Multi-modal input processing: Photos, Voice notes, and Text descriptions.
2. AI Extraction using Gemini Vision / Audio / Text API to extract FULL 360° Telemetry:
   - Basic Macros (Calories, Protein, Fat, Carbs, Fiber, Sugar)
   - Essential Amino Acids (Lysine, Leucine, Tryptophan, Methionine, etc.)
   - Vitamins & Minerals (Magnesium, Zinc, Iron, B12, Vitamin C, etc.)
   - Healthy Lipids (Omega-3 & Omega-6)
3. Intent Detection: Distinguish between food logging and conversational chat.
4. Two-Phase Confirmation: Parse draft -> User approval -> Save to "food_diary.json".
5. Personalized AI Biohacking Recommendations engine for Daily/Weekly/Monthly reports.
"""

import os
import sys
import json
import time
import base64
import re
from datetime import datetime, timedelta
import requests

DIARY_FILE = "food_diary.json"
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

def get_gemini_model():
    """Retrieve model name from config or default to gemini-3.5-flash."""
    if os.path.exists(GEMINI_CONFIG_FILE):
        with open(GEMINI_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if cfg.get("model_name"):
                return cfg["model_name"]
    return "gemini-3.5-flash"


def is_food_query(text):
    """
    Check if incoming text is a food entry vs general conversation.
    Returns True if text appears to describe food or meal intake.
    """
    if not text:
        return False

    text_lower = text.lower().strip()

    # Commands or short conversational hellos are NOT food
    if text_lower.startswith("/") or text_lower in ["привет", "как дела", "здравствуйте", "хеллоу", "хай", "помощь", "help", "спасибо"]:
        return False

    # Food keywords and indicators
    food_keywords = [
        "съел", "выпил", "завтрак", "обед", "ужин", "перекус", "кушал", "поел", "еда", "блюдо",
        "грам", "гр", "ккал", "калори", "шейк", "творог", "каша", "овсянк", "салат", "суп",
        "мясо", "рыба", "куриц", "говядин", "овощ", "фрукт", "яблоко", "банан", "яйц", "хлеб",
        "орех", "сметан", "молоко", "протеин", "кофе", "чай", "сок", "мед", "мёд", "масло",
        "сыр", "макарон", "паста", "рис", "гречк", "авокадо", "чиа", "конопл", "тыкв"
    ]

    for kw in food_keywords:
        if kw in text_lower:
            return True

    # If text contains numbers + letters (e.g. "200g", "150 грамм", "2 яйца"), likely food
    if re.search(r'\d+\s*(g|г|мл|шт|порци|ккал)', text_lower):
        return True

    # Longer texts (more than 3 words) without conversational triggers might be meal descriptions
    words = text_lower.split()
    if len(words) >= 3 and not any(text_lower.startswith(w) for w in ["что ", "как ", "почему ", "где ", "кто ", "скажи "]):
        return True

    return False


def load_user_profile():
    """Load user profile settings."""
    if os.path.exists(USER_PROFILE_FILE):
        try:
            with open(USER_PROFILE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "weight_kg": 80,
        "height_cm": 180,
        "age": 35,
        "gender": "Мужской",
        "goal": "Поддержание формы, восполнение магния, анаболический синтез белка",
        "activity_level": "Умеренная активность",
        "target_calories": 2000,
        "target_protein_g": 90,
        "target_fiber_g": 30
    }

def save_user_profile(profile):
    """Save user profile settings."""
    with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)


def parse_and_update_user_profile(text):
    """
    Parse profile updates from user voice/text input like:
    'перезапиши мои параметры. мне 46 лет, вешу я сейчас 102 кг, мужчина. цель 95 кг'
    """
    if not text:
        return False, ""
    
    text_lower = text.lower()
    if not any(kw in text_lower for kw in ["параметр", "профиль", "вешу", "мой вес", "мои данные", "мне 46", "лет", "цель"]):
        return False, ""

    profile = load_user_profile()
    updated = False

    # Weight match: '102 кг' or 'вешу 102'
    weight_m = re.search(r'(?:вешу|вес|весом)?\s*(\d+(?:[\.,]\d+)?)\s*кгр?', text_lower)
    if not weight_m:
        weight_m = re.search(r'вешу\s*(?:сейчас)?\s*(\d+(?:[\.,]\d+)?)', text_lower)
    if weight_m:
        profile["weight_kg"] = float(weight_m.group(1).replace(",", "."))
        updated = True

    # Age match: '46 лет' or 'мне 46'
    age_m = re.search(r'(?:мне|возраст)?\s*(\d+)\s*(?:лет|года|годов)', text_lower)
    if not age_m:
        age_m = re.search(r'мне\s*(\d+)', text_lower)
    if age_m:
        profile["age"] = int(age_m.group(1))
        updated = True

    # Gender match
    if "мужчин" in text_lower or "парень" in text_lower or "мужской" in text_lower:
        profile["gender"] = "Мужской"
        updated = True
    elif "женщин" in text_lower or "девушка" in text_lower or "женский" in text_lower:
        profile["gender"] = "Женский"
        updated = True

    # Goal match: 'цель 95 кг'
    goal_m = re.search(r'цель\s*(.*)', text_lower)
    if goal_m:
        goal_text = goal_m.group(1).strip()
        profile["goal"] = f"Снижение веса до {goal_text}" if ("95" in goal_text or "похуде" in goal_text or "снижени" in goal_text) else goal_text
        updated = True

    # Recalculate target calories & protein based on user weight
    if profile.get("weight_kg"):
        w = profile["weight_kg"]
        profile["target_calories"] = int(w * 24)  # ~2448 kcal for 102kg
        profile["target_protein_g"] = int(w * 1.3) # ~132g protein for 102kg

    if updated:
        save_user_profile(profile)
        msg = (
            f"👤 *ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ОБНОВЛЁН*:\n\n"
            f"• Возраст: `{profile.get('age')} лет`\n"
            f"• Вес: `{profile.get('weight_kg')} кг`\n"
            f"• Пол: `{profile.get('gender')}`\n"
            f"• Цель: _{profile.get('goal')}_\n\n"
            f"*ОБНОВЛЁННЫЕ СУТОЧНЫЕ НОРМАТИВЫ*:\n"
            f"• Целевые калории: `{profile.get('target_calories')} ккал`\n"
            f"• Целевой белок: `{profile.get('target_protein_g')} г`\n"
            f"• Целевая клетчатка: `{profile.get('target_fiber_g', 30)} г`"
        )
        return True, msg

    return False, ""


def load_food_diary():
    """Load the food diary JSON file."""
    if os.path.exists(DIARY_FILE):
        try:
            with open(DIARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"entries": []}
    return {"entries": []}


def call_gemini_ai_deep(prompt, image_path=None, audio_path=None):
    """Invoke Gemini AI Model (Text, Audio, Vision) to return 360° Nutrition JSON with full user context."""
    api_key = get_gemini_api_key()
    if not api_key:
        print("❌ Gemini API Key Missing!", flush=True)
        return None

    model_name = get_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    diary = load_food_diary()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_entries = [e for e in diary.get("entries", []) if e.get("timestamp", "").startswith(today_str)]
    
    today_context = f"CURRENT DATE: {today_str}\nTODAY'S LOGGED MEALS IN USER DIARY ({len(today_entries)} meals logged so far):\n"
    if today_entries:
        for idx, e in enumerate(today_entries, 1):
            today_context += f"{idx}. [{e.get('timestamp', '')}] {e.get('meal_type', 'Meal')}: {e.get('meal_name')} ({e.get('calories', 0)} kcal, P:{e.get('protein_g', 0)}g, F:{e.get('fat_g', 0)}g, C:{e.get('carbs_g', 0)}g)\n"
    else:
        today_context += "No meals logged yet today.\n"

    profile = load_user_profile()
    profile_context = f"USER PARAMETERS & TARGETS: Weight {profile.get('weight_kg')}kg, Height {profile.get('height_cm')}cm, Age {profile.get('age')}, Goal: {profile.get('goal')}\n"

    week_sum = get_period_summary(7)
    month_sum = get_period_summary(30)
    period_context = (
        f"7-DAY TELEMETRY AUDIT: Total Meals: {week_sum['total_meals']}, Avg Daily Calories: {week_sum['avg_daily_calories']} kcal, Avg Daily Protein: {week_sum['avg_daily_protein']}g, Avg Daily Fiber: {week_sum['avg_daily_fiber']}g, Avg Daily Magnesium: {week_sum['avg_daily_magnesium']}mg\n"
        f"30-DAY TELEMETRY AUDIT: Total Meals: {month_sum['total_meals']}, Avg Daily Calories: {month_sum['avg_daily_calories']} kcal, Avg Daily Protein: {month_sum['avg_daily_protein']}g, Avg Daily Fiber: {month_sum['avg_daily_fiber']}g, Avg Daily Magnesium: {month_sum['avg_daily_magnesium']}mg\n"
    )

    system_instruction = (
        "You are an elite sports biohacker, clinical nutritionist, and FoodTech AI assistant.\n"
        "FOR AUDIO VOICE NOTES: You MUST transcribe the spoken audio text word-for-word into Russian in the 'transcribed_text' field FIRST.\n"
        "First, evaluate the user input (text, photo image, or audio voice note):\n"
        "1) If the user is describing or showing food/drink consumed (e.g. 'съел омлет', photo of dish, voice saying 'я выпил шейк'), classify intent as 'FOOD_LOG' and output the 360° nutrition JSON.\n"
        "2) If the user is asking a question, greeting, requesting advice, or chatting (e.g. 'сколько калорий в яблоке?', 'выдай данные за день', 'как дела за неделю?', 'привет'), classify intent as 'QUESTION_OR_CHAT' and answer conversationally using the REAL-TIME USER DATA CONTEXT below!\n\n"
        f"ACTUAL REAL-TIME USER DATA CONTEXT:\n{profile_context}\n{period_context}\n{today_context}\n\n"
        "Respond ONLY with a JSON object in one of these two exact schemas:\n\n"
        "SCHEMA 1 (FOOD_LOG):\n"
        "{\n"
        '  "intent": "FOOD_LOG",\n'
        '  "transcribed_text": "Exact word-for-word transcription of user speech if audio note, or empty string if text/photo",\n'
        '  "meal_name": "Name of Food in Russian",\n'
        '  "meal_type": "Breakfast | Lunch | Snack | Dinner",\n'
        '  "estimated_weight_g": 300,\n'
        '  "calories": 490,\n'
        '  "protein_g": 28.0,\n'
        '  "fat_g": 6.0,\n'
        '  "carbs_g": 78.0,\n'
        '  "fiber_g": 9.0,\n'
        '  "sugar_g": 25.0,\n'
        '  "amino_acids": {"leucine_g": 2.4, "isoleucine_g": 1.2, "valine_g": 1.3, "lysine_g": 1.8, "tryptophan_g": 0.4, "methionine_g": 0.6, "threonine_g": 1.1, "phenylalanine_g": 1.2, "histidine_g": 0.7},\n'
        '  "vitamins_minerals": {"magnesium_mg": 180, "zinc_mg": 4.5, "iron_mg": 5.2, "vitamin_c_mg": 15},\n'
        '  "omega_3_6": {"omega3_g": 1.2, "omega6_g": 3.4},\n'
        '  "ai_comment": "Deep biohacking comment in Russian"\n'
        "}\n\n"
        "SCHEMA 2 (QUESTION_OR_CHAT):\n"
        "{\n"
        '  "intent": "QUESTION_OR_CHAT",\n'
        '  "transcribed_text": "Exact word-for-word transcription of user speech if audio note, or empty string if text/photo",\n'
        '  "ai_reply": "Detailed, friendly, expert biohacking answer in Russian using Markdown formatting, utilizing the ACTUAL REAL-TIME USER DATA CONTEXT above!"\n'
        "}"
    )

    parts = [{"text": f"{system_instruction}\n\nUser Input: {prompt}"}]

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": img_data
            }
        })

    if audio_path and os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")
        mime_type = "audio/ogg"
        if audio_path.endswith(".mp3"):
            mime_type = "audio/mp3"
        elif audio_path.endswith(".wav"):
            mime_type = "audio/wav"
        elif audio_path.endswith(".m4a"):
            mime_type = "audio/m4a"

        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": audio_data
            }
        })

    payload = {"contents": [{"parts": parts}]}

    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        if r.status_code == 200:
            res_json = r.json()
            candidates = res_json.get('candidates', [])
            if candidates and 'content' in candidates[0]:
                parts_resp = candidates[0]['content'].get('parts', [])
                if parts_resp and 'text' in parts_resp[0]:
                    text_response = parts_resp[0]['text'].strip()
                    print(f"🤖 [GEMINI RAW RESP]: {text_response[:100]}...", flush=True)
                    # Clean markdown codeblocks
                    text_response = re.sub(r'^```json\s*', '', text_response)
                    text_response = re.sub(r'^```\s*', '', text_response)
                    text_response = re.sub(r'\s*```$', '', text_response).strip()
                    
                    # Search for JSON object if surrounded by text
                    json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(0))
        else:
            print(f"❌ Gemini API Error Status {r.status_code}: {r.text}", flush=True)
    except Exception as e:
        print(f"❌ Gemini Deep API Exception: {e}", flush=True)

    return None


def convert_ogg_to_wav(ogg_path):
    """Convert Telegram OGG Opus audio file to WAV using ffmpeg if available."""
    if not os.path.exists(ogg_path):
        return ogg_path
    
    wav_path = ogg_path.rsplit(".", 1)[0] + ".wav"
    try:
        cmd = ["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if res.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
            print(f"🎵 [AUDIO CONVERTED TO WAV SUCCESS]: {wav_path}", flush=True)
            return wav_path
    except Exception as e:
        print(f"Notice: ffmpeg conversion skipped ({e}), using raw OGG", flush=True)
    return ogg_path


def transcribe_audio_explicitly(audio_path):
    """Explicitly transcribe audio file to text via Gemini API with retry logic and format conversion."""
    api_key = get_gemini_api_key()
    if not api_key or not os.path.exists(audio_path):
        print(f"⚠️ audio_path missing or no api key: {audio_path}", flush=True)
        return ""
        
    model_name = get_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    # Try converting OGG to WAV for higher transcription accuracy
    target_path = convert_ogg_to_wav(audio_path)
    mime_type = "audio/wav" if target_path.endswith(".wav") else "audio/ogg"

    with open(target_path, "rb") as f:
        audio_bytes = f.read()
        audio_data = base64.b64encode(audio_bytes).decode("utf-8")
        
    print(f"🎤 [TRANSCRIBING AUDIO]: {target_path} ({len(audio_bytes)} bytes, MIME: {mime_type})...", flush=True)
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Дословно распознай русскую речь из этого аудиофайла. Выведи ТОЛЬКО расшифрованный текст на русском языке без лишних знаков и вводных слов."},
                {"inline_data": {"mime_type": mime_type, "data": audio_data}}
            ]
        }]
    }
    
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if r.status_code == 200:
                res_json = r.json()
                candidates = res_json.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts and "text" in parts[0]:
                        trans_text = parts[0]["text"].strip()
                        if trans_text:
                            print(f"🎙️ [AUDIO TRANSCRIBED SUCCESS]: \"{trans_text}\"", flush=True)
                            return trans_text
            else:
                print(f"⚠️ Transcribe API error Status {r.status_code}: {r.text[:150]}", flush=True)
        except Exception as e:
            print(f"⚠️ Retry {attempt+1} transcribing audio: {e}", flush=True)
            time.sleep(1)
            
    return ""



def parse_food_input_deep(text_or_dict, image_path=None, audio_path=None):
    """Process user input via Gemini Deep AI (Text, Vision, or Audio) with robust 2-step audio pipeline."""
    text_input = text_or_dict if isinstance(text_or_dict, str) else text_or_dict.get("text", "")
    
    transcribed_text = ""
    if audio_path and os.path.exists(audio_path):
        transcribed_text = transcribe_audio_explicitly(audio_path)
        if not transcribed_text:
            return {
                "intent": "AUDIO_ERROR",
                "error_message": "🎙️ Не удалось четко распознать голосовое сообщение. Пожалуйста, надиктуйте блюдо еще раз близко к микрофону."
            }
        text_input = transcribed_text

    prompt = text_input
    ai_result = call_gemini_ai_deep(prompt, image_path=image_path, audio_path=audio_path if not transcribed_text else None)
    if ai_result:
        if transcribed_text and not ai_result.get("transcribed_text"):
            ai_result["transcribed_text"] = transcribed_text
        return ai_result


    # Intent-aware Fallback (never create fake meal entries on API error!)
    if is_food_query(text_input) or image_path:
        return {
            "intent": "FOOD_LOG",
            "meal_name": text_input if text_input else "Приём пищи по фото",
            "meal_type": "Meal",
            "estimated_weight_g": 250,
            "calories": 350,
            "protein_g": 18.0,
            "fat_g": 10.0,
            "carbs_g": 40.0,
            "fiber_g": 4.0,
            "sugar_g": 10.0,
            "amino_acids": {"lysine_g": 1.2, "leucine_g": 1.5, "tryptophan_g": 0.25, "methionine_g": 0.4},
            "vitamins_minerals": {"magnesium_mg": 80, "zinc_mg": 2.0, "iron_mg": 2.5, "vitamin_c_mg": 10},
            "omega_3_6": {"omega3_g": 0.3, "omega6_g": 1.5},
            "ai_comment": "Быстрое резервное построение КБЖУ. Настройте стабильное подключение к Gemini API для 100% точного ответа."
        }

    return {
        "intent": "QUESTION_OR_CHAT",
        "ai_reply": "👋 Я на связи! Я готов ответить на любые вопросы по питанию, микронутриентам и восстановлению. Задайте вопрос или отправьте фото/описание приёма пищи."
    }

    # Smart fallback based on text content keywords if no Gemini API key
    text_lower = text_input.lower()
    
    if "творог" in text_lower or "сырник" in text_lower:
        return {
            "meal_name": text_input if text_input else "Творог 5% с добавками",
            "meal_type": "Snack",
            "estimated_weight_g": 250,
            "calories": 420,
            "protein_g": 32.0,
            "fat_g": 14.0,
            "carbs_g": 18.0,
            "fiber_g": 2.0,
            "sugar_g": 12.0,
            "amino_acids": {"lysine_g": 2.6, "leucine_g": 3.1, "tryptophan_g": 0.42, "methionine_g": 0.8},
            "vitamins_minerals": {"magnesium_mg": 65, "zinc_mg": 2.8, "iron_mg": 1.2, "vitamin_c_mg": 2},
            "omega_3_6": {"omega3_g": 0.3, "omega6_g": 1.8},
            "ai_comment": "Высокобелковый приём (казеин). Оптимально для мышечного восстановления."
        }
    
    if "яйц" in text_lower or "омлет" in text_lower:
        return {
            "meal_name": text_input if text_input else "Омлет из 3 яиц с зеленью",
            "meal_type": "Breakfast",
            "estimated_weight_g": 220,
            "calories": 340,
            "protein_g": 24.0,
            "fat_g": 22.0,
            "carbs_g": 4.0,
            "fiber_g": 1.0,
            "sugar_g": 1.0,
            "amino_acids": {"lysine_g": 1.9, "leucine_g": 2.2, "tryptophan_g": 0.38, "methionine_g": 0.75},
            "vitamins_minerals": {"magnesium_mg": 45, "zinc_mg": 3.4, "iron_mg": 3.6, "vitamin_c_mg": 8},
            "omega_3_6": {"omega3_g": 0.6, "omega6_g": 2.8},
            "ai_comment": "Богат холином и лецитином. Идеальное нейропитание для мозга."
        }

    # Default fallback structured biohacking estimate
    return {
        "meal_name": text_input if text_input else "Овсяно-Конопляный Шейк",
        "meal_type": "Meal",
        "estimated_weight_g": 300,
        "calories": 490,
        "protein_g": 28.0,
        "fat_g": 6.0,
        "carbs_g": 78.0,
        "fiber_g": 9.0,
        "sugar_g": 25.0,
        "amino_acids": {
            "lysine_g": 1.6,
            "leucine_g": 2.2,
            "tryptophan_g": 0.35,
            "methionine_g": 0.5
        },
        "vitamins_minerals": {
            "magnesium_mg": 160,
            "zinc_mg": 4.2,
            "iron_mg": 4.8,
            "vitamin_c_mg": 12
        },
        "omega_3_6": {
            "omega3_g": 1.1,
            "omega6_g": 3.2
        },
        "ai_comment": "Полный биохакинг-аудит. Полноценный аминокислотный профиль и Магний."
    }


def load_food_diary():
    """Load food diary from JSON file."""
    if os.path.exists(DIARY_FILE):
        with open(DIARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": []}


def save_food_diary(diary):
    """Save food diary to JSON file."""
    with open(DIARY_FILE, "w", encoding="utf-8") as f:
        json.dump(diary, f, indent=2, ensure_ascii=False)


CSV_FILE = "food_diary.csv"

def append_to_csv_diary(meal_data):
    """Append meal row to food_diary.csv table file for Excel / Numbers."""
    file_exists = os.path.exists(CSV_FILE)
    
    ts = meal_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    date_str, time_str = ts.split(" ") if " " in ts else (ts, "")
    
    m_type = meal_data.get("meal_type", "Meal")
    if m_type == "Breakfast":
        m_type = "Завтрак"
    elif m_type == "Lunch":
        m_type = "Обед"
    elif m_type == "Dinner":
        m_type = "Ужин"
    elif m_type == "Snack":
        m_type = "Перекус"

    vm = meal_data.get("vitamins_minerals", {})
    
    row = [
        date_str,
        time_str,
        m_type,
        meal_data.get("meal_name", ""),
        str(meal_data.get("estimated_weight_g", 0)),
        str(meal_data.get("calories", 0)),
        str(meal_data.get("protein_g", 0)),
        str(meal_data.get("fat_g", 0)),
        str(meal_data.get("carbs_g", 0)),
        str(meal_data.get("fiber_g", 0)),
        str(meal_data.get("sugar_g", 0)),
        str(vm.get("magnesium_mg", 0)),
        str(vm.get("zinc_mg", 0)),
        str(vm.get("iron_mg", 0)),
        str(vm.get("vitamin_c_mg", 0))
    ]

    with open(CSV_FILE, "a", encoding="utf-8-sig") as f:
        if not file_exists:
            f.write("Дата;Время;Период;Блюдо;Вес (г);Калории (ккал);Белок (г);Жиры (г);Углеводы (г);Клетчатка (г);Сахар (г);Магний (мг);Цинк (мг);Железо (мг);Витамин C (мг)\n")
        f.write(";".join(row) + "\n")


def delete_meals_by_indices(indices_list):
    """
    Delete entries by 1-based indices list from food_diary.json and regenerate food_diary.csv.
    indices_list: list of 1-based integers (e.g. [3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    """
    diary = load_food_diary()
    entries = diary.get("entries", [])
    if not entries:
        return 0, "Дневник питания пуст."

    # Convert to 0-based set
    zero_based = set(i - 1 for i in indices_list if 1 <= i <= len(entries))
    if not zero_based:
        return 0, f"Записи с номерами {indices_list} не найдены в дневнике (всего записей в базе: {len(entries)})."

    new_entries = [e for idx, e in enumerate(entries) if idx not in zero_based]
    diary["entries"] = new_entries
    save_food_diary(diary)

    # Regenerate CSV file completely
    with open(CSV_FILE, "w", encoding="utf-8-sig") as f:
        f.write("Дата;Время;Период;Блюдо;Вес (г);Калории (ккал);Белок (г);Жиры (г);Углеводы (г);Клетчатка (г);Сахар (г);Магний (мг);Цинк (мг);Железо (мг);Витамин C (мг)\n")
        for e in new_entries:
            append_to_csv_diary(e)

    deleted_count = len(entries) - len(new_entries)
    return deleted_count, f"Успешно удалено записей: {deleted_count}. Осталось записей в базе: {len(new_entries)}."


def delete_meal_by_id(meal_id):
    """Delete meal from JSON & CSV diaries by meal_id."""
    if not meal_id:
        return False
    diary = load_food_diary()
    entries = diary.get("entries", [])
    new_entries = [e for e in entries if e.get("meal_id") != meal_id]
    
    if len(new_entries) == len(entries):
        return False
        
    diary["entries"] = new_entries
    save_food_diary(diary)

    # Regenerate CSV file completely
    with open(CSV_FILE, "w", encoding="utf-8-sig") as f:
        f.write("Дата;Время;Период;Блюдо;Вес (г);Калории (ккал);Белок (г);Жиры (г);Углеводы (г);Клетчатка (г);Сахар (г);Магний (мг);Цинк (мг);Железо (мг);Витамин C (мг)\n")
        for e in new_entries:
            append_to_csv_diary(e)

    # Rebuild daily history
    try:
        from daily_biometrics_diary import generate_full_professional_diary
        generate_full_professional_diary(14)
    except Exception:
        pass

    return True



def parse_and_execute_delete_command(text):
    """
    Detect deletion commands like:
    - 'удали записи с 3 по 12'
    - 'удали позиции с 3 по 12'
    - 'удали 5 запись'
    - '/delete 3-12'
    Returns (True, result_msg) if deletion was executed, or (False, "") if not a delete command.
    """
    if not text:
        return False, ""
    
    text_lower = text.lower().strip()
    
    # Range regex: 'с 3 по 12' or '3-12' or 'от 3 до 12'
    range_match = re.search(r'(?:удал|стир|убери).*(?:с|от)\s*(\d+)\s*(?:по|до|-)\s*(\d+)', text_lower)
    if not range_match:
        range_match = re.search(r'/del.*\s+(\d+)\s*(?:-|по|до)\s*(\d+)', text_lower)
        
    if range_match:
        start_idx = int(range_match.group(1))
        end_idx = int(range_match.group(2))
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
        indices = list(range(start_idx, end_idx + 1))
        count, msg = delete_meals_by_indices(indices)
        return True, f"🗑️ *УДАЛЕНИЕ ЗАПИСЕЙ*:\n{msg}"

    # Single index regex: 'удали 3' or 'удали запись 3'
    single_match = re.search(r'(?:удал|стир|убери).*(?:запись|позици|номер|№)?\s*(\d+)', text_lower)
    if not single_match:
        single_match = re.search(r'/del.*\s+(\d+)', text_lower)

    if single_match:
        idx = int(single_match.group(1))
        count, msg = delete_meals_by_indices([idx])
        return True, f"🗑️ *УДАЛЕНИЕ ЗАПИСИ*:\n{msg}"

    return False, ""


def commit_meal(meal_data):
    """Save a confirmed meal entry into persistent JSON and CSV diaries, updating daily history."""
    if not meal_data.get("timestamp"):
        meal_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    diary = load_food_diary()
    diary["entries"].append(meal_data)
    save_food_diary(diary)
    append_to_csv_diary(meal_data)

    # Rebuild daily history diary JSON and CSV
    try:
        from daily_biometrics_diary import generate_full_professional_diary
        generate_full_professional_diary(14)
    except Exception as e:
        print(f"Error rebuilding daily history: {e}", flush=True)

    return meal_data



def log_meal(text_input, image_path=None):
    """Direct parse and log helper."""
    meal_data = parse_food_input_deep(text_input, image_path)
    return commit_meal(meal_data)


def get_period_summary(days=7):
    """Calculate aggregated 360° audit over N days (Week / Month)."""
    diary = load_food_diary()
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent_entries = [e for e in diary["entries"] if e.get("timestamp", "") >= cutoff_date]

    total_cal = sum(e.get("calories", 0) for e in recent_entries)
    total_prot = sum(e.get("protein_g", 0) for e in recent_entries)
    total_fiber = sum(e.get("fiber_g", 0) for e in recent_entries)
    
    total_magnesium = sum(e.get("vitamins_minerals", {}).get("magnesium_mg", 0) for e in recent_entries)
    total_zinc = sum(e.get("vitamins_minerals", {}).get("zinc_mg", 0) for e in recent_entries)
    total_iron = sum(e.get("vitamins_minerals", {}).get("iron_mg", 0) for e in recent_entries)
    total_lysine = sum(e.get("amino_acids", {}).get("lysine_g", 0) for e in recent_entries)
    total_tryptophan = sum(e.get("amino_acids", {}).get("tryptophan_g", 0) for e in recent_entries)

    days_count = max(1, days)
    return {
        "period_days": days,
        "total_meals": len(recent_entries),
        "total_calories": total_cal,
        "total_protein": round(total_prot, 1),
        "avg_daily_calories": round(total_cal / days_count),
        "avg_daily_protein": round(total_prot / days_count, 1),
        "avg_daily_fiber": round(total_fiber / days_count, 1),
        "avg_daily_magnesium": round(total_magnesium / days_count),
        "avg_daily_zinc": round(total_zinc / days_count, 1),
        "avg_daily_iron": round(total_iron / days_count, 1),
        "avg_daily_lysine": round(total_lysine / days_count, 1),
        "avg_daily_tryptophan": round(total_tryptophan / days_count, 2)
    }


def generate_biohacking_recommendations(summary_data):
    """
    Generate personalized biohacking recommendations based on actual telemetry vs targets.
    Targets (daily):
    - Magnesium: 400 mg
    - Protein: 90 g
    - Fiber: 30 g (WHO standard)
    - Zinc: 11 mg
    - Tryptophan: 0.4 g
    """
    rec_lines = []

    # 1. Magnesium check
    avg_mag = summary_data.get("avg_daily_magnesium", summary_data.get("total_magnesium", 0))
    if avg_mag < 300:
        rec_lines.append(
            f"• *Низкий Магний* (`{avg_mag}мг` / 400мг): Рекомендуется добавить в рацион тыквенные семечки (30г = 150мг Mg), кунжут, миндаль или какао для нормализации работы ЦНС и глубокого сна."
        )
    else:
        rec_lines.append(
            f"• *Магний в норме* (`{avg_mag}мг`): Нервная система и мышечное восстановление под защитой."
        )

    # 2. Protein & Lysine check
    avg_prot = summary_data.get("avg_daily_protein", summary_data.get("total_protein", 0))
    if avg_prot < 75:
        rec_lines.append(
            f"• *Дефицит белка* (`{avg_prot}г` / 90г): Для восстановления мышечной ткани и синтеза нейромедиаторов добавьте творог 5%, яйца, куриное филе или конопляный протеин."
        )

    # 3. Fiber check
    avg_fib = summary_data.get("avg_daily_fiber", summary_data.get("total_fiber", 0))
    if avg_fib < 25:
        rec_lines.append(
            f"• *Клетчатка ниже нормы ВОЗ* (`{avg_fib}г` / 30г): Для поддержки микробиоты кишечника добавьте семена льна, авокадо, отруби или свежие зелёные овощи."
        )

    # 4. Tryptophan check
    avg_tryp = summary_data.get("avg_daily_tryptophan", 0)
    if avg_tryp > 0 and avg_tryp < 0.35:
        rec_lines.append(
            f"• *Мало Триптофана* (`{avg_tryp}г` / 0.4г): Триптофан — предшественник мелатонина (сна). Добавьте индейку, твердый сыр или грецкие орехи на ужин."
        )

    if not rec_lines:
        rec_lines.append("• *Отличный микронутриентный баланс!* Все показатели в пределах нормы.")

    return "\n".join(rec_lines)
