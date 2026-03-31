import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin, get_admin_groups, format_date
from database.mongo import add_user_by_username
from handlers.collection_functions import start_collection, start_test_collection, stop_collection, update_collection_counter
from database.mongo import add_user_by_username

def register_commands(bot, active_collections, test_collection):

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        # Проверка: работаем только в личке
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
        # Игнорируем команду, если она написана в группе
        if message.chat.type != 'private':
            return

        text = (
            "📖 **Справка по командам GeassBot:**\n\n"
            "📊 **История и списки**\n"
            "• `/list` — Просмотр истории сборов по периодам (сегодня, неделя и т.д.).\n"
            "• `/clean` — Мгновенная очистка вашей истории периодов.\n\n"
            "👤 **Участники**\n"
            "• `/add @username` — Ручное добавление пользователя в базу.\n\n"
            "⚙️ **Системные**\n"
            "• `/start` — Узнать свой ID и запустить бота.\n"
        )
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    @bot.message_handler(commands=['list', 'clean'])
    def cmd_select_group(message):
        if message.chat.type != 'private':
            return bot.reply_to(message, "Эта команда работает только в личке.")

        mode = "list" if "list" in message.text else "clean"
        admin_groups = get_admin_groups(message.from_user.id, bot)
        
        if not admin_groups:
            return bot.reply_to(message, "❌ Вы не являетесь админом в группах из моей базы.")

        res = f"📂 <b>Режим: {mode.upper()}</b>\nВыберите группу:\n\n"
        kb = InlineKeyboardMarkup()
        
        for i, g in enumerate(admin_groups, 1):
            gid = g['chat_id']
            title = g.get('title', f"Чат {gid}")
            res += f"{i}. <code>{gid}</code> — <b>{title}</b>\n"
            kb.add(InlineKeyboardButton(f"{i}. {title}", callback_data=f"{mode}_{gid}"))
        
        res += "\n💡 <i>Нажмите кнопку, введите порядковый номер или ID.</i>"
        bot.send_message(message.chat.id, res, reply_markup=kb, parse_mode="HTML")

    @bot.message_handler(commands=['add'])
    def cmd_add_manual(message):
        if message.chat.type == 'private':
            return bot.reply_to(message, "Эта команда работает только в группах.")
            
        if not is_admin(message.chat.id, message.from_user.id, bot): return
            
        args = message.text.split()
        if len(args) < 2:
            return bot.reply_to(message, "📝 Формат: <code>/add @nickname</code>", parse_mode="HTML")
        
        target = args[1].replace("@", "")
        add_user_by_username(message.chat.id, target)
        
        storage = active_collections.get(message.chat.id) or test_collection.get(message.chat.id)
        if storage:
            storage['participants'].append({
                'id': f"manual_{target}", 'name': target, 
                'username': target, 'join_time': time.time()
            })
            update_collection_counter(message.chat.id, storage, bot, time.time())
            bot.reply_to(message, f"✅ <b>{target}</b> добавлен в текущий сбор!", parse_mode="HTML")
        else:
            bot.reply_to(message, f"✅ <b>{target}</b> добавлен в базу данных группы.", parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and not m.text.startswith('/'))
    def handle_manual_input(message):
        text_input = message.text.strip()
        if not text_input.replace('-', '').isdigit(): return

        admin_groups = get_admin_groups(message.from_user.id, bot)
        val = int(text_input)
        target_id = None

        if 1 <= val <= len(admin_groups):
            target_id = admin_groups[val-1]['chat_id']
        else:
            for g in admin_groups:
                if g['chat_id'] == val:
                    target_id = val
                    break

        if target_id:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("📊 Статистика", callback_data=f"list_{target_id}"))
            kb.add(InlineKeyboardButton("🗑 Очистить историю", callback_data=f"clean_{target_id}"))
            bot.send_message(message.chat.id, f"📍 Группа: <code>{target_id}</code>", reply_markup=kb, parse_mode="HTML")


    # Основные функции сбора (только для групп)
    @bot.message_handler(commands=['start_collect'])
    def c_sc(m): 
        if m.chat.type != 'private':
            start_collection(m, bot, active_collections, test_collection)

    @bot.message_handler(commands=['test'])
    def c_t(m): 
        if m.chat.type != 'private':
            start_test_collection(m, bot, active_collections, test_collection)

    @bot.message_handler(commands=['stop'])
    def c_st(m): 
        if m.chat.type != 'private':
            stop_collection(m, bot, active_collections, test_collection)
    
    @bot.message_handler(commands=['add'])
    def handle_manual_add(message):
        # Формат: /add @username
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "📂 **Формат:** `/add @username`", parse_mode="Markdown")
            return
        username = args[1].replace("@", "")
        if add_user_by_username(message.chat.id, username):
            bot.reply_to(message, f"✅ Пользователь `@{username}` добавлен в базу.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Не удалось добавить (возможно, юзер уже есть).")