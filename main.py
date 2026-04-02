import os
import time
from flask import Flask, request
import telebot
from telebot import apihelper
from database.mongo import cleanup_old_history, save_user_id
from handlers import register_all_handlers
from commands_setup import setup_bot_menu

# Включаем Middleware до создания бота
apihelper.ENABLE_MIDDLEWARE = True

TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- УСТАНОВКА КОНТЕКСТНОГО МЕНЮ КОМАНД ---
try:
    setup_bot_menu(bot)
except Exception as e:
    print(f"Ошибка установки меню: {e}")

# Хранилища
active_collections = {}
test_collection = {}
known_groups = []
user_sessions = {}

# --- MIDDLEWARES ---
@bot.middleware_handler(update_types=['message'])
def track_user_msg(bot_instance, message):
    if message.from_user:
        save_user_id(message.chat.id, message.from_user.id, 
                     message.from_user.username, message.from_user.first_name)

# Регистрация логики из handlers.py
register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

@app.route('/', methods=['GET', 'HEAD'])
def index(): return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Unsupported Media Type", 415