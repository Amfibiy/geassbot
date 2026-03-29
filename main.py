#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telebot
import threading
import time
import sys
import os
from flask import Flask, request
from dotenv import load_dotenv

# Загрузка окружения
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import BOT_TOKEN
from database.mongo import get_known_groups, save_known_group
from handlers import register_all_handlers

# Инициализация
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Оперативные данные в памяти
active_collections = {}
test_collection = {}
user_sessions = {}
# Синхронизируем известные группы с MongoDB при старте
known_groups = get_known_groups()

# Регистрируем обработчики (теперь без collection_history)
register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

def update_counters():
    """Фоновое обновление счётчиков в отдельном потоке"""
    while True:
        current_time = time.time()
        # Обычные сборы
        for chat_id, collect in list(active_collections.items()):
            from handlers.collection_functions import update_collection_counter
            update_collection_counter(chat_id, collect, bot, current_time)
        # Тестовые сборы
        for chat_id, collect in list(test_collection.items()):
            from handlers.collection_functions import update_test_counter
            update_test_counter(chat_id, collect, bot, current_time)
        time.sleep(30)

# Запуск фонового потока
threading.Thread(target=update_counters, daemon=True).start()

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

@app.route('/')
def index():
    return 'Bot is active on MongoDB', 200

if __name__ == "__main__":
    # Настройка Webhook для Render
    bot.remove_webhook()
    webhook_url = 'https://geassbot-1.onrender.com/webhook'
    bot.set_webhook(url=webhook_url, allowed_updates=['message', 'callback_query'])
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)