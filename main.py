#!/usr/bin/env python
# -*- coding: utf-8 -*-
import telebot
import threading
import time
import sys
import os
from flask import Flask
from config.commands_setup import setup_bot_menu
from telebot.handler_backends import BaseMiddleware # НОВЫЙ ИМПОРТ
from telebot.types import Message, CallbackQuery # НОВЫЙ ИМПОРТ
from database.mongo import save_known_group, save_user_id
from utils.scheduler import update_counters

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config.settings import BOT_TOKEN
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

class RegistrationMiddleware(BaseMiddleware):
    def __init__(self):
        self.update_types = ['message', 'callback_query']

    def pre_process(self, message, data):
        if isinstance(message, Message):
            chat = message.chat
            user = message.from_user
        elif isinstance(message, CallbackQuery):
            chat = message.message.chat
            user = message.from_user
        else:
            return

        if chat.type in ['group', 'supergroup']:
            save_known_group(chat.id, chat.title)
            if user and not user.is_bot:
                save_user_id(chat.id, user.id, user.username)

    def post_process(self, message, data, exception):
        pass

bot.setup_middleware(RegistrationMiddleware())

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

@bot.message_reaction_handler()
def handle_reaction(reaction):
    chat_id = reaction.chat.id
    chat_title = reaction.chat.title or f"Group {chat_id}"
    save_known_group(chat_id, chat_title)

    if reaction.user and not reaction.user.is_bot:
        save_user_id(chat_id, reaction.user.id, reaction.user.username)
    
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot.remove_webhook()

    counter_thread = threading.Thread(
        target=update_counters, 
        args=(bot, active_collections, test_collection)
    )
    counter_thread.daemon = True
    counter_thread.start()

    print("✅ Все системы запущены. Ожидание сообщений...")
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'])