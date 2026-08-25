#!/usr/bin/env python3
"""
24/7 Autonomous Telegram AI Health & Biohacking Bot (Clean Version with Itemized Diary & File Export)
Project: Honey Packs Health AI

Features:
- Dual-Intent AI Engine (Gemini 3.5 Flash): Automatic recognition of Food Logging vs Questions/Conversations.
- Itemized Today Diary (/today, /diary, /list): Shows complete list of all meals eaten today with periods, timestamps, calories, and macros.
- Full File Export (/file, /export, /json): Sends actual food_diary.json file directly to Telegram chat.
- Interactive Inline Buttons: [✅ Записать в дневник] and [❌ Отменить].
- Zero footer tags / clean text formatting.
"""

import os
import sys
import json
import time
import uuid
import signal
import requests
from datetime import datetime

from data_ingestion_collector import (
    parse_raw_food_input,
    commit_raw_meal
)
from food_nutrition_engine import (
    load_food_diary,
    get_period_summary,
    is_food_query,
    generate_biohacking_recommendations,
    load_user_profile,
    parse_and_execute_delete_command,
    parse_and_update_user_profile
)


TELEGRAM_CONFIG_FILE = "telegram_config.json"
PENDING_MEALS_FILE = "pending_meals.json"
DIARY_FILE = "food_diary.json"
USER_PROFILE_FILE = "user_profile.json"
PID_FILE = "bot_daemon.pid"
TEMP_MEDIA_DIR = "temp_media"

# User states dictionary for conversational state tracking
user_states = {}


def load_pending_meals():
    """Load pending meal drafts from JSON file."""
    if os.path.exists(PENDING_MEALS_FILE):
        try:
            with open(PENDING_MEALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_pending_meals(data):
    """Save pending meal drafts to JSON file."""
    with open(PENDING_MEALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_telegram_token():
    """Retrieve Telegram Bot Token from environment or config."""
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        return os.environ["TELEGRAM_BOT_TOKEN"]

    if os.path.exists(TELEGRAM_CONFIG_FILE):
        with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if cfg.get("bot_token"):
                return cfg["bot_token"]

    return None


def send_telegram_message(token, chat_id, text, reply_markup=None):
    """Send Markdown formatted text message to Telegram chat with optional reply_markup."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    else:
        payload["reply_markup"] = {"remove_keyboard": True}

    try:
        r = requests.post(url, json=payload)
        return r.json()
    except Exception as e:
        print(f"Error sending Telegram message: {e}", flush=True)
        return None


def send_telegram_document(token, chat_id, file_path, caption=None):
    """Send document file to Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption
                r = requests.post(url, data=data, files=files)
                return r.json()
        except Exception as e:
            print(f"Error sending document: {e}", flush=True)
    return None


def edit_telegram_message(token, chat_id, message_id, text, reply_markup=None):
    """Edit existing Telegram message."""
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error editing Telegram message: {e}", flush=True)


def delete_telegram_message(token, chat_id, message_id):
    """Delete Telegram message from chat completely."""
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error deleting message: {e}", flush=True)


def answer_callback_query(token, callback_query_id, text=None):
    """Acknowledge Telegram callback query to dismiss loading state."""
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error answering callback query: {e}", flush=True)


def download_telegram_file(token, file_id, dest_filename):
    """Download photo or voice note from Telegram server with strict timeouts."""
    get_file_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
    try:
        r = requests.get(get_file_url, timeout=10).json()
        if r.get("ok"):
            file_path = r["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            
            os.makedirs(TEMP_MEDIA_DIR, exist_ok=True)
            local_path = os.path.join(TEMP_MEDIA_DIR, dest_filename)
            
            res = requests.get(download_url, timeout=15)
            if res.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(res.content)
                print(f"📥 [FILE DOWNLOADED SUCCESS]: {local_path} ({len(res.content)} bytes)", flush=True)
                return local_path
            else:
                print(f"❌ Error downloading file Status {res.status_code}", flush=True)
    except Exception as e:
        print(f"❌ Error downloading Telegram media: {e}", flush=True)
    return None


def format_360_meal_draft(meal):
    """Format preview card of recognized meal prior to confirmation."""
    aa = meal.get("amino_acids", {})
    vm = meal.get("vitamins_minerals", {})
    om = meal.get("omega_3_6", {})

    header = ""
    if meal.get("transcribed_text"):
        header = f"*Распознано из голоса*: _\"{meal['transcribed_text']}\"_\n\n"

    meal_type_ru = meal.get("meal_type", "Приём пищи")
    if meal_type_ru == "Breakfast":
        meal_type_ru = "Завтрак"
    elif meal_type_ru == "Lunch":
        meal_type_ru = "Обед"
    elif meal_type_ru == "Dinner":
        meal_type_ru = "Ужин"
    elif meal_type_ru == "Snack":
        meal_type_ru = "Перекус"

    msg = (
        f"{header}"
        f"✅ *ЗАПИСАНО В ДНЕВНИК ПИТАНИЯ (JSON & CSV)*\n\n"
        f"*Название*: *{meal['meal_name']}*\n"
        f"*Период дня*: `{meal_type_ru}`\n"
        f"*Оценочный вес*: `{meal.get('estimated_weight_g', 250)}г`\n"
        f"*Калории*: `{meal['calories']} ккал`\n\n"
        f"*МАКРОНУТРИЕНТЫ*:\n"
        f"• Белок: `{meal['protein_g']}г` | Жиры: `{meal['fat_g']}г` | Углеводы: `{meal['carbs_g']}г`\n"
        f"• Клетчатка: `{meal['fiber_g']}г` | Сахар: `{meal.get('sugar_g', 0)}г`\n\n"
        f"*МИКРОНУТРИЕНТЫ И АМИНОКИСЛОТЫ*:\n"
        f"• Магний: `{vm.get('magnesium_mg', 0)}мг` | Цинк: `{vm.get('zinc_mg', 0)}мг`\n"
        f"• Лизин: `{aa.get('lysine_g', 0)}г` | Триптофан: `{aa.get('tryptophan_g', 0)}г`\n\n"
        f"*Комментарий AI*: _{meal['ai_comment']}_"
    )
    return msg



def send_meal_confirmation_card(token, chat_id, meal_data):
    """Send auto-committed meal card with single cancel/delete inline button."""
    meal_id = str(uuid.uuid4())[:8]
    meal_data["meal_id"] = meal_id
    committed = commit_meal(meal_data)
    
    aa = committed.get("amino_acids", {})
    vm = committed.get("vitamins_minerals", {})
    
    header = ""
    if committed.get("transcribed_text"):
        header = f"*Распознано из голоса*: _\"{committed['transcribed_text']}\"_\n\n"

    msg = (
        f"{header}"
        f"✅ *ЗАПИСАНО В ДНЕВНИК ПИТАНИЯ (JSON & CSV)*!\n\n"
        f"*Блюдо*: *{committed.get('meal_name', 'Приём пищи')}*\n"
        f"*Калории*: `{committed.get('calories', 0)} ккал` | Вес: `{committed.get('estimated_weight_g', 250)}г`\n\n"
        f"*МАКРОНУТРИЕНТЫ*:\n"
        f"• Белок: `{committed.get('protein_g', 0)}г` | Жиры: `{committed.get('fat_g', 0)}г` | Углеводы: `{committed.get('carbs_g', 0)}г`\n"
        f"• Клетчатка: `{committed.get('fiber_g', 0)}г` | Сахар: `{committed.get('sugar_g', 0)}г`\n\n"
        f"*МИКРОНУТРИЕНТЫ И АМИНОКИСЛОТЫ*:\n"
        f"• Магний: `{vm.get('magnesium_mg', 0)}мг` | Цинк: `{vm.get('zinc_mg', 0)}мг`\n"
        f"• Лизин: `{aa.get('lysine_g', 0)}г` | Триптофан: `{aa.get('tryptophan_g', 0)}г`\n\n"
        f"*Комментарий AI*: _{committed.get('ai_comment', '')}_\n\n"
        f"_Запись сохранена в базу food_diary.json, food_diary.csv и обновлена на Веб-Дашборде._"
    )
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🗑️ Отменить запись", "callback_data": f"cancel_logged_meal_{meal_id}"}]
        ]
    }
    send_telegram_message(token, chat_id, msg, reply_markup=reply_markup)



def handle_callback_query(token, callback_query):
    """Handle Telegram Inline Button clicks."""
    cb_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    msg_id = message.get("message_id")

    if not chat_id:
        return

    chat_id_str = str(chat_id)
    pending = load_pending_meals()
    draft_info = pending.get(chat_id_str)

    # Handle cancellation of newly logged meal
    if data.startswith("cancel_logged_meal_"):

        meal_id = data.replace("cancel_logged_meal_", "")
        from food_nutrition_engine import delete_meal_by_id
        success = delete_meal_by_id(meal_id)
        
        answer_callback_query(token, cb_id, "Запись отменена и удалена")
        cancel_msg = "🗑️ *ЗАПИСЬ ОТМЕНЕНА И УДАЛЕНА ИЗ ДНЕВНИКАПИТАНИЯ (JSON & CSV)*."
        edit_telegram_message(token, chat_id, msg_id, cancel_msg)

    # Handle legacy button clicks on old messages in chat history
    elif data.startswith("confirm_meal_") or data.startswith("cancel_meal_"):
        pending.pop(chat_id_str, None)
        save_pending_meals(pending)
        answer_callback_query(token, cb_id, "Эта кнопка устарела. Все блюда теперь записываются автоматически.")
        delete_telegram_message(token, chat_id, msg_id)


    # Handle Model Switching
    elif data.startswith("set_model_"):
        new_model = data.replace("set_model_", "")
        if os.path.exists("gemini_config.json"):
            with open("gemini_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
        else:
            cfg = {}
        cfg["model_name"] = new_model
        with open("gemini_config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        answer_callback_query(token, cb_id, f"Модель изменена на {new_model}")
        model_msg = (
            f"*ИИ-МОДЕЛЬ ИЗМЕНЕНА*\n\n"
            f"Текущая модель анализа: `{new_model}`"
        )
        edit_telegram_message(token, chat_id, msg_id, model_msg)

    # Handle Daily Check-in: All Done
    elif data == "checkin_all_done":
        answer_callback_query(token, cb_id, "Формирую суточный отчёт...")
        send_daily_summary_with_recommendations(token, chat_id)

    # Handle Daily Check-in: Add Meal
    elif data == "checkin_add_meal":
        answer_callback_query(token, cb_id)
        prompt_msg = (
            "*ОТПРАВЬТЕ БЛЮДО ДЛЯ ФИКСАЦИИ*:\n\n"
            "• Пришлите фото блюда\n"
            "• Надиктуйте голосовое сообщение\n"
            "• Или напишите текстом (например: `Гречневая каша 200г и 2 яйца`)"
        )
        send_telegram_message(token, chat_id, prompt_msg)


def send_model_selection_menu(token, chat_id):
    """Send interactive AI model selection menu."""
    current_model = "gemini-3.5-flash"
    if os.path.exists("gemini_config.json"):
        with open("gemini_config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
            current_model = cfg.get("model_name", current_model)

    text = (
        f"*ВЫБОР ИИ-МОДЕЛИ*\n\n"
        f"Текущая активная модель: `{current_model}`\n\n"
        f"Выберите модель из списка ниже:"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "Gemini 3.5 Flash (Рекомендуется)", "callback_data": "set_model_gemini-3.5-flash"}
            ],
            [
                {"text": "Gemini 2.5 Flash (Быстрая)", "callback_data": "set_model_gemini-2.5-flash"}
            ],
            [
                {"text": "Gemini 2.5 Pro (Клинический анализ)", "callback_data": "set_model_gemini-2.5-pro"}
            ]
        ]
    }
    send_telegram_message(token, chat_id, text, reply_markup=reply_markup)


def generate_histogram_bar(metric_name, value, target, unit="", color_type="green", length=8, label_width=14):
    """
    Generate vibrant colored emoji bar on the same line as the title per user specification:
    Line 1: Metric Name (padded for exact column alignment) + Colored Emoji Bar [🟩🟩🟩🟩 86% ⬜⬜] + Target quantity + Red circle 🔴 (ONLY at end if >100%)
    Line 2: Consumed quantity below the bar
    Colors:
    - green (Calories): 🟩
    - blue (Protein, Fat, Carbs): 🟦
    - orange (Fiber, Magnesium, Zinc, Iron): 🟧
    """
    pct = (value / target * 100) if target > 0 else 0
    pct_round = int(round(pct))
    
    val_fmt = f"{value:.1f}".rstrip('0').rstrip('.') if isinstance(value, float) else f"{value}"
    target_fmt = f"{target:.1f}".rstrip('0').rstrip('.') if isinstance(target, float) else f"{target}"

    if color_type == "green":
        fill_block = "🟩"
    elif color_type == "blue":
        fill_block = "🟦"
    elif color_type == "orange":
        fill_block = "🟧"
    else:
        fill_block = "🟩"

    track_block = "⬜"

    filled_count = min(length, max(0, int(round((value / target) * length)))) if target > 0 else 0
    remaining_count = max(0, length - filled_count)

    bar_inner = fill_block * filled_count + track_block * remaining_count

    # Format percentage with fixed 4-character width (e.g. " 71%", "103%") for 100% bracket alignment!
    pct_str = f"{pct_round}%".rjust(4)
    bar_str = f"[{bar_inner} {pct_str}]"

    red_circle = " 🔴" if pct_round > 100 else ""

    clean_label = metric_name.replace("*", "")
    pad_spaces = " " * max(0, label_width - len(clean_label))

    return f"`{clean_label}:{pad_spaces} {bar_str}` *{target_fmt} {unit}*{red_circle}\n└─ *{val_fmt} {unit}*"


def send_daily_stats_summary_only(token, chat_id):
    """Generate and send STATS ONLY report (NO FOOD NAMES), categorized into 4 structured blocks."""
    diary = load_food_diary()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_entries = [e for e in diary.get("entries", []) if e.get("timestamp", "").startswith(today_str)]

    profile = load_user_profile()
    target_cal = profile.get("target_calories", 2000)
    target_prot = profile.get("target_protein_g", 90)
    target_fat = 70
    target_carbs = 250
    target_fiber = profile.get("target_fiber_g", 30)
    target_mag = 400
    target_zinc = 11
    target_iron = 10

    total_cal = sum(e.get("calories", 0) for e in today_entries)
    total_prot = sum(e.get("protein_g", 0) for e in today_entries)
    total_fat = sum(e.get("fat_g", 0) for e in today_entries)
    total_carbs = sum(e.get("carbs_g", 0) for e in today_entries)
    total_fiber = sum(e.get("fiber_g", 0) for e in today_entries)
    
    total_mag = sum(e.get("vitamins_minerals", {}).get("magnesium_mg", 0) for e in today_entries)
    total_zinc = sum(e.get("vitamins_minerals", {}).get("zinc_mg", 0) for e in today_entries)
    total_iron = sum(e.get("vitamins_minerals", {}).get("iron_mg", 0) for e in today_entries)

    summary_data = {
        "total_calories": total_cal,
        "total_protein": total_prot,
        "total_fiber": total_fiber,
        "total_magnesium": total_mag,
    }

    rec_text = generate_biohacking_recommendations(summary_data)

    cal_bar = generate_histogram_bar("⚡ *КАЛОРИИ*", total_cal, target_cal, "ккал", color_type="green", length=8)
    prot_bar = generate_histogram_bar("🥩 *БЕЛОК*", total_prot, target_prot, "г", color_type="blue", length=8)
    fat_bar = generate_histogram_bar("🧈 *ЖИРЫ*", total_fat, target_fat, "г", color_type="blue", length=8)
    carbs_bar = generate_histogram_bar("🍞 *УГЛЕВОДЫ*", total_carbs, target_carbs, "г", color_type="blue", length=8)

    fiber_bar = generate_histogram_bar("🌾 *КЛЕТЧАТКА*", total_fiber, target_fiber, "г", color_type="orange", length=8)
    mag_bar = generate_histogram_bar("🧲 *МАГНИЙ*", total_mag, target_mag, "мг", color_type="orange", length=8)
    zinc_bar = generate_histogram_bar("🛡️ *ЦИНК*", total_zinc, target_zinc, "мг", color_type="orange", length=8)
    iron_bar = generate_histogram_bar("🩸 *ЖЕЛЕЗО*", total_iron, target_iron, "мг", color_type="orange", length=8)

    msg = (
        f"📊 *ИТОГИ И ПОЛОСЧАТАЯ ГИСТОГРАММА ПИТАНИЯ [{today_str}]*\n\n"
        f"🔹 *БЛОК 1: КБЖУ (Калории и Макронутриенты)*\n\n"
        f"{cal_bar}\n\n"
        f"{prot_bar}\n\n"
        f"{fat_bar}\n\n"
        f"{carbs_bar}\n\n"
        f"---\n"
        f"🔹 *БЛОК 2: КЛЕТЧАТКА И МИКРОНУТРИЕНТЫ*\n\n"
        f"{fiber_bar}\n\n"
        f"{mag_bar}\n\n"
        f"{zinc_bar}\n\n"
        f"{iron_bar}\n\n"
        f"---\n"
        f"🔹 *БЛОК 3: ИИ БИОХАКИНГ-РЕКОМЕНДАЦИИ*\n"
        f"{rec_text}"
    )
    send_telegram_message(token, chat_id, msg)


def send_itemized_meals_only(token, chat_id):
    """Generate and send ONLY the list of eaten food/meals for today."""
    diary = load_food_diary()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_entries = [e for e in diary.get("entries", []) if e.get("timestamp", "").startswith(today_str)]

    itemized_lines = []
    if today_entries:
        for idx, e in enumerate(today_entries, 1):
            ts = e.get("timestamp", "").split()[-1][:5] if " " in e.get("timestamp", "") else ""
            time_prefix = f"[{ts}] " if ts else ""
            m_type = e.get("meal_type", "Приём пищи")
            if m_type == "Breakfast":
                m_type = "Завтрак"
            elif m_type == "Lunch":
                m_type = "Обед"
            elif m_type == "Dinner":
                m_type = "Ужин"
            elif m_type == "Snack":
                m_type = "Перекус"

            itemized_lines.append(
                f"{idx}. *{m_type}* {time_prefix}— *{e['meal_name']}*\n"
                f"   `{e.get('calories', 0)} ккал` | Белок: `{e.get('protein_g', 0)}г` | Жиры: `{e.get('fat_g', 0)}г` | Углеводы: `{e.get('carbs_g', 0)}г`"
            )
        meals_text = "\n\n".join(itemized_lines)
    else:
        meals_text = "Сегодня ещё нет записанных приёмов пищи."

    msg = (
        f"🍽️ *ПЕРЕЧЕНЬ СЪЕДЕННЫХ БЛЮД ЗА СЕГОДНЯ [{today_str}]*:\n\n"
        f"{meals_text}\n\n"
        f"_Всего зафиксировано приёмов пищи: {len(today_entries)}._"
    )
    send_telegram_message(token, chat_id, msg)


def send_period_report(token, chat_id, days=7):
    """Generate and send period biohacking audit report (7 days or 30 days)."""
    title = "30-ДНЕВНЫЙ" if days == 30 else "7-ДНЕВНЫЙ"
    send_telegram_message(token, chat_id, f"Формирую {title} глубокий биохакинг-аудит...")
    summary = get_period_summary(days)
    recs = generate_biohacking_recommendations(summary)
    
    report = (
        f"*{title} ГЛУБОКИЙ БИОХАКИНГ-АУДИТ ПИТАНИЯ*:\n\n"
        f"Приёмов пищи за период: `{summary['total_meals']}`\n"
        f"Среднесуточные калории: `{summary['avg_daily_calories']} ккал`\n"
        f"Среднесуточный белок: `{summary['avg_daily_protein']}г`\n"
        f"Среднесуточная клетчатка: `{summary['avg_daily_fiber']}г` (Норма ВОЗ: 30г)\n\n"
        f"*СРЕДНЕСУТОЧНЫЕ МИКРОНУТРИЕНТЫ*:\n"
        f"• Магний: `{summary['avg_daily_magnesium']} мг` (Норма: 400мг)\n"
        f"• Цинк: `{summary['avg_daily_zinc']} мг` (Норма: 11мг)\n"
        f"• Железо: `{summary['avg_daily_iron']} мг` (Норма: 10мг)\n"
        f"• Аминокислота Лизин: `{summary['avg_daily_lysine']} г`\n\n"
        f"*БИОХАКИНГ-РЕКОМЕНДАЦИИ*:\n"
        f"{recs}"
    )
    send_telegram_message(token, chat_id, report)


SCHEDULER_STATE_FILE = "scheduler_state.json"

def load_scheduler_state():
    """Load scheduler state tracking last sent dates."""
    if os.path.exists(SCHEDULER_STATE_FILE):
        try:
            with open(SCHEDULER_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_evening_sent": "", "last_morning_sent": "", "chat_id": None}


def save_scheduler_state(state):
    """Save scheduler state tracking last sent dates."""
    with open(SCHEDULER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def send_evening_2200_report(token, chat_id):
    """Generate and send 22:00 PM Evening Summary of today's intake."""
    diary = load_food_diary()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_entries = [e for e in diary.get("entries", []) if e.get("timestamp", "").startswith(today_str)]

    total_cal = sum(e.get("calories", 0) for e in today_entries)
    total_prot = sum(e.get("protein_g", 0) for e in today_entries)
    total_fiber = sum(e.get("fiber_g", 0) for e in today_entries)
    total_mag = sum(e.get("vitamins_minerals", {}).get("magnesium_mg", 0) for e in today_entries)

    summary_data = {
        "total_calories": total_cal,
        "total_protein": total_prot,
        "total_fiber": total_fiber,
        "total_magnesium": total_mag
    }
    rec_text = generate_biohacking_recommendations(summary_data)

    itemized = []
    for idx, e in enumerate(today_entries, 1):
        itemized.append(f"{idx}. *{e.get('meal_name')}* (`{e.get('calories')} ккал`) — Белок: `{e.get('protein_g')}г`")
    meals_str = "\n".join(itemized) if itemized else "Сегодня не было зафиксировано записей."

    profile = load_user_profile()
    cal_bar = generate_histogram_bar("⚡ *КАЛОРИИ*", total_cal, profile.get("target_calories", 2000), "ккал")
    prot_bar = generate_histogram_bar("🥩 *БЕЛОК*", total_prot, profile.get("target_protein_g", 90), "г")
    fiber_bar = generate_histogram_bar("🌾 *КЛЕТЧАТКА*", total_fiber, profile.get("target_fiber_g", 30), "г")
    mag_bar = generate_histogram_bar("🧲 *МАГНИЙ*", total_mag, 400, "мг")

    msg = (
        f"🌙 *ЕЖЕДНЕВНАЯ ВЕЧЕРНЯЯ СВОДКА ПИТАНИЯ [22:00]*\n\n"
        f"*СЪЕДЕНО ЗА СЕГОДНЯ [{today_str}]*:\n"
        f"{meals_str}\n\n"
        f"---\n"
        f"📊 *ПОЛОСЧАТАЯ ГИСТОГРАММА И БАЛАНС ПИТАНИЯ*:\n\n"
        f"{cal_bar}\n\n"
        f"{prot_bar}\n\n"
        f"{fiber_bar}\n\n"
        f"{mag_bar}\n\n"
        f"---\n"
        f"*ВЕЧЕРНИЕ БИОХАКИНГ-РЕКОМЕНДАЦИИ И ВОССТАНОВЛЕНИЕ*:\n"
        f"{rec_text}"
    )
    send_telegram_message(token, chat_id, msg)


def send_morning_0800_briefing(token, chat_id):
    """Generate and send 08:00 AM Morning Briefing with 7-day weekly trend & today's recommendations."""
    summary_7d = get_period_summary(7)
    recs_7d = generate_biohacking_recommendations(summary_7d)
    profile = load_user_profile()

    msg = (
        f"🌅 *ЕЖЕДНЕВНЫЙ УТРЕННИЙ БРИФИНГ ПИТАНИЯ [08:00]*\n\n"
        f"Доброе утро! Ваш ИИ-Центр Анализа подготовил утренний сводный план.\n\n"
        f"*АНАЛИЗ ПИТАНИЯ ЗА ПОСЛЕДНЮЮ НЕДЕЛЮ (7 ДНЕЙ)*:\n"
        f"• Всего приёмов пищи за 7 дней: `{summary_7d['total_meals']}`\n"
        f"• Среднесуточные калории: `{summary_7d['avg_daily_calories']} ккал` (Цель: {profile.get('target_calories', 2000)} ккал)\n"
        f"• Среднесуточный белок: `{summary_7d['avg_daily_protein']}г` (Цель: {profile.get('target_protein_g', 90)}г)\n"
        f"• Среднесуточная клетчатка: `{summary_7d['avg_daily_fiber']}г` (Норма ВОЗ: 30г)\n"
        f"• Среднесуточный магний: `{summary_7d['avg_daily_magnesium']} мг` (Цель: 400мг)\n\n"
        f"*🎯 ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ НА СЕГОДНЯ*:\n"
        f"{recs_7d}\n\n"
        f"_Продуктивного дня! Записывайте приёмы пищи голосом, фото или текстом._"
    )
    send_telegram_message(token, chat_id, msg)


def check_and_run_scheduled_tasks(token):
    """Check time and send 22:00 evening summary & 08:00 morning briefing automatically."""
    state = load_scheduler_state()
    chat_id = state.get("chat_id")
    if not chat_id:
        return

    now = datetime.now()
    today_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    # 22:00 Evening Report Rule
    if current_time == "22:00" and state.get("last_evening_sent") != today_date:
        send_evening_2200_report(token, chat_id)
        state["last_evening_sent"] = today_date
        save_scheduler_state(state)

    # 08:00 Morning Report Rule
    if current_time == "08:00" and state.get("last_morning_sent") != today_date:
        send_morning_0800_briefing(token, chat_id)
        state["last_morning_sent"] = today_date
        save_scheduler_state(state)


def handle_update(token, update):
    """Process incoming Telegram updates."""
    # Process Callback Queries (button clicks)
    if "callback_query" in update:
        handle_callback_query(token, update["callback_query"])
        return

    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    # Update chat_id in scheduler_state
    state = load_scheduler_state()
    if state.get("chat_id") != chat_id:
        state["chat_id"] = chat_id
        save_scheduler_state(state)

    text = message.get("text", "")
    photo = message.get("photo")
    voice = message.get("voice") or message.get("audio")

    # Check if text is a profile update command
    is_prof, prof_msg = parse_and_update_user_profile(text)
    if is_prof:
        send_telegram_message(token, chat_id, prof_msg)
        return

    # Check if text is a deletion command (e.g. 'удали записи с 3 по 12')
    is_del, del_msg = parse_and_execute_delete_command(text)
    if is_del:
        send_telegram_message(token, chat_id, del_msg)
        return

    # Command Handling with Russian keyboard layout aliases (/ещвфн -> /today, /ашду -> /file)
    if text.startswith("/start") or text.startswith("/help") or text.startswith("/ытарк"):
        welcome = (
            "*Honey Packs 360° Biohacking AI*\n\n"
            "Личный Биохакер и Нейро-Ассистент.\n\n"
            "*ГОЛОСОМ, ФОТО или ТЕКСТОМ*:\n"
            "• Записывайте приёмы пищи (например: `200г творога и банан`)\n"
            "• Удаляйте приёмы пищи (например: `удали записи с 3 по 12`)\n"
            "• Задавайте любые вопросы по питанию и здоровью\n\n"
            "*Команды просмотра дневника*:\n"
            "• `/today`, `/diary`, `/list` — Вывести полный перечень приёмов пищи за сегодня\n"
            "• `/file`, `/export`, `/excel` — Скачать файлы Excel (.csv) и JSON\n"
            "• `/week` / `/month` — 7-дневный или 30-дневный биохакинг-аудит\n"
            "• `/profile` — Профиль и целевые нормативы пользователя\n"
            "• `/checkin` — Вечерняя сверка дневника\n"
        )
        send_telegram_message(token, chat_id, welcome, reply_markup={"remove_keyboard": True})
        return

    if any(text.startswith(cmd) for cmd in ["/file", "/export", "/csv", "/excel", "/table", "/json", "/ашду", "/упонщке", "/оыщн", "/срт", "/уъсуд"]):
        send_telegram_message(token, chat_id, "📊 *ЭКСПОРТ ДНЕВНИКА ПИТАНИЯ*:\nОтправляю файлы таблицы Excel (CSV) и JSON данных...")
        if os.path.exists("food_diary.csv"):
            send_telegram_document(token, chat_id, "food_diary.csv", caption="📊 Таблица дневника питания (Excel / Numbers)")
        send_telegram_document(token, chat_id, DIARY_FILE, caption="📁 Исходные данные (JSON)")
        return

    if any(text.startswith(cmd) for cmd in ["/add", "/авв"]):
        send_telegram_message(token, chat_id, "*ДОБАВИТЬ ЕДУ*: Отправьте фото, надиктуйте голос или напишите название и вес блюда.")
        return

    if any(text.startswith(cmd) for cmd in ["/model", "/ьщвуд"]):
        send_model_selection_menu(token, chat_id)
        return

    if any(text.startswith(cmd) for cmd in ["/checkin", "/сруксшт"]):
        send_daily_checkin_survey(token, chat_id)
        return

    if any(text.startswith(cmd) for cmd in ["/week", "/month", "/цуек", "/ьщген"]):
        days = 30 if any(text.startswith(cmd) for cmd in ["/month", "/ьщген"]) else 7
        send_period_report(token, chat_id, days)
        return

    if any(text.startswith(cmd) for cmd in ["/profile", "/профиль", "/params"]):
        profile = load_user_profile()
        profile_msg = (
            f"*ПРОФИЛЬ И ПАРАМЕТРЫ ПОЛЬЗОВАТЕЛЯ*:\n\n"
            f"• Рост: `{profile.get('height_cm', 180)} см`\n"
            f"• Вес: `{profile.get('weight_kg', 80)} кг`\n"
            f"• Возраст: `{profile.get('age', 35)} лет`\n"
            f"• Пол: `{profile.get('gender', 'Мужской')}`\n"
            f"• Цель: _{profile.get('goal')}_\n\n"
            f"*СУТОЧНЫЕ ЦЕЛИ*:\n"
            f"• Калории: `{profile.get('target_calories', 2000)} ккал`\n"
            f"• Белок: `{profile.get('target_protein_g', 90)}г`\n"
            f"• Клетчатка: `{profile.get('target_fiber_g', 30)}г`\n\n"
            f"_Эти данные используются Центром ИИ-Анализа Gemini для персонализированного биохакинга._"
        )
        send_telegram_message(token, chat_id, profile_msg)
        return

    if any(text.startswith(cmd) for cmd in ["/meals", "/food", "/еда", "/приемы"]):
        send_itemized_meals_only(token, chat_id)
        return

    if any(text.startswith(cmd) for cmd in ["/today", "/summary", "/stats", "/diary", "/log", "/ещвфн", "/вшфпя", "/дшыт", "/дщп"]):
        send_daily_stats_summary_only(token, chat_id)
        return

    def process_result_and_reply(res_data):
        """Route Gemini result based on classified intent (FOOD_LOG vs QUESTION_OR_CHAT)."""
        if not res_data:
            send_telegram_message(token, chat_id, "Не удалось обработать сообщение. Попробуйте еще раз.")
            return

        intent = res_data.get("intent")
        transcription = (res_data.get("transcribed_text") or "").lower()
        transcription_header = ""
        if res_data.get("transcribed_text"):
            transcription_header = f"*Распознано из голоса*: _\"{res_data['transcribed_text']}\"_\n\n"

        # Check if user spoke a profile update command
        is_prof_v, prof_msg_v = parse_and_update_user_profile(transcription)
        if is_prof_v:
            send_telegram_message(token, chat_id, prof_msg_v)
            return

        # Check if user spoke a deletion command
        is_del_v, del_msg_v = parse_and_execute_delete_command(transcription)
        if is_del_v:
            send_telegram_message(token, chat_id, del_msg_v)
            return

        # Check if user requested a Monthly Report ("месяц", "отчет за месяц", "30 дней")
        month_keywords = ["месяц", "30 дн", "тридцать дн", "за месяц", "дела за месяц", "отчет за месяц", "месячный отчет", "отчет месяц"]
        if any(kw in transcription for kw in month_keywords):
            send_period_report(token, chat_id, 30)
            return

        # Check if user requested a Weekly Report ("неделя", "отчет за неделю", "7 дней")
        week_keywords = ["неделя", "недел", "7 дн", "семь дн", "за неделю", "дела за неделю", "отчет за неделю", "недельный отчет", "отчет неделя"]
        if any(kw in transcription for kw in week_keywords):
            send_period_report(token, chat_id, 7)
            return

        # Check if user requested a Daily Report or General Report ("день", "отчет за день", "итоги дня", "отчет", "отчёт")
        day_keywords = ["день", "сегодня", "итоги дня", "отчет за день", "дневной отчет", "отчет день", "итоги", "отчет", "отчёт", "данные", "статистика", "баланс", "выдай все данные", "покажи дневник"]
        if any(kw in transcription for kw in day_keywords):
            send_daily_stats_summary_only(token, chat_id)
            return

        # Explicit request for food/meals list ONLY ("что я съел", "какую еду я ел", "покажи блюда")
        meal_list_keywords = [
            "что я съел", "какую еду", "какую еду я ел", "покажи блюда", "список блюд",
            "какие блюда", "покажи приемы", "выведи все блюда", "приемы пищи"
        ]
        if any(kw in transcription for kw in meal_list_keywords):
            send_itemized_meals_only(token, chat_id)
            return


        if intent == "AUDIO_ERROR":
            send_telegram_message(token, chat_id, res_data.get("error_message", "🎙️ Не удалось разобрать голосовую аудиозапись."))
            return

        if intent == "FOOD_LOG" or "meal_name" in res_data:
            meal_id = str(uuid.uuid4())[:8]
            res_data["meal_id"] = meal_id
            
            # AUTOMATIC IMMEDIATE COMMIT TO JSON AND CSV VIA TIER 1 DATA INGESTION
            committed = commit_raw_meal(res_data, source="APP")
            if not committed:
                return

                
            aa = committed.get("amino_acids", {})
            vm = committed.get("vitamins_minerals", {})
            source_tag = " [Источник: Библиотека]" if committed.get("source") == "LIBRARY" else ""
            
            header = ""
            if committed.get("transcribed_text"):
                header = f"*Распознано из голоса*: _\"{committed['transcribed_text']}\"_\n\n"

            msg = (
                f"{header}"
                f"✅ *ЗАПИСАНО В ДНЕВНИК ПИТАНИЯ (JSON & CSV)*{source_tag}!\n\n"
                f"*Блюдо*: *{committed.get('meal_name', 'Приём пищи')}*\n"
                f"*Калории*: `{committed.get('calories', 0)} ккал` | Вес: `{committed.get('estimated_weight_g', 250)}г`\n\n"
                f"*МАКРОНУТРИЕНТЫ*:\n"
                f"• Белок: `{committed.get('protein_g', 0)}г` | Жиры: `{committed.get('fat_g', 0)}г` | Углеводы: `{committed.get('carbs_g', 0)}г`\n"
                f"• Клетчатка: `{committed.get('fiber_g', 0)}г` | Сахар: `{committed.get('sugar_g', 0)}г`\n\n"
                f"*МИКРОНУТРИЕНТЫ И АМИНОКИСЛОТЫ*:\n"
                f"• Магний: `{vm.get('magnesium_mg', 0)}мг` | Цинк: `{vm.get('zinc_mg', 0)}мг`\n"
                f"• Лизин: `{aa.get('lysine_g', 0)}г` | Триптофан: `{aa.get('tryptophan_g', 0)}г`\n\n"
                f"_Запись сохранена в базу food_diary.json, food_diary.csv и обновлена на Веб-Дашборде._"
            )
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🗑️ Отменить запись", "callback_data": f"cancel_logged_meal_{meal_id}"}]
                ]
            }
            send_telegram_message(token, chat_id, msg, reply_markup=reply_markup)

        elif intent == "QUESTION_OR_CHAT" or "ai_reply" in res_data:
            reply = transcription_header + res_data.get("ai_reply", "Я на связи! Чем могу помочь по вашему рациону или восстановлению?")
            send_telegram_message(token, chat_id, reply)
        else:
            reply = transcription_header + res_data.get("ai_reply", "Я на связи! Отправьте описание/фото блюда или задайте любой вопрос по питанию.")
            send_telegram_message(token, chat_id, reply)


    # Photo logging
    if photo:
        file_id = photo[-1]["file_id"]
        local_img = download_telegram_file(token, file_id, f"photo_{int(time.time())}.jpg")
        res_data = parse_raw_food_input("Проанализируй фото: еда или вопрос", image_path=local_img)
        process_result_and_reply(res_data)
        return

    # Voice logging
    if voice:
        file_id = voice["file_id"]
        local_voice = download_telegram_file(token, file_id, f"voice_{int(time.time())}.ogg")
        res_data = parse_raw_food_input(
            "Внимательно послушай аудиозапись. Определи намерение (FOOD_LOG или QUESTION_OR_CHAT) и ответь согласно схеме.",
            audio_path=local_voice
        )
        process_result_and_reply(res_data)
        return

    # Text processing
    if text:
        res_data = parse_raw_food_input(text)
        process_result_and_reply(res_data)
        return




def ensure_single_instance():
    """Guarantee that ONLY ONE single process of telegram_bot.py is running. Auto-kills old duplicates."""
    my_pid = os.getpid()
    
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    old_pid = int(content)
                    if old_pid != my_pid:
                        try:
                            os.kill(old_pid, signal.SIGKILL)
                            print(f"🧹 [AUTO-CLEANUP]: Killed stale duplicate bot daemon PID {old_pid}", flush=True)
                        except (OSError, ProcessLookupError):
                            pass
        except Exception:
            pass

    # Write current PID
    with open(PID_FILE, "w") as f:
        f.write(str(my_pid))


def start_bot_daemon():
    """Run 24/7 Long Polling Daemon loop with PID single-instance lock and self-healing error recovery."""
    ensure_single_instance()
    token = get_telegram_token()
    print("\n" + "=" * 65, flush=True)
    print(f"24/7 AUTONOMOUS TELEGRAM BIOHACKING BOT STARTED (PID: {os.getpid()})", flush=True)
    print("=" * 65, flush=True)

    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    while True:
        try:
            check_and_run_scheduled_tasks(token)
            r = requests.get(f"{url}?offset={offset}&timeout=25", timeout=30)
            if r.status_code == 200:
                data = r.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    print(f"\n[UPDATE RECEIVED]: update_id={update['update_id']}", flush=True)
                    try:
                        handle_update(token, update)
                    except Exception as e:
                        print(f"Error in handle_update: {e}", flush=True)
            elif r.status_code == 409:
                print("⚠️ [409 CONFLICT DETECTED]: Auto-healing duplicate sessions... Waiting 3s.", flush=True)
                time.sleep(3)
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.RequestException as e:
            print(f"Network Exception in Long Polling: {e}", flush=True)
            time.sleep(2)
        except KeyboardInterrupt:
            print("\nBot daemon stopped.", flush=True)
            break
        except Exception as e:
            print(f"Loop Exception: {e}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    start_bot_daemon()
