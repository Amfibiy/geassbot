from telebot import types
from database.mongo import add_user_by_username
from utils.messages import get_welcome_text, get_help_text
from utils.helpers import get_admin_groups

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
            bot.reply_to(message, "❌ Команда /add теперь работает только в личных сообщениях с ботом.")
            return
        
        admin_groups = get_admin_groups(message.from_user.id, bot)
        if not admin_groups:
            bot.reply_to(message, "📭 У вас нет доступных групп, где вы являетесь администратором.")
            return

        markup = types.InlineKeyboardMarkup()
        for g in admin_groups:
            markup.add(types.InlineKeyboardButton(text=g.get('title', f"Группа {g['chat_id']}"), callback_data=f"add_group_{g['chat_id']}"))

        bot.send_message(
            message.chat.id, 
            "➕ **Добавление участника**\nВыберите группу, в которую хотите добавить пользователя:", 
            reply_markup=markup, 
            parse_mode="Markdown"
        )
    @bot.callback_query_handler(func=lambda call: call.data.startswith('add_group_'))
    def add_group_selection(call):
        chat_id = int(call.data.replace('add_group_', ''))
        user_id = call.from_user.id
        
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]['add_chat_id'] = chat_id
        
        msg = bot.edit_message_text(
            "🆔 **Отправьте ник вида @username:**\n*(или напишите /cancel для отмены)*",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_add_step, bot, user_sessions)

    def process_add_step(message, bot, user_sessions):
        user_id = message.from_user.id
        text = message.text.strip()

        if text.lower() == '/cancel':
            bot.send_message(message.chat.id, "🛑 Добавление отменено.")
            if user_id in user_sessions and 'add_chat_id' in user_sessions[user_id]:
                del user_sessions[user_id]['add_chat_id']
            return

        if not text.startswith('@'):
            msg = bot.reply_to(message, "❌ Ник должен начинаться с @. Попробуйте еще раз или введите /cancel")
            bot.register_next_step_handler(msg, process_add_step, bot, user_sessions)
            return
        
        session = user_sessions.get(user_id, {})
        chat_id = session.get('add_chat_id')
        
        if not chat_id:
            bot.reply_to(message, "❌ Ошибка сессии: не выбрана группа. Начните заново с команды /add.")
            return
        username = text
        success = add_user_by_username(chat_id, username)
        
        if success:
            bot.reply_to(message, f"✅ Пользователь {username} успешно добавлен в базу выбранной группы!")
        else:
            bot.reply_to(message, f"❌ Ошибка базы данных при добавлении {username}.")

        if 'add_chat_id' in user_sessions[user_id]:
            del user_sessions[user_id]['add_chat_id']