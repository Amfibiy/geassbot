# handlers/admin_handlers.py
from telebot import types
from database.mongo import add_user_by_username
from utils.helpers import is_admin

def register_admin_handlers(bot, known_groups):
    @bot.message_handler(commands=['add_user'])
    def handle_manual_add(message):
        if message.chat.type == "private":
            bot.reply_to(message, "❌ Эта команда работает только в группах.")
            return
        
        if not is_admin(message.chat.id, message.from_user.id):
            bot.reply_to(message, "❌ У вас нет прав для добавления пользователей.")
            return

        args = message.text.split(maxsplit=2)
        
        if len(args) < 2:
            bot.reply_to(message, "📂 **Формат:** `/add_user @username [Имя]`", parse_mode="Markdown")
            return

        username = args[1].replace("@", "")
        first_name = args[2] if len(args) > 2 else username

        if add_user_by_username(message.chat.id, username, first_name):
            bot.reply_to(message, f"✅ Пользователь `@{username}` добавлен в базу чата.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Ошибка при добавлении.")