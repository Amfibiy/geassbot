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

bot = telebot.TeleBot(BOT_TOKEN)

active_collections = {}
test_collection = {}
user_sessions = {}
setup_bot_menu(bot)

try:
    register_all_handlers(bot, active_collections, test_collection, known_groups=set(), user_sessions=user_sessions)
except Exception as e:
    print(f"❌ Ошибка регистрации хэндлеров: {e}")

def update_counters():
    while True:
        try:
            now = time.time()
            for chat_id, col in list(active_collections.items()):
                elapsed = int(now - col['start_time'])
                
                if elapsed >= COLLECTION_DURATION:
                    from handlers.collection_functions import stop_collection_automatically
                    stop_collection_automatically(chat_id, bot, active_collections, is_test=False)
                else:
                    rem = COLLECTION_DURATION - elapsed
                    minutes_rem = rem // 60
                    seconds_rem = rem % 60
                    
                    new_text = (
                        f"🚨 <b>ВНИМАНИЕ!</b> 🚨\n\n"
                        f"🎯 Начинается сбор участников!\n"
                        f"⏱ Осталось времени: {minutes_rem:02d}:{seconds_rem:02d}\n\n"
                        f"👇 Присоединяйтесь по кнопке ниже"
                    )
                    
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton(f"✅ Присоединиться ({len(col['participants'])})", callback_data="join_collection"))

                    try:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=col['main_message_id'],
                            text=new_text,
                            reply_markup=markup,
                            parse_mode="HTML" # Заменено на HTML
                        )
                    except Exception as e:
                        if "message is not modified" not in str(e):
                            print(f"⚠️ Ошибка обновления счетчика: {e}")

        except Exception as e:
            print(f"❌ Ошибка в цикле счетчика: {e}")
        time.sleep(30)

if __name__ == "__main__":
    print("🚀 Запуск Geass Collector...", flush=True)
    
    try:
        all_groups = get_known_groups()
        print("--- СТАТИСТИКА БАЗЫ ДАННЫХ ---", flush=True)
        print(f"📁 Зарегистрировано групп: {len(all_groups)}", flush=True)
        for g in all_groups:
            print(f"  • {g.get('title')} [{g.get('chat_id')}]", flush=True)
        print("------------------------------", flush=True)
    except Exception as e:
        print(f"⚠️ Ошибка при загрузке базы данных: {e}")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot.remove_webhook()
    
    counter_thread = threading.Thread(target=update_counters)
    counter_thread.daemon = True
    counter_thread.start()

    print("✅ Все системы запущены. Ожидание сообщений...")
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, interval=0)
        except Exception as e:
            print(f"❌ Ошибка polling: {e}")
            time.sleep(15)