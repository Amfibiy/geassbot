from telebot import types
from utils.helpers import get_admin_groups
from database.mongo import (
    update_group_duration, 
    update_admin_timezone, 
    get_combined_settings,
    add_to_exceptions,
    get_exceptions_list,
    clear_all_exceptions)

def register_settings_handlers(bot, user_sessions):
    
    @bot.message_handler(commands=['settings'])
    def cmd_settings(message):
        if message.chat.type != 'private': return
        groups = get_admin_groups(message.from_user.id, bot)
        if not groups:
            bot.reply_to(message, "📭 У вас нет групп для управления.")
            return
        
        markup = types.InlineKeyboardMarkup()
        for g in groups:
            markup.add(types.InlineKeyboardButton(g['title'], callback_data=f"set_main_{g['chat_id']}"))
        bot.send_message(message.chat.id, "⚙️ <b>Настройки</b>\nВыберите группу:", reply_markup=markup, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('set_main_'))
    def group_main_menu(call):
        chat_id = call.data.replace('set_main_', '')
        configs = get_combined_settings(chat_id, call.from_user.id)
        
        text = (f"🛠 <b>Настройки группы</b>\n\n"
                f"⏱ Время сбора: {configs['duration'] // 60} мин\n"
                f"🌍 Ваш часовой пояс: {configs['timezone']}")
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("⏱ Установить время сбора", callback_data=f"set_dur_{chat_id}"),
            types.InlineKeyboardButton("🌍 Выбрать часовой пояс", callback_data=f"set_tz_{chat_id}"),
            types.InlineKeyboardButton("🔙 К списку групп", callback_data="set_back_list")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

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
        current_list = get_exceptions_list(chat_id)
    
        text = "<b>Управление исключениями</b>\n\n"
        text += f"Текущий список:\n{', '.join(current_list) if current_list else 'Пусто'}\n\n"
        text += "Введите username пользователя (с @ или без), которого нужно исключить из рассылки."
    
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🧹 Очистить список", callback_data=f"clear_ex_{chat_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=f"set_main_{chat_id}"))
    
        msg = bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode="HTML")

        bot.register_next_step_handler(msg, process_exception_input, chat_id)

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