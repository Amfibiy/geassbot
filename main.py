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
from database.mongo import save_known_group

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config.settings import BOT_TOKEN, COLLECTION_DURATION
    from database.mongo import get_known_groups
    from handlers import register_all_handlers
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
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
    all_groups = get_known_groups()
    known_groups = {g['chat_id'] for g in all_groups}
except Exception:
    known_groups = set()

try:
    register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)
except Exception as e:
    print(f"❌ Ошибка регистрации хэндлеров: {e}")

def update_counters():
    while True:
        try:
            now = time.time()
            for coll_dict, is_test in [(active_collections, False), (test_collection, True)]:
                for chat_id, col in list(coll_dict.items()):
                    elapsed = int(now - col['start_time'])
                    
                    if elapsed >= COLLECTION_DURATION:
                        from handlers.collection_functions import stop_collection_automatically
                        stop_collection_automatically(chat_id, bot, coll_dict, is_test)
                    else:
                        rem = COLLECTION_DURATION - elapsed
                        minutes_rem = rem // 60
                        seconds_rem = rem % 60
                        
                        if is_test:
                            new_text = (
                                f"🧪 <b>ТЕСТОВЫЙ СБОР</b>\n\n"
                                f"⏱ Осталось времени: {minutes_rem:02d}:{seconds_rem:02d}\n\n"
                                f"👇 Нажмите кнопку (статистика не сохранится)"
                            )
                        else:
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
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            if "message is not modified" not in str(e):
                                print(f"⚠️ Ошибка обновления счетчика: {e}")

        except Exception as e:
            print(f"❌ Ошибка в цикле счетчика: {e}")
        time.sleep(30)

@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            save_known_group(message.chat.id, message.chat.title)
            bot.send_message(message.chat.id, "Бот активирован и группа зарегистрирована! ✅")

@bot.message_reaction_handler()
def handle_reaction(reaction):
    chat_id = reaction.chat.id
    chat_title = reaction.chat.title or f"Group {chat_id}"
    save_known_group(chat_id, chat_title)

@bot.message_handler(
    func=lambda m: m.chat.type in ['group', 'supergroup'] and (m.text is None or not m.text.startswith('/')), 
    content_types=['text', 'photo', 'video', 'document', 'sticker', 'voice']
)
def silent_group_registration(message):
    save_known_group(message.chat.id, message.chat.title)
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot.remove_webhook()

    counter_thread = threading.Thread(target=update_counters)
    counter_thread.daemon = True
    counter_thread.start()

    print("✅ Все системы запущены. Ожидание сообщений...")

    bot.infinity_polling(
    timeout=10, 
    long_polling_timeout=5, 
    allowed_updates=['message', 'callback_query', 'message_reaction']
)