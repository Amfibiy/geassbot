import time
from telebot import types
from database.mongo import add_user_by_username
from utils.messages import get_welcome_text, get_help_text

def register_commands(bot, active_collections, test_collection, known_groups, user_sessions):

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        if message.chat.type != 'private': return
        bot.reply_to(message, get_welcome_text(), parse_mode="HTML")

    @bot.message_handler(commands=['help'])
    def cmd_help(message):
        if message.chat.type != 'private': return
        bot.send_message(message.chat.id, get_help_text(), parse_mode="HTML")

    @bot.message_handler(commands=['add'])
    def handle_add_start(message):
        if message.chat.type != 'private':
            bot.reply_to(message, "❌ Команда только для ЛС.")
            return
        msg = bot.send_message(message.chat.id, "🆔 **Отправьте ник вида @username:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_step, bot)

    def process_add_step(message, bot):
        username = message.text.strip()
        if not username.startswith('@'):
            msg = bot.reply_to(message, "❌ Ник должен начинаться с @. Попробуйте еще раз или введите /cancel")
            if username.lower() != '/cancel':
                bot.register_next_step_handler(msg, process_add_step, bot)
            return
        
        # Здесь логика добавления в базу
        # add_user_by_username(None, username.replace('@', ''), ...)
        bot.send_message(message.chat.id, f"✅ Пользователь **{username}** успешно добавлен!")

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and m.text.isdigit())
    def handle_numeric_input(message):
        # Логика выбора группы цифрой из /list
        pass