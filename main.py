#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telebot
import threading
import time
import sys
import os
from flask import Flask
from config.commands_setup import setup_bot_menu
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config.settings import BOT_TOKEN, COLLECTION_DURATION
    from database.mongo import get_known_groups
    from handlers import register_all_handlers
    
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print(f"Текущий sys.path: {sys.path}")
    sys.exit(1)

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000)) 
    app.run(host='0.0.0.0', port=port)

print("🚀 Запуск бота через Web Service (Flask + Polling)...")

bot = telebot.TeleBot(BOT_TOKEN)

active_collections = {}
test_collection = {}
user_sessions = {}
setup_bot_menu(bot)

try:
    known_groups = {g['chat_id'] for g in get_known_groups()}
except Exception as e:
    print(f"⚠️ Предупреждение: Не удалось загрузить группы из БД: {e}")
    known_groups = set()

register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

def update_counters():
    while True:
        try:
            for coll_dict in [active_collections, test_collection]:
                for chat_id in list(coll_dict.keys()):
                    col = coll_dict[chat_id]
                    elapsed = int(time.time() - col['start_time'])
                    rem = max(0, COLLECTION_DURATION - elapsed)

                    if elapsed >= COLLECTION_DURATION:
                        from handlers.collection_functions import stop_collection_automatically
                        stop_collection_automatically(chat_id, bot, coll_dict, coll_dict is test_collection)
                    else:
                        minutes_left = rem // 60
                        seconds_left = rem % 60
                        
                        if col['participants']:
                            members_text = "\n".join([f"{i+1}. {p['name']}" for i, p in enumerate(col['participants'])])
                        else:
                            members_text = "Пока никто не присоединился..."

                        new_text = f"""📊 *Счётчики:*
{members_text}

⏰ Осталось времени: {minutes_left:02d}:{seconds_left:02d}

👇 Нажмите кнопку чтобы присоединиться"""
                        
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton(f"✅ Присоединиться ({len(col['participants'])})", callback_data="join_collection"))

                        try:
                            bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=col['main_message_id'],
                                text=new_text,
                                reply_markup=markup,
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            # Игнорируем ошибку, если текст не изменился
                            if "message is not modified" not in str(e):
                                print(f"⚠️ Ошибка обновления счетчика: {e}")

        except Exception as e:
            print(f"❌ Ошибка в цикле счетчика: {e}")
        time.sleep(30)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot.remove_webhook()
    
    counter_thread = threading.Thread(target=update_counters)
    counter_thread.daemon = True
    counter_thread.start()

    print("✅ Все системы запущены. Ожидание сообщений...")
    
    # 4. Запуск бота (с бесконечным циклом перезапуска при сбоях сети)
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, interval=0)
        except Exception as e:
            print(f"❌ Ошибка Polling: {e}")
            time.sleep(5)