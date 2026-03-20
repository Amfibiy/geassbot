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
from config.settings import BOT_TOKEN, COLLECTION_DURATION, DATA_DIR
from database.history import load_history, save_history
from database.groups import load_known_groups, save_known_groups, remove_inaccessible_groups
from handlers import register_all_handlers
from utils.helpers import is_admin

# Инициализация бота
print("🚀 Запуск бота для сбора участников...")
print(f"📁 Папка данных: {DATA_DIR}")

bot = telebot.TeleBot(BOT_TOKEN)

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
        # ИСПРАВЛЕНО: убрал allowed_updates=['message']
        updates = bot.get_updates(offset=0, limit=1000)
        found_groups = set()
        max_update_id = 0
        me = bot.get_me()
        
        for update in updates:
            max_update_id = max(max_update_id, update.update_id)
            if update.message and update.message.chat.type in ['group', 'supergroup']:
                chat = update.message.chat
                chat_id = chat.id
                try:
                    bot_member = bot.get_chat_member(chat_id, me.id)
                    if bot_member.status in ['administrator', 'creator']:
                        found_groups.add(chat_id)
                        print(f"✅ Бот найден в группе: {chat.title} (ID: {chat_id})")
                except:
                    pass
        
        global known_groups
        old_count = len(known_groups)
        known_groups.update(found_groups)
        
        if len(known_groups) > old_count:
            save_known_groups(known_groups)
            print(f"📋 Добавлено {len(known_groups) - old_count} новых групп")
        print(f"📋 Всего известно: {len(known_groups)} групп")
        
        from config.settings import OFFSET_FILE
        if max_update_id > 0:
            with open(OFFSET_FILE, 'w') as f:
                f.write(str(max_update_id + 1))
                
    except Exception as e:
        print(f"❌ Ошибка при проверке групп: {e}")

def remove_inaccessible():
    """Удаляет недоступные группы"""
    global known_groups
    known_groups, deleted = remove_inaccessible_groups(known_groups, bot)
    if deleted > 0:
        save_known_groups(known_groups)
        print(f"🗑️ Удалено {deleted} недоступных групп")

# Запускаем проверки
remove_inaccessible()
check_all_groups_at_startup()

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

# Запускаем бота
if __name__ == "__main__":
    try:
        # Разрешаем все типы обновлений (включая callback_query)
        bot.polling(none_stop=True, allowed_updates=None)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        time.sleep(5)