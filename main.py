import os
from flask import Flask, request
import telebot
from database.mongo import cleanup_old_history, save_user_id
from handlers import register_all_handlers

TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Хранилища в памяти
active_collections = {}
test_collection = {}
known_groups = []
user_sessions = {}

# --- MIDDLEWARES (Авто-захват имен и ников) ---

@bot.middleware_handler(update_types=['message'])
def track_user_msg(bot_instance, message):
    if message.from_user:
        save_user_id(message.chat.id, message.from_user.id, 
                     message.from_user.username, message.from_user.first_name)

@bot.message_reaction_handler()
def track_user_reac(message):
    if message.user:
        save_user_id(message.chat.id, message.user.id, 
                     message.user.username, message.user.first_name)

@bot.callback_query_handler(func=lambda call: True)
def track_user_call(call):
    save_user_id(call.message.chat.id, call.from_user.id, 
                 call.from_user.username, call.from_user.first_name)
    # После сохранения данных Middleware НЕ останавливает процесс, 
    # колбэк пойдет дальше в ваши хендлеры.

# Регистрация всех обработчиков
register_all_handlers(bot, active_collections, test_collection, known_groups, user_sessions)

@app.route('/', methods=['GET', 'HEAD'])
def index(): return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

if __name__ == "__main__":
    print(f"🧹 Автоочистка: удалено {cleanup_old_history()} записей.")
    
    bot.remove_webhook()
    bot.set_webhook(
        url="https://geassbot-1.onrender.com/webhook",
        allowed_updates=['message', 'callback_query', 'message_reaction']
    )
    
    app.run(host="0.0.0.0", port=10000)