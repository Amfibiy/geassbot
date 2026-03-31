import time
from telebot import types
from database.mongo import add_user_by_username
from utils.helpers import is_admin
# Импортируем тексты
from utils.messages import get_welcome_text, get_help_text

def register_commands(bot, active_collections, test_collection, known_groups, user_sessions):

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        """Приветствие и вывод ID пользователя (только в ЛС)"""
        if message.chat.type != 'private':
            return 

        # Вызываем функцию текста из сообщений (используем HTML)
        bot.reply_to(message, get_welcome_text(), parse_mode="HTML")

    @bot.message_handler(commands=['help'])
    def cmd_help(message):
        """Справка по доступным командам (только в ЛС)"""
        if message.chat.type != 'private':
            return

        # Вызываем функцию текста из сообщений (используем HTML)
        bot.send_message(message.chat.id, get_help_text(), parse_mode="HTML")

    @bot.message_handler(commands=['add'])
    def handle_manual_add(message):
        """Ручное добавление пользователя в базу данных или текущий сбор"""
        if message.chat.type != 'private':
            if not is_admin(message.chat.id, message.from_user.id, bot):
                return
        
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "📂 <b>Формат:</b> <code>/add @username</code>", parse_mode="HTML")
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
                # Импортируем функцию обновления счетчика здесь
                from handlers.collection_functions import update_collection_counter
                update_collection_counter(message.chat.id, storage, bot, time.time())
                bot.reply_to(message, f"✅ @{username} добавлен в текущий сбор и базу.")
            else:
                bot.reply_to(message, f"ℹ️ @{username} уже есть в списке сбора.")
        else:
            bot.reply_to(message, f"✅ @{username} добавлен в базу данных группы.")

    # ОБРАБОТЧИК ЦИФР И ID (для навигации в /list)
    @bot.message_handler(func=lambda m: m.chat.type == 'private' and m.text.replace('-', '').isdigit())
    def handle_numeric_input(message):
        groups = list(known_groups.find({"active": True}))
        if not groups: return

        val = int(message.text.strip())
        target_id = None

        if 1 <= val <= len(groups):
            target_id = groups[val-1]['chat_id']
        else:
            for g in groups:
                if g['chat_id'] == val:
                    target_id = val
                    break
        
        if target_id:
            from handlers.list_functions import handle_list_group_callback
            class FakeCall:
                def __init__(self):
                    self.message = message
                    self.data = f"list_group_{target_id}"
                    self.from_user = message.from_user
            handle_list_group_callback(FakeCall(), bot, active_collections, test_collection, known_groups, user_sessions)