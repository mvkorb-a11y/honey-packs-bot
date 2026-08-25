#!/usr/bin/env python3
"""
24/7 Autonomous Telegram AI Health & Biohacking Bot (Pristine Clean Rebuild)
Project: Honey Packs Biohacking Core

Features:
- Dual-Pathway Architecture: Fast Food Ingestion (Tier 1) vs Analytics Period Reports (Tier 2).
- Zero AI Commentary / Zero Conversational Chatter: Strictly itemized parameter cards with 0 advice.
- Spoken Meal Time Support: Recognizes spoken times ("в 14:30 съел творог"), defaulting to exact message recording timestamp.
- Single Instance Guarantee: Autonomous PID file locking (bot_daemon.pid).
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

BOT_VERSION = "2026-08-25-REBUILD-V6"
TELEGRAM_CONFIG_FILE = "telegram_config.json"
PENDING_MEALS_FILE = "pending_meals.json"
DIARY_FILE = "food_diary.json"
USER_PROFILE_FILE = "user_profile.json"
PID_FILE = "bot_daemon.pid"
TEMP_MEDIA_DIR = "temp_media"

# User states dictionary for conversational state tracking
user_states = {}


def get_telegram_token():
    """Retrieve Telegram Bot Token from environment or config file."""
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        return os.environ["TELEGRAM_BOT_TOKEN"]

    if os.path.exists(TELEGRAM_CONFIG_FILE):
        try:
            with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("telegram_bot_token"):
                    return cfg["telegram_bot_token"]
        except Exception:
            pass
    return "8655523437:AAFau3OUqTj453kuM_aT3wDxGwv6CGegJJM"




def send_telegram_message(token, chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Send text message to Telegram user via HTTP API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram message: {e}", flush=True)
        return False


def download_telegram_file(token, file_id, dest_filename):
    """Download audio/photo media file from Telegram servers."""
    if not os.path.exists(TEMP_MEDIA_DIR):
        os.makedirs(TEMP_MEDIA_DIR, exist_ok=True)

    dest_path = os.path.join(TEMP_MEDIA_DIR, dest_filename)
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}", timeout=10)
        if r.status_code == 200:
            file_path_on_server = r.json().get("result", {}).get("file_path")
            if file_path_on_server:
                dl_url = f"https://api.telegram.org/file/bot{token}/{file_path_on_server}"
                media_res = requests.get(dl_url, timeout=30)
                if media_res.status_code == 200:
                    with open(dest_path, "wb") as f:
                        f.write(media_res.content)
                    return dest_path
    except Exception as e:
        print(f"Error downloading Telegram media: {e}", flush=True)
    return None


def format_360_meal_draft(meal):
    """Format meal data into clean text message card (0 AI comments)."""
    vm = meal.get("vitamins_minerals", {})
    aa = meal.get("amino_acids", {})
    
    meal_type_ru = meal.get("meal_type", "Приём пищи")
    if meal_type_ru == "Breakfast": meal_type_ru = "Завтрак"
    elif meal_type_ru == "Lunch": meal_type_ru = "Обед"
    elif meal_type_ru == "Dinner": meal_type_ru = "Ужин"
    elif meal_type_ru == "Snack": meal_type_ru = "Перекус"

    ts = meal.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    msg = (
        f"✅ *ЗАПИСАНО В ДНЕВНИК ПИТАНИЯ (JSON & CSV)*\n\n"
        f"*Время*: `{ts}`\n"
        f"*Название*: *{meal['meal_name']}*\n"
        f"*Период*: `{meal_type_ru}` | Вес: `{meal.get('estimated_weight_g', 250)}г`\n"
        f"*Калории*: `{meal['calories']} ккал`\n\n"
        f"*МАКРОНУТРИЕНТЫ*:\n"
        f"• Белок: `{meal['protein_g']}г` | Жиры: `{meal['fat_g']}г` | Углеводы: `{meal['carbs_g']}г`\n"
        f"• Клетчатка: `{meal['fiber_g']}г` | Сахар: `{meal.get('sugar_g', 0)}г`\n\n"
        f"*МИКРОНУТРИЕНТЫ И АМИНОКИСЛОТЫ*:\n"
        f"• Магний: `{vm.get('magnesium_mg', 0)}мг` | Цинк: `{vm.get('zinc_mg', 0)}мг`\n"
        f"• Лизин: `{aa.get('lysine_g', 0)}г` | Триптофан: `{aa.get('tryptophan_g', 0)}г`\n"
    )
    return msg


def send_daily_stats_summary_only(token, chat_id):
    """Pathway B: Render clean itemized daily summary report from Tier 2."""
    diary = load_food_diary()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_entries = [e for e in diary.get("entries", []) if e.get("timestamp", "").startswith(today_str)]

    if not today_entries:
        send_telegram_message(token, chat_id, f"📊 *ИТОГИ ДНЯ ({today_str})*:\n\n_Дневник питания за сегодня пуст._")
        return

    total_cal = sum(e.get("calories", 0) for e in today_entries)
    total_prot = sum(e.get("protein_g", 0) for e in today_entries)
    total_fat = sum(e.get("fat_g", 0) for e in today_entries)
    total_carbs = sum(e.get("carbs_g", 0) for e in today_entries)

    lines = [f"📊 *ИТОГИ ДНЯ ({today_str})*:\n"]
    lines.append(f"*Всего приёмов пищи*: `{len(today_entries)}`")
    lines.append(f"*Суммарная калорийность*: `{total_cal} ккал`")
    lines.append(f"*Макросы*: Белки: `{round(total_prot,1)}г` | Жиры: `{round(total_fat,1)}г` | Углеводы: `{round(total_carbs,1)}г`\n")
    lines.append("*СПИСОК БЛЮД ЗА СЕГОДНЯ*:")

    for idx, e in enumerate(today_entries, 1):
        t_time = e.get("timestamp", "").split(" ")[-1] if " " in e.get("timestamp", "") else ""
        lines.append(f"{idx}. `{t_time}` *{e.get('meal_name', 'Блюдо')}* — `{e.get('calories', 0)} ккал` (Б: `{e.get('protein_g', 0)}g`)")

    send_telegram_message(token, chat_id, "\n".join(lines))


def send_period_report(token, chat_id, days):
    """Pathway B: Render 7d/30d period report from Tier 2 Analytics."""
    summary = get_period_summary(days)
    header_title = f"📊 *ОТЧЕТ ЗА {days} ДНЕЙ*"
    
    msg = (
        f"{header_title}\n\n"
        f"• Всего записей: `{summary.get('total_meals', 0)}`\n"
        f"• Суммарные калории: `{summary.get('total_calories', 0)} ккал`\n"
        f"• Среднесуточный белок: `{summary.get('avg_daily_protein', 0)}г`\n"
        f"• Среднесуточный магний: `{summary.get('avg_daily_magnesium', 0)}мг`\n"
        f"• Среднесуточный цинк: `{summary.get('avg_daily_zinc', 0)}мг`\n"
        f"• Среднесуточный лизин: `{summary.get('avg_daily_lysine', 0)}г`\n"
        f"• Среднесуточный триптофан: `{summary.get('avg_daily_tryptophan', 0)}г`\n"
    )
    send_telegram_message(token, chat_id, msg)


def process_result_and_reply(token, chat_id, res_data):
    """
    Unified 2-Pathway Telegram Message Dispatcher.
    Pathway A: Food Ingestion (Tier 1) -> 0 AI comments.
    Pathway B: Period Reports (Tier 2) -> Aggregated stats.
    Non-food Fallback: Clean notification without conversational chatter.
    """
    if not res_data:
        send_telegram_message(token, chat_id, "🎙️ Не удалось обработать сообщение. Назовите блюдо (например: 'Творог 200г').")
        return

    intent = res_data.get("intent")
    transcription = (res_data.get("transcribed_text") or "").lower()

    # Check profile update command
    is_prof_v, prof_msg_v = parse_and_update_user_profile(transcription)
    if is_prof_v:
        send_telegram_message(token, chat_id, prof_msg_v)
        return

    # Check deletion command
    is_del_v, del_msg_v = parse_and_execute_delete_command(transcription)
    if is_del_v:
        send_telegram_message(token, chat_id, del_msg_v)
        return

    # Check Monthly Report triggers
    if any(kw in transcription for kw in ["месяц", "30 дн", "отчет за месяц", "месячный отчет"]):
        send_period_report(token, chat_id, 30)
        return

    # Check Weekly Report triggers
    if any(kw in transcription for kw in ["неделя", "7 дн", "отчет за неделю", "недельный отчет"]):
        send_period_report(token, chat_id, 7)
        return

    # Check Daily Report triggers
    if any(kw in transcription for kw in ["день", "сегодня", "итоги дня", "отчет за день", "отчет", "отчёт", "статистика", "покажи дневник"]):
        send_daily_stats_summary_only(token, chat_id)
        return

    # PATHWAY A: FOOD INGESTION
    if intent == "FOOD_LOG" or "meal_name" in res_data:
        meal_id = str(uuid.uuid4())[:8]
        res_data["meal_id"] = meal_id

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
            f"*Время*: `{committed.get('timestamp')}`\n"
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

    else:
        # NON-FOOD FALLBACK: Strict Notification (0 AI Chatter)
        transcription_header = ""
        if res_data.get("transcribed_text"):
            transcription_header = f"*Распознано из голоса*: _\"{res_data['transcribed_text']}\"_\n\n"

        reply = (
            f"{transcription_header}"
            f"🎙️ *Еда не распознана*.\n\n"
            f"Назовите блюдо (например: _\"Творог 200г\"_ или _\"в 14:30 съел овсянку\"_) или запросите отчёт словами: *день*, *неделя*, *месяц*."
        )
        send_telegram_message(token, chat_id, reply)


def handle_update(token, update):
    """Process incoming Telegram update payload."""
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")

        if data.startswith("cancel_logged_meal_"):
            meal_id = data.replace("cancel_logged_meal_", "")
            try:
                from food_nutrition_engine import delete_meal_by_id
                ok = delete_meal_by_id(meal_id)
                if ok:
                    send_telegram_message(token, chat_id, f"🗑️ *Запись (ID: {meal_id}) успешно удалена из базы дневника!*")
                else:
                    send_telegram_message(token, chat_id, "⚠️ Запись уже была удалена или не найдена.")
            except Exception as e:
                send_telegram_message(token, chat_id, f"Error deleting meal: {e}")

        # Answer callback query to stop loading spinner
        try:
            requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=5)
        except Exception:
            pass
        return

    msg = update.get("message")
    if not msg:
        return

    chat_id = msg["chat"]["id"]
    text = msg.get("text")
    photo = msg.get("photo")
    voice = msg.get("voice")

    if text and text.startswith("/"):
        cmd = text.split()[0].lower()
        if cmd == "/start":
            send_telegram_message(token, chat_id, "👋 *Добро пожаловать в 360° Biohacking Bot!*\n\nОтправьте голосом или текстом ваше блюдо (например: _'Творог 200г'_ или _'в 14:30 съел овсянку'_).")
            return
        elif cmd in ["/today", "/diary", "/list"]:
            send_daily_stats_summary_only(token, chat_id)
            return

    # Process Photo
    if photo:
        file_id = photo[-1]["file_id"]
        local_img = download_telegram_file(token, file_id, f"photo_{int(time.time())}.jpg")
        res_data = parse_raw_food_input("Проанализируй фото: еда", image_path=local_img)
        process_result_and_reply(token, chat_id, res_data)
        return

    # Process Voice
    if voice:
        file_id = voice["file_id"]
        local_voice = download_telegram_file(token, file_id, f"voice_{int(time.time())}.ogg")
        res_data = parse_raw_food_input(None, audio_path=local_voice)
        process_result_and_reply(token, chat_id, res_data)
        return

    # Process Text
    if text:
        res_data = parse_raw_food_input(text)
        process_result_and_reply(token, chat_id, res_data)
        return


def ensure_single_instance():
    """Guarantee that ONLY ONE single process of telegram_bot.py is running via PID file lock."""
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

    with open(PID_FILE, "w") as f:
        f.write(str(my_pid))


def start_bot_daemon():
    """Run 24/7 Long Polling Daemon loop with PID single-instance lock."""
    ensure_single_instance()
    token = get_telegram_token()
    print("\n" + "=" * 65, flush=True)
    print(f"24/7 AUTONOMOUS TELEGRAM BIOHACKING BOT STARTED ({BOT_VERSION} | PID: {os.getpid()})", flush=True)
    print("=" * 65, flush=True)

    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    while True:
        try:
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
                print("⚠️ [409 CONFLICT DETECTED]: Waiting 3s for single-instance resolution...", flush=True)
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
