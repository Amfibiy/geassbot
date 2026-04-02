#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telebot
import threading
import time
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем настройки
from config.settings import BOT_TOKEN, COLLECTION_DURATION
# Импортируем функции MongoDB
from database.mongo import get_known_groups
from handlers import register_all_handlers

# Инициализация бота
print("🚀 Запуск бота для сбора участников (MongoDB version)...")

bot = telebot.TeleBot(BOT_TOKEN)

# Глобальные переменные (состояния в памяти)
active_collections = {}
test_collection = {}
user_sessions = {}
# Подгружаем известные группы из MongoDB
known_groups = {g['chat_id'] for g in get_known_groups()}

print(f"📋 Загружено {len(known_groups)} активных групп из базы")

# Регистрируем все обработчики из папки handlers
# Передаем все необходимые зависимости
register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

def update_counters():
    """Фоновое обновление счётчиков (если логика вынесена в функции)"""
    while True:
        # Здесь можно оставить пустой цикл или добавить проверку таймаутов, 
        # если вы планируете обновлять сообщения в группах каждые 30 сек.
        time.sleep(30)

# Запускаем фоновые потоки
counter_thread = threading.Thread(target=update_counters)
counter_thread.daemon = True
counter_thread.start()

print("✅ Бот успешно запущен и готов к работе.")

# Запускаем бота
if __name__ == "__main__":
    try:
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"❌ Критическая ошибка в polling: {e}")
        time.sleep(5)