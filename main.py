#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telebot
import threading
import time
import sys
import os
from flask import Flask

# 1. ИСПРАВЛЕНИЕ ПУТЕЙ (Самое важное для Render)
# Находим путь к директории, где лежит этот файл (src или корень)
current_dir = os.path.dirname(os.path.abspath(__file__))
# Вставляем путь в самое начало, чтобы модули 'handlers' и 'database' точно нашлись
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Теперь импорты пойдут без ошибок
try:
    from config.settings import BOT_TOKEN, COLLECTION_DURATION
    from database.mongo import get_known_groups
    from handlers import register_all_handlers
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    # Выводим текущие пути, чтобы понять, где Python ищет файлы в логах Render
    print(f"Текущий sys.path: {sys.path}")
    sys.exit(1)

# --- СЕКЦИЯ FLASK (Для Render Web Service) ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running perfectly!"

def run_flask():
    # 2. ИСПРАВЛЕНИЕ ПОРТА
    # Render сам передает нужный порт через переменную PORT
    port = int(os.environ.get("PORT", 10000)) 
    app.run(host='0.0.0.0', port=port)

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
print("🚀 Запуск бота через Web Service (Flask + Polling)...")

bot = telebot.TeleBot(BOT_TOKEN)

active_collections = {}
test_collection = {}
user_sessions = {}

# Пытаемся получить группы из базы (с обработкой ошибки подключения)
try:
    known_groups = {g['chat_id'] for g in get_known_groups()}
except Exception as e:
    print(f"⚠️ Предупреждение: Не удалось загрузить группы из БД: {e}")
    known_groups = set()

# Регистрируем хендлеры
register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

def update_counters():
    """Фоновое обновление счетчиков в активных сборах каждые 30 секунд"""
    while True:
        try:
            current_time = time.time()
            for chat_id, col in list(active_collections.items()):
                elapsed_sec = int(current_time - col['start_time'])
                rem_sec = max(0, COLLECTION_DURATION - elapsed_sec)
                
                if rem_sec > 0:
                    rem_mins = rem_sec // 60
                    rem_secs = rem_sec % 60
                    count = len(col['participants'])
                    
                    markup = telebot.types.InlineKeyboardMarkup()
                    markup.add(telebot.types.InlineKeyboardButton(
                        "✅ Стать первым" if count == 0 else "✅ Присоединиться", 
                        callback_data="join_collection"
                    ))
                    
                    text = (
                        "📊 **Счётчики:**\n"
                        f"👥 Участников: {count}\n"
                        f"⏰ Осталось времени: {rem_mins:02d}:{rem_secs:02d}\n\n"
                        "👇 Нажмите кнопку чтобы присоединиться"
                    )
                    
                    try:
                        bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=col['counter_message_id'],
                            text=text,
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                    except telebot.apihelper.ApiTelegramException as e:
                        if "message is not modified" not in str(e):
                            print(f"Ошибка обновления сообщения в {chat_id}: {e}")
                            
        except Exception as e:
            print(f"❌ Критическая ошибка в потоке счетчика: {e}")
            
        time.sleep(30)

# --- ЗАПУСК ПОТОКОВ ---
if __name__ == "__main__":
    # 1. Запускаем Flask для Render
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 2. Очищаем вебхук
    bot.remove_webhook()
    
    # 3. Запускаем фоновый счетчик
    counter_thread = threading.Thread(target=update_counters)
    counter_thread.daemon = True
    counter_thread.start()

    print("✅ Все системы запущены. Ожидание сообщений...")
    
    # 4. Запуск бота
    try:
        bot.polling(none_stop=True, timeout=60, interval=0)
    except Exception as e:
        print(f"❌ Ошибка Polling: {e}")
        time.sleep(5)