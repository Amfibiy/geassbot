#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telebot
import threading
import time
import sys
import os
from flask import Flask, request
import json

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем настройки
from config.settings import BOT_TOKEN, COLLECTION_DURATION, DATA_DIR
from database.history import load_history, save_history
from database.groups import load_known_groups, save_known_groups, remove_inaccessible_groups
from handlers import register_all_handlers
from utils.helpers import is_admin

# Инициализация бота
print("🚀 Запуск бота для сбора участников...")
print(f"📁 Папка данных: {DATA_DIR}")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Глобальные переменные
active_collections = {}
test_collection = {}
collection_history = load_history()
user_sessions = {}
known_groups = load_known_groups()

# Устанавливаем глобальные переменные для utils.helpers
import utils.helpers
utils.helpers.known_groups = known_groups
utils.helpers.collection_history = collection_history
utils.helpers.bot = bot

print(f"📋 Загружено {len(known_groups)} известных групп")

def check_all_groups_at_startup():
    """Проверяет группы при запуске"""
    print("🔍 Проверка групп при запуске...")
    try:
        # Важно: для webhook нельзя использовать get_updates
        # Поэтому пропускаем эту проверку при webhook
        print("⚠️ Webhook режим — пропускаем проверку групп")
        return
    except Exception as e:
        print(f"❌ Ошибка при проверке групп: {e}")

def remove_inaccessible():
    """Удаляет недоступные группы"""
    global known_groups
    known_groups, deleted = remove_inaccessible_groups(known_groups, bot)
    if deleted > 0:
        save_known_groups(known_groups)
        print(f"🗑️ Удалено {deleted} недоступных групп")

# Запускаем проверки (только если не webhook)
remove_inaccessible()
# check_all_groups_at_startup() - пропускаем для webhook

# Регистрируем все обработчики
register_all_handlers(bot, active_collections, test_collection, 
                     collection_history, known_groups, user_sessions)

def update_counters():
    """Фоновое обновление счётчиков"""
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

# Запускаем фоновые потоки
counter_thread = threading.Thread(target=update_counters)
counter_thread.daemon = True
counter_thread.start()

print("✅ Бот запущен. При старте сбора отправляет 5 сообщений.")

# ========== WEBHOOK ОБРАБОТЧИК ==========
@app.route('/webhook', methods=['POST'])
def webhook():
    """Принимает обновления от Telegram"""
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        print(f"❌ Ошибка в webhook: {e}")
        return 'Error', 500

@app.route('/')
def index():
    """Проверка работоспособности"""
    return 'Bot is running!', 200

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    try:
        # Удаляем старый webhook
        bot.remove_webhook()
        # Устанавливаем новый webhook
        webhook_url = 'https://geassbot.onrender.com/webhook'
        bot.set_webhook(url=webhook_url, allowed_updates=['message', 'callback_query'])
        print(f"✅ Webhook установлен на {webhook_url}")
        
        # Получаем порт из переменной окружения Render
        port = int(os.environ.get('PORT', 10000))
        
        # Запускаем Flask
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        time.sleep(5)