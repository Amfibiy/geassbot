import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin, get_admin_groups, format_date
from database.mongo import add_user_by_username, clear_all_members, cleanup_old_history
from handlers.collection_functions import start_collection, start_test_collection, stop_collection, update_collection_counter

def register_commands(bot, active_collections, test_collection):

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"Твой ID: <code>{message.from_user.id}</code>\n\n"
            "Если забыли, что я умею, или нужна справка по командам — вызовите /help"
        )
        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=['help'])
    def cmd_help(message):
        text = (
            "📖 <b>Справка по командам бота:</b>\n\n"
            "<b>Для групп:</b>\n"
            "/start_collect - Запустить стандартный сбор\n"
            "/test - Запустить тестовый сбор (без тегов)\n"
            "/stop - Остановить текущий сбор\n"
            "/add @nickname - Внести игрока в базу/сбор вручную\n\n"
            "<b>Для личных сообщений:</b>\n"
            "/list - Посмотреть историю и статистику по группам\n"
            "/clean - Выбрать группу для очистки истории\n\n"
            "<b>Управление БД (сервисные):</b>\n"
            "/db_reset_members - Полный сброс базы участников\n"
            "/db_cleanup - Удаление истории старше 90 дней"
        )
        bot.reply_to(message, text, parse_mode="HTML")

    # ГИБРИДНЫЙ ВЫБОР ДЛЯ /list И /clean В ЛИЧКЕ
    @bot.message_handler(commands=['list', 'clean'])
    def cmd_select_group(message):
        if message.chat.type != 'private':
            bot.reply_to(message, "Эта команда работает только в личных сообщениях со мной.")
            return

        mode = "list" if "list" in message.text else "clean"
        bot.send_message(message.chat.id, "⏳ Проверяю ваши права в группах...")
        
        # Получаем только те группы, где пользователь админ
        admin_groups = get_admin_groups(message.from_user.id, bot)
        
        if not admin_groups:
            bot.reply_to(message, "❌ Вы не являетесь администратором ни в одной из сохраненных групп.")
            return

        res = f"📂 <b>Режим: {mode.upper()}</b>\nВыберите группу из списка:\n\n"
        kb = InlineKeyboardMarkup()
        
        for i, g in enumerate(admin_groups, 1):
            gid = g['chat_id']
            title = g.get('title', f"Группа {gid}")
            res += f"{i}. <code>{gid}</code> — <b>{title}</b>\n"
            kb.add(InlineKeyboardButton(f"{i}. {title}", callback_data=f"{mode}_{gid}"))
        
        res += "\n💡 <i>Нажмите кнопку, введите порядковый номер или ID группы.</i>"
        bot.send_message(message.chat.id, res, reply_markup=kb, parse_mode="HTML")

    # РУЧНОЕ ДОБАВЛЕНИЕ ИГРОКА
    @bot.message_handler(commands=['add'])
    def cmd_add_manual(message):
        if not is_admin(message.chat.id, message.from_user.id, bot): 
            return bot.reply_to(message, "Эта команда доступна только администраторам.")
            
        args = message.text.split()
        if len(args) < 2:
            return bot.reply_to(message, "📝 Формат: <code>/add @nickname</code>", parse_mode="HTML")
        
        target = args[1].replace("@", "")
        chat_id = message.chat.id
        
        # Сохраняем в БД (теперь с ником)
        add_user_by_username(chat_id, target)
        
        # Если идет активный сбор — добавляем сразу в список
        storage = active_collections.get(chat_id) or test_collection.get(chat_id)
        if storage:
            storage['participants'].append({
                'id': f"manual_{target}", 'name': target, 
                'username': target, 'join_time': time.time()
            })
            update_collection_counter(chat_id, storage, bot, time.time())
            bot.reply_to(message, f"✅ <b>{target}</b> добавлен в базу и в активный сбор!", parse_mode="HTML")
        else:
            bot.reply_to(message, f"✅ <b>{target}</b> успешно внесен в базу данных чата.", parse_mode="HTML")

    # ОБРАБОТЧИК ВВОДА НОМЕРА ИЛИ ID (Для гибридного выбора)
    @bot.message_handler(func=lambda m: m.chat.type == 'private' and not m.text.startswith('/'))
    def handle_manual_input(message):
        text_input = message.text.strip()
        if not text_input.replace('-', '').isdigit(): 
            return

        admin_groups = get_admin_groups(message.from_user.id, bot)
        if not admin_groups: return

        val = int(text_input)
        target_id = None

        # Проверяем: это номер в списке (1, 2, 3...) или прямой ID группы?
        if 1 <= val <= len(admin_groups):
            target_id = admin_groups[val-1]['chat_id']
        else:
            for g in admin_groups:
                if g['chat_id'] == val:
                    target_id = val
                    break

        if target_id:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("📊 Показать статистику", callback_data=f"list_{target_id}"))
            kb.add(InlineKeyboardButton("🗑 Очистить историю", callback_data=f"clean_{target_id}"))
            bot.send_message(message.chat.id, f"📍 Выбрана группа: <code>{target_id}</code>\nЧто необходимо сделать?", reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ Неверный номер или у вас нет прав администратора для этого ID.")

    # СЕРВИСНЫЕ КОМАНДЫ (Только в ЛС)
    @bot.message_handler(commands=['db_reset_members'])
    def cmd_reset(message):
        if message.chat.type == 'private':
            count = clear_all_members()
            bot.reply_to(message, f"🗑 База участников очищена ({count} зап.). Поля username будут заполняться корректно при новых сообщениях.")

    @bot.message_handler(commands=['db_cleanup'])
    def cmd_cleanup(message):
        if message.chat.type == 'private':
            count = cleanup_old_history()
            bot.reply_to(message, f"🧹 Очистка завершена. Удалено {count} записей истории старше 90 дней.")

    # РЕГИСТРАЦИЯ ФУНКЦИЙ СБОРА
    @bot.message_handler(commands=['start_collect'])
    def c_sc(m): start_collection(m, bot, active_collections, test_collection)

    @bot.message_handler(commands=['test'])
    def c_t(m): start_test_collection(m, bot, active_collections, test_collection)

    @bot.message_handler(commands=['stop'])
    def c_st(m): stop_collection(m, bot, active_collections, test_collection)