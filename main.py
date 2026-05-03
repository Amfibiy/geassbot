#!/usr/bin/env python
# -*- coding: utf-8 -*-
import telebot
import threading
import time
import sys
import os
from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config.settings import BOT_TOKEN
    from config.commands_setup import setup_bot_menu
    from telebot.handler_backends import BaseMiddleware 
    from telebot.types import Message, CallbackQuery 
    from database.mongo import (
        save_known_group, 
        save_user_id, 
        get_known_groups
    )
    from handlers import register_all_handlers
    from utils.scheduler import update_counters
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

bot = telebot.TeleBot(BOT_TOKEN, use_class_middlewares=True)

class RegistrationMiddleware(BaseMiddleware):
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.update_types = ['message', 'callback_query']

    def pre_process(self, message, data):
        if isinstance(message, Message):
            chat, user = message.chat, message.from_user
        elif isinstance(message, CallbackQuery):
            chat, user = message.message.chat, message.from_user
        else: return

        if chat.type in ['group', 'supergroup'] and user and not user.is_bot:
            save_known_group(chat.id, chat.title)
            
            custom_title = None
            try:
                member = self.bot.get_chat_member(chat.id, user.id)
                custom_title = getattr(member, 'custom_title', None)
            except Exception as e:
                print(f"⚠️ Не удалось получить статус для {user.id}: {e}")

            save_user_id(
                chat.id, 
                user.id, 
                user.username, 
                first_name=user.first_name, 
                custom_title=custom_title
            )

bot.setup_middleware(RegistrationMiddleware(bot))

active_collections, test_collection, user_sessions = {}, {}, {}
setup_bot_menu(bot)

try:
    all_groups_data = get_known_groups()
    known_groups = {g['chat_id'] for g in all_groups_data}
except: known_groups = set()

register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

@bot.message_reaction_handler()
def handle_reaction(reaction):
    chat_id = reaction.chat.id
    save_known_group(chat_id, reaction.chat.title or f"Group {chat_id}")
    if reaction.user and not reaction.user.is_bot:
        save_user_id(chat_id, reaction.user.id, reaction.user.username)

    
if __name__ == "__main__":
    bot.delete_webhook(drop_pending_updates=True)
    print("✅ Система запущена. Ожидание 20 сек...")
    time.sleep(20)

    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=update_counters, args=(bot, active_collections, test_collection), daemon=True).start()

    print("✅ Бот в сети. Ожидаем сообщений.")
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'])