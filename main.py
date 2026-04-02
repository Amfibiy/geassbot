#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telebot
import threading
import time
import sys
import os
from flask import Flask

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем настройки
from config.settings import BOT_TOKEN, COLLECTION_DURATION
from database.mongo import get_known_groups
from handlers import register_all_handlers

# --- СЕКЦИЯ FLASK (Для Render Web Service) ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running..."

def run_flask():
    # Render автоматически передает переменную PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
print("🚀 Запуск бота через Web Service (Flask + Polling)...")

bot = telebot.TeleBot(BOT_TOKEN)

active_collections = {}
test_collection = {}
user_sessions = {}
known_groups = {g['chat_id'] for g in get_known_groups()}

register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

def update_counters():
    while True:
        time.sleep(30)

# --- ЗАПУСК ПОТОКОВ ---
if __name__ == "__main__":
    # 1. Запускаем Flask в отдельном потоке, чтобы Render видел открытый порт
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 2. Очищаем вебхук (обязательно для перехода на polling внутри веб-сервиса)
    bot.remove_webhook()
    
    # 3. Фоновый счетчик
    counter_thread = threading.Thread(target=update_counters)
    counter_thread.daemon = True
    counter_thread.start()

    print("✅ Все системы запущены. Ожидание сообщений...")
    
    # 4. Запуск бота (в основном потоке)
    try:
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        time.sleep(5)