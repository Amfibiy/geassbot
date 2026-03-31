import time
from telebot import types
from database.mongo import add_user_by_username
from utils.helpers import is_admin

def register_commands(bot, active_collections, test_collection):

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        """Приветствие и вывод ID пользователя (только в ЛС)"""
        if message.chat.type != 'private':
            return 

        text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"Ваш ID: <code>{message.from_user.id}</code>\n\n"
            "Если нужна справка по командам — введите /help"
        )
        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=['help'])
    def cmd_help(message):
        """Справка по доступным командам (только в ЛС)"""
        if message.chat.type != 'private':
            return

        text = (
            "📖 **Справка GeassBot:**\n\n"
            "• `/list` — История сборов (в ЛС)\n"
            "• `/clean` — Очистка истории (в ЛС)\n"
            "• `/add @username` — Добавить участника в базу\n"
            "• `/collect` — Начать сбор (в группе)\n"
            "• `/stop` — Остановить сбор (в группе)"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['add'])
    def handle_manual_add(message):
        """Ручное добавление пользователя в базу данных или текущий сбор"""
        # Проверка прав (в группе — только админ, в ЛС — любой админ групп)
        if message.chat.type != 'private':
            if not is_admin(message.chat.id, message.from_user.id, bot):
                return
        
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "📂 **Формат:** `/add @username`", parse_mode="Markdown")
            return

        username = args[1].replace("@", "")
        
        # 1. Сохраняем в общую базу участников
        add_user_by_username(message.chat.id, username)

        # 2. Если сейчас идет активный сбор в этой группе, добавляем его и туда
        storage = active_collections.get(message.chat.id) or test_collection.get(message.chat.id)
        if storage:
            # Проверяем, нет ли его уже в списке
            if not any(p['username'] == username for p in storage['participants']):
                storage['participants'].append({
                    'id': f"manual_{username}", 
                    'name': username, 
                    'username': username, 
                    'join_time': time.time()
                })
                # Импортируем функцию обновления счетчика здесь, чтобы избежать кругового импорта
                from handlers.collection_functions import update_collection_counter
                update_collection_counter(message.chat.id, storage, bot, time.time())
                bot.reply_to(message, f"✅ @{username} добавлен в текущий сбор и базу.", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"ℹ️ @{username} уже есть в списке сбора.")
        else:
            bot.reply_to(message, f"✅ @{username} добавлен в базу данных группы.", parse_mode="Markdown")