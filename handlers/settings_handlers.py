from telebot import types
from utils.helpers import get_admin_groups
from database.mongo import (
    update_group_duration, 
    update_admin_timezone, 
    get_combined_settings,
    add_to_exceptions,
    get_exceptions_list,
    clear_all_exceptions,
    get_exceptions_details, 
    remove_from_exceptions)

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
        
        text = "⚙️ <b>Настройки</b>\nВыберите группу:\n<i>Нажмите на кнопку или отправьте ID группы текстом.</i>\n\n"
        markup = types.InlineKeyboardMarkup()
        for i, g in enumerate(groups, 1):
            title = g.get('title', 'Группа')
            c_id = g.get('chat_id')
            text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
            markup.add(types.InlineKeyboardButton(title, callback_data=f"set_main_{c_id}"))
            
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    
    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'settings_wait_group_id')
    def handle_settings_group_id_input(message):
        user_id = message.from_user.id
        text_id = message.text.strip()
        
        groups = get_admin_groups(user_id, bot)
        valid_ids = [str(g['chat_id']) for g in groups]
        
        if text_id in valid_ids:
            user_sessions[user_id]['step'] = None 
            show_group_main_menu(message.chat.id, text_id, user_id, bot)
        else:
            bot.send_message(message.chat.id, "❌ Неверный ID группы или у вас нет прав. Попробуйте еще раз или выберите из списка.")

    def show_group_main_menu(chat_id_to_send, target_chat_id, user_id, bot, message_id=None):
        configs = get_combined_settings(target_chat_id, user_id)
        text = (f"🛠 <b>Настройки группы {target_chat_id}</b>\n\n"
                f"⏱ Время сбора: <b>{configs['duration'] // 60} мин.</b>\n"
                f"🌍 Ваш часовой пояс: {configs.get('timezone', 'Не задан')}")
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⏱ Изменить время", callback_data=f"set_dur_{target_chat_id}"),
            types.InlineKeyboardButton("🌍 Выбрать часовой пояс", callback_data=f"set_tz_{target_chat_id}"),
            types.InlineKeyboardButton("🚫 Добавить исключения", callback_data=f"set_ex_{target_chat_id}"),
            types.InlineKeyboardButton("🔙 К списку групп", callback_data="set_back_list")
        )
        
        if message_id:
            bot.edit_message_text(text, chat_id_to_send, message_id, reply_markup=markup, parse_mode="HTML")
        else:
            bot.send_message(chat_id_to_send, text, reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_main_'))
    def group_main_menu(call):
        target_chat_id = call.data.replace('set_main_', '')
        user_id = call.from_user.id
        if user_id in user_sessions:
            user_sessions[user_id]['step'] = None
            
        bot.answer_callback_query(call.id)
        show_group_main_menu(call.message.chat.id, target_chat_id, user_id, bot, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_dur_'))
    def ask_duration(call):
        chat_id = call.data.replace('set_dur_', '')
        msg = bot.send_message(call.message.chat.id, "✍️ <b>Введите время сбора в минутах (только число):</b>\nНапишите 'отмена' для выхода.", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_duration_input, chat_id)

    def process_duration_input(message, chat_id):
        if message.text and message.text.lower() in ['отмена', '/cancel', '/stop']:
            bot.reply_to(message, "🚫 Ввод отменен.")
            return

        if not message.text or not message.text.isdigit():
            msg = bot.reply_to(message, "❌ Ошибка! Введите <b>число минут</b> цифрами (например, 60).\nДля отмены напишите 'отмена'.", parse_mode="HTML")
            bot.register_next_step_handler(msg, process_duration_input, chat_id)
            return
    
        val = int(message.text)
        if val < 1 or val > 1440:
            msg = bot.reply_to(message, "⚠️ Время должно быть от 1 до 1440 минут (24 часа). Попробуйте еще раз:")
            bot.register_next_step_handler(msg, process_duration_input, chat_id)
            return

        update_group_duration(chat_id, val)
    
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад к настройкам", callback_data=f"set_main_{chat_id}"))
        bot.send_message(message.chat.id, f"✅ Время сбора обновлено: <b>{val} мин.</b>", reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_tz_'))
    def select_tz_buttons(call):
        chat_id = call.data.replace('set_tz_', '') 
        markup = types.InlineKeyboardMarkup(row_width=3)
        zones = ["МСК-1", "МСК", "МСК+1", "МСК+2", "МСК+3", "МСК+4", "МСК+5", "МСК+6", "МСК+7", "МСК+8", "МСК+9"]
        btns = [types.InlineKeyboardButton(z, callback_data=f"save_tz_{z}:{chat_id}") for z in zones]
        markup.add(*btns)
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}"))
    
        bot.edit_message_text("🌍 <b>Выберите ваш часовой пояс</b> (относительно Москвы):", 
                         call.message.chat.id, 
                         call.message.message_id, 
                         reply_markup=markup,
                         parse_mode="HTML")
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith('save_tz_'))
    def save_tz_final(call):
        parts = call.data.replace('save_tz_', '').split(':')
        new_tz = parts[0]
        chat_id = parts[1] if len(parts) > 1 else ""
        
        update_admin_timezone(call.from_user.id, new_tz)
        
        markup = types.InlineKeyboardMarkup()
        if chat_id:
            markup.add(types.InlineKeyboardButton("🔙 Назад к настройкам", callback_data=f"set_main_{chat_id}"))
        
        bot.edit_message_text(f"✅ Настройка сохранена! Ваш пояс: <b>{new_tz}</b>", 
                             call.message.chat.id, call.message.message_id, 
                             reply_markup=markup, parse_mode="HTML")
        
    @bot.callback_query_handler(func=lambda call: call.data == "set_back_list")
    def back_to_list(call):
        cmd_settings(call.message)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_ex_'))
    def manage_exceptions(call):
        chat_id = call.data.replace('set_ex_', '')
        show_exceptions_menu(call.message, chat_id, bot)
    
    def show_exceptions_menu(message, chat_id, bot):
        users = get_exceptions_details(chat_id)
        
        text = "<b>🚫 Исключения группы</b>\n\n"
        if not users:
            text += "Список пуст. Пользователи из этого списка не будут тегаться ботом."
        else:
            text += "Нажмите на кнопку с пользователем, чтобы <b>удалить</b> его из исключений:"

        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for u in users:
            btn_text = f"❌ @{u['username']}"
            markup.add(types.InlineKeyboardButton(
                text=btn_text, 
                callback_data=f"rm_ex_{u['id']}_{chat_id}"
            ))
            
        markup.add(types.InlineKeyboardButton("➕ Добавить (юзернейм)", callback_data=f"add_ex_mode_{chat_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}"))
        
        bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=markup, parse_mode="HTML")

    def process_exception_input(message, chat_id):
        remove_markup = types.ReplyKeyboardRemove()
        if message.text == "❌ Отмена":
            bot.send_message(message.chat.id, "Ввод отменен. Возвращаемся в меню.", reply_markup=remove_markup)
            return
        
        if message.text and message.text.startswith('/'):
            bot.send_message(message.chat.id, "Ввод прерван командой.", reply_markup=remove_markup)
            return

        username = message.text.strip()
        success, result_msg = add_to_exceptions(chat_id, username)

        markup_inline = types.InlineKeyboardMarkup()
        markup_inline.add(types.InlineKeyboardButton("🔙 Назад к списку", callback_data=f"set_ex_{chat_id}"))

        bot.send_message(message.chat.id, result_msg, reply_markup=remove_markup)
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup_inline)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clear_ex_'))
    def handle_clear_exceptions(call):
        chat_id = call.data.replace('clear_ex_', '')
        clear_all_exceptions(chat_id)
        bot.answer_callback_query(call.id, "✅ Список исключений очищен")
        manage_exceptions(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_dur_'))
    def set_duration_menu(call):
        chat_id = call.data.replace('set_dur_', '')
        markup = types.InlineKeyboardMarkup()
        durations = [15, 30, 45, 60, 90, 120]
        btns = [types.InlineKeyboardButton(f"{d} мин", callback_data=f"save_dur_{d}:{chat_id}") for d in durations]

        for i in range(0, len(btns), 3):
            markup.add(*btns[i:i+3])
            
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}"))
        
        bot.edit_message_text("⏱ <b>Выберите длительность сбора по умолчанию:</b>", 
                             call.message.chat.id, 
                             call.message.message_id, 
                             reply_markup=markup, 
                             parse_mode="HTML")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('save_dur_'))
    def save_duration_final(call):
        data = call.data.replace('save_dur_', '').split(':')
        duration_min = data[0]
        chat_id = data[1]
        
        update_group_duration(chat_id, duration_min)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Назад к настройкам", callback_data=f"set_main_{chat_id}"))
        
        bot.edit_message_text(f"✅ Длительность сбора обновлена: <b>{duration_min} мин.</b>", 
                             call.message.chat.id, 
                             call.message.message_id, 
                             reply_markup=markup, 
                             parse_mode="HTML")
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_ex_'))
    def manage_exceptions(call):
        chat_id = call.data.replace('set_ex_', '')
        current_list = get_exceptions_list(chat_id)
        text = "<b>Управление исключениями</b>\n\n"
        text += f"Текущий список:\n{', '.join(current_list) if current_list else 'Пусто'}\n\n"
        text += "Отправьте username пользователя, которого нужно исключить."

        markup_reply = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup_reply.add("❌ Отмена")

        bot.send_message(call.message.chat.id, "Режим ввода активирован. Для выхода нажмите кнопку ниже:", 
                     reply_markup=markup_reply)
    
        msg = bot.send_message(call.message.chat.id, text, parse_mode="HTML")
        bot.register_next_step_handler(msg, process_exception_input, chat_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('rm_ex_'))
    def handle_remove_exception(call):
        parts = call.data.split('_')
        u_id = parts[2]
        c_id = parts[3]
        
        if remove_from_exceptions(c_id, u_id):
            bot.answer_callback_query(call.id, "✅ Пользователь удален")
            show_exceptions_menu(call.message, c_id, bot)
        else:
            bot.answer_callback_query(call.id, "⚠️ Ошибка удаления")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('add_ex_mode_'))
    def set_add_exception_mode(call):
        chat_id = call.data.replace('add_ex_mode_', '')
        bot.answer_callback_query(call.id)
        
        markup_reply = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup_reply.add("❌ Отмена")

        msg = bot.send_message(call.message.chat.id, "Отправьте username пользователя (без @), которого нужно добавить в исключения:\nДля выхода нажмите 'Отмена'.", reply_markup=markup_reply)
        bot.register_next_step_handler(msg, process_exception_input, chat_id)