from telebot import types
from utils.helpers import (
    get_admin_groups,
    get_cancel_kbd, 
    check_cancellation)

from database.mongo import (
    update_group_duration, 
    update_admin_timezone, 
    get_combined_settings,
    add_to_exceptions,
    get_exceptions_list,
    clear_all_exceptions,
    get_exceptions_details, 
    remove_from_exceptions,
    update_internal_tag, 
    get_user_internal_tag, 
    get_chat_members_list,
    save_user_id 
)

def register_settings_handlers(bot, user_sessions):
    
    @bot.message_handler(commands=['settings'])
    def cmd_settings(message):
        if message.chat.type != 'private': return
        user_id = message.from_user.id
        groups = get_admin_groups(user_id, bot)
        
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
            
        if not groups:
            bot.reply_to(message, "📭 У вас нет групп для управления.")
            return
            
        user_sessions[user_id]['step'] = 'settings_wait_group_id'
        
        text = "⚙️ <b>Настройки</b>\nВыберите группу:\n"
        markup = types.InlineKeyboardMarkup()
        for i, g in enumerate(groups, 1):
            title = g.get('title', 'Группа')
            c_id = g.get('chat_id')
            text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
            markup.add(types.InlineKeyboardButton(title, callback_data=f"set_main_{c_id}"))
            
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    def show_group_main_menu(chat_id_to_send, target_chat_id, user_id, bot, message_id=None):
        configs = get_combined_settings(target_chat_id, user_id)
        text = (f"🛠 <b>Настройки группы {target_chat_id}</b>\n\n"
                f"⏱ Время сбора: <b>{configs['duration'] // 60} мин.</b>\n"
                f"🌍 Ваш часовой пояс: {configs.get('timezone', 'Не задан')}")
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⏱ Изменить время", callback_data=f"set_dur_{target_chat_id}"),
            types.InlineKeyboardButton("🌍 Выбрать часовой пояс", callback_data=f"set_tz_{target_chat_id}"),
            types.InlineKeyboardButton("🚫 Исключения", callback_data=f"set_ex_{target_chat_id}"),
            types.InlineKeyboardButton("🏷 Управление тегами", callback_data=f"manage_tags_{target_chat_id}"),
            types.InlineKeyboardButton("🔙 К списку групп", callback_data="set_back_list")
                )
        if message_id: bot.edit_message_text(text, chat_id_to_send, message_id, reply_markup=markup, parse_mode="HTML")
        else: bot.send_message(chat_id_to_send, text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_tz_'))
    def set_timezone_menu(call):
        chat_id = call.data.replace('set_tz_', '')
        markup = types.InlineKeyboardMarkup(row_width=3)
        zones = ["МСК-1", "МСК", "МСК+1", "МСК+2", "МСК+3", "МСК+4"]
        btns = [types.InlineKeyboardButton(tz, callback_data=f"save_tz_{tz}:{chat_id}") for tz in zones]
        markup.add(*btns)
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}"))
        bot.edit_message_text("🌍 <b>Выберите часовой пояс для отчетов:</b>", 
                             call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_dur_'))
    def set_duration_menu(call):
        chat_id = call.data.replace('set_dur_', '')
        markup = types.InlineKeyboardMarkup()
        durations = [15, 30, 45, 60, 90, 120]
        btns = [types.InlineKeyboardButton(f"{d} мин", callback_data=f"save_dur_{d}:{chat_id}") for d in durations]

        for i in range(0, len(btns), 3):
            markup.add(*btns[i:i+3])
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}"))
        
        bot.edit_message_text("⏱ <b>Выберите время или введите число вручную:</b>", 
                             call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")
        
        msg = bot.send_message(call.message.chat.id, "Или напишите количество минут текстом:", reply_markup=get_cancel_kbd())
        bot.register_next_step_handler(msg, process_duration_input, chat_id)

    def process_duration_input(message, chat_id): 
        if check_cancellation(message, bot, user_sessions):
            bot.send_message(message.chat.id, "Действие отменено", reply_markup=types.ReplyKeyboardRemove())
            show_group_main_menu(message.chat.id, chat_id, message.from_user.id, bot)
            return

        if not message.text or not message.text.isdigit():
            msg = bot.send_message(message.chat.id, "⚠️ Введите число минут:", reply_markup=get_cancel_kbd())
            bot.register_next_step_handler(msg, process_duration_input, chat_id) 
            return

        update_group_duration(chat_id, message.text)
        bot.send_message(message.chat.id, f"✅ Время изменено на {message.text} мин.", reply_markup=types.ReplyKeyboardRemove())
        show_group_main_menu(message.chat.id, chat_id, message.from_user.id, bot)

    def show_exceptions_menu(message, chat_id, bot, message_id=None):
        raw_list = get_exceptions_list(chat_id) 
        users_details = get_exceptions_details(chat_id)
        text = "<b>🚫 Исключения группы</b>\n\n"
        if raw_list:
            text += f"<b>Сейчас в списке:</b> {', '.join(raw_list)}\n\n"
            text += "Нажмите на кнопку, чтобы <b>удалить</b>:"
        else: text += "Список пуст. Все участники получают теги."
        markup = types.InlineKeyboardMarkup(row_width=1)
        for u in users_details:
            markup.add(types.InlineKeyboardButton(f"❌ Удалить @{u['username']}", callback_data=f"rm_ex_{u['id']}_{chat_id}"))
        markup.add(types.InlineKeyboardButton("➕ Добавить (юзернейм)", callback_data=f"add_ex_mode_{chat_id}"))
        if raw_list: markup.add(types.InlineKeyboardButton("🗑 Очистить весь список", callback_data=f"clear_ex_{chat_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}"))
        m_id = message_id if message_id else (message.message_id if hasattr(message, 'message_id') else None)
        if m_id: bot.edit_message_text(text, message.chat.id, m_id, reply_markup=markup, parse_mode="HTML")
        else: bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clear_ex_'))
    def handle_clear_exceptions_call(call):
        chat_id = call.data.replace('clear_ex_', '')
        clear_all_exceptions(chat_id)
        bot.answer_callback_query(call.id, "✅ Список исключений полностью очищен")
        show_exceptions_menu(call.message, chat_id, bot, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('add_ex_mode_'))
    def set_add_exception_mode(call):
        chat_id = call.data.replace('add_ex_mode_', '')
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Введите username (без @):", reply_markup=get_cancel_kbd())
        bot.register_next_step_handler(msg, process_exception_input, chat_id)

    def process_exception_input(message, chat_id):
        if check_cancellation(message, bot, user_sessions):
            show_exceptions_menu(message, chat_id, bot)
            return
        username = message.text.strip().replace("@", "")
        success, res_msg = add_to_exceptions(chat_id, username)
        bot.send_message(message.chat.id, res_msg, reply_markup=types.ReplyKeyboardRemove())
        show_exceptions_menu(message, chat_id, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('manage_tags_'))
    def manage_tags_menu(call):
        chat_id = call.data.replace('manage_tags_', '')
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📢 Кнопка получения в чат", callback_data=f"send_tag_btn_{chat_id}"),
            types.InlineKeyboardButton("✏️ Изменить теги участников", callback_data=f"list_tag_members_{chat_id}"),
            types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}")
        )
        bot.edit_message_text("🏷 <b>Управление тегами участников</b>", 
                             call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('send_tag_btn_'))
    def send_tag_button_to_group(call):
        chat_id = int(call.data.replace('send_tag_btn_', ''))
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎁 Получить мой тег", callback_data=f"get_my_tag_{chat_id}"))
        
        try:
            bot.send_message(chat_id, "✨ Администратор активировал раздачу тегов! Нажмите кнопку, чтобы получить свой статус.", reply_markup=markup)
            bot.answer_callback_query(call.id, "✅ Кнопка отправлена в группу")
        except:
            bot.answer_callback_query(call.id, "❌ Ошибка: бот не может писать в группу", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('get_my_tag_'))
    def handle_get_tag_in_group(call):
        chat_id = int(call.data.replace('get_my_tag_', ''))
        user_id = call.from_user.id
        try:
            member = bot.get_chat_member(chat_id, user_id)
            official_tag = (
                getattr(call.message, 'sender_tag', None) or 
                member.json.get('tag') or 
                getattr(member, 'custom_title', None)
            )

            save_user_id(chat_id, user_id, call.from_user.username, call.from_user.first_name, official_tag)
        
            final_tag = get_user_internal_tag(chat_id, user_id)
        
            if final_tag:
                bot.answer_callback_query(call.id, f"✅ Твой статус в базе: {final_tag}", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "💡 Тег не установлен. Установи его в настройках группы или обратись к админу.", show_alert=True)
        except Exception as e:
            print(f"Error in get_tag button: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка доступа. Бот должен быть админом.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_tag_members_'))
    def list_members_for_tags(call):
        chat_id = call.data.replace('list_tag_members_', '')
        members = get_chat_members_list(chat_id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        for m in members[:50]: 
            tag = m.get('internal_tag', '')
            tag_display = f" [{tag}]" if tag else ""
            name = f"{m.get('name', '???')}{tag_display}"
            markup.add(types.InlineKeyboardButton(name, callback_data=f"edt_tag_{m['user_id']}_{chat_id}"))
            
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"manage_tags_{chat_id}"))
        bot.edit_message_text("Выберите пользователя для редактирования:", 
                             call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith('edt_tag_'))
    def ask_tag_text(call):
        parts = call.data.split('_')
        u_id, c_id = parts[2], parts[3]
        msg = bot.send_message(call.message.chat.id, f"Введите новый тег для пользователя {u_id}:", reply_markup=get_cancel_kbd())
        bot.register_next_step_handler(msg, process_tag_input, u_id, c_id)

    def process_tag_input(message, u_id, c_id):
        if check_cancellation(message, bot, user_sessions): 
            bot.send_message(message.chat.id, "Отмена редактирования.", reply_markup=types.ReplyKeyboardRemove())
            list_members_for_tags_manual(message.chat.id, c_id, bot)
            return
        if message.from_user.id in user_sessions:
            user_sessions[message.from_user.id]['step'] = None
        new_tag = message.text.strip()
        update_internal_tag(c_id, u_id, new_tag)
        bot.send_message(message.chat.id, f"✅ Тег '{new_tag}' сохранен.", reply_markup=types.ReplyKeyboardRemove())
        show_tag_management_after_input(message.chat.id, c_id, bot)

    def list_members_for_tags_manual(chat_id_pm, target_chat_id, bot):
        members = get_chat_members_list(target_chat_id)
        markup = types.InlineKeyboardMarkup(row_width=2)
        for m in members[:20]:
            name = m.get('name') or m.get('username') or f"ID {m['user_id']}"
            markup.add(types.InlineKeyboardButton(name, callback_data=f"edt_tag_{m['user_id']}_{target_chat_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"manage_tags_{target_chat_id}"))
        bot.send_message(chat_id_pm, "Выберите пользователя:", reply_markup=markup)

    def show_tag_management_after_input(chat_id_pm, target_chat_id, bot):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📢 Кнопка получения в чат", callback_data=f"send_tag_btn_{target_chat_id}"),
            types.InlineKeyboardButton("✏️ Изменить теги участников", callback_data=f"list_tag_members_{target_chat_id}"),
            types.InlineKeyboardButton("🔙 Назад в меню группы", callback_data=f"set_main_{target_chat_id}")
        )
        bot.send_message(chat_id_pm, "🏷 <b>Управление тегами участников</b>", reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_main_'))
    def group_main_menu_call(call):
        bot.clear_step_handler_by_chat_id(call.message.chat.id) # На случай, если нажали "Назад" при вводе
        target_chat_id = call.data.replace('set_main_', '')
        show_group_main_menu(call.message.chat.id, target_chat_id, call.from_user.id, bot, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "set_back_list")
    def back_to_list_call(call):
        cmd_settings(call.message)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('save_tz_'))
    def save_tz_final(call):
        parts = call.data.replace('save_tz_', '').split(':')
        new_tz, chat_id = parts[0], parts[1]
        update_admin_timezone(call.from_user.id, new_tz)
        show_group_main_menu(call.message.chat.id, chat_id, call.from_user.id, bot, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('rm_ex_'))
    def handle_remove_exception_call(call):
        parts = call.data.split('_')
        u_id, c_id = parts[2], parts[3]
        remove_from_exceptions(c_id, u_id)
        show_exceptions_menu(call.message, c_id, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('save_dur_'))
    def save_duration_btn(call):
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        
        parts = call.data.replace('save_dur_', '').split(':')
        dur, chat_id = int(parts[0]), parts[1]
        update_group_duration(chat_id, dur)
        bot.answer_callback_query(call.id, f"✅ Сохранено: {dur} мин.")
        show_group_main_menu(call.message.chat.id, chat_id, call.from_user.id, bot, call.message.message_id)
    
    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'settings_wait_group_id')
    def process_manual_group_id(message):
        if check_cancellation(message, bot, user_sessions): return
        target_id = message.text.strip()

        try:
            member = bot.get_chat_member(int(target_id), message.from_user.id)
            if member.status in ['creator', 'administrator']:
                user_sessions[message.from_user.id]['step'] = None
                show_group_main_menu(message.chat.id, target_id, message.from_user.id, bot)
            else:
                bot.reply_to(message, "❌ Вы не администратор в этой группе.")
        except:
            bot.reply_to(message, "❌ Группа не найдена или бот в ней не состоит.")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('edt_tag_'))
    def ask_tag_text(call):
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        
        parts = call.data.split('_')
        u_id, c_id = parts[2], parts[3]
        
        current_tag = get_user_internal_tag(c_id, u_id) or "не установлен"
        
        text = (f"👤 Пользователь ID: <code>{u_id}</code>\n"
                f"🏷 Текущий тег: <b>{current_tag}</b>\n\n"
                f"Введите новый текст тега (до 16 симв.):")
        
        msg = bot.send_message(call.message.chat.id, text, 
                               reply_markup=get_cancel_kbd(), parse_mode="HTML")
        bot.register_next_step_handler(msg, process_tag_input, u_id, c_id)
    