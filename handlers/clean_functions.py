import datetime
from telebot import types
from database.mongo import delete_history_records, delete_history_record_by_id, load_history_for_chat
from utils.helpers import get_admin_groups

def handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions, edit=False):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    if not admin_groups:
        text = "📭 <b>Список групп пуст.</b>"
        if edit:
            bot.edit_message_text(text, message.chat.id, message.message_id, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, text, parse_mode="HTML")
        return

    user_sessions[user_id]['step'] = 'clean_wait_group_id'
    text = "🧹 <b>Выберите группу для очистки:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        raw_title = g.get('title', 'Группа')
        title = raw_title.replace('Группа ', '').replace('Группа: ', '')
        title = title.replace('<', '&lt;').replace('>', '&gt;')
        
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(f"{i}. {title}", callback_data=f"clean_group_{c_id}"))

    if edit:
        bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_clean_periods_menu(message_or_call, session, bot, edit=True):
    if hasattr(message_or_call, 'message'):
        chat_id = message_or_call.message.chat.id
        msg_id = message_or_call.message.message_id
    else:
        chat_id = message_or_call.chat.id
        msg_id = message_or_call.message_id

    raw_name = session.get('name_group', 'Группа')
    clean_name = raw_name.replace('Группа ', '').replace('Группа: ', '')
    
    text = f"🧹 <b>Очистка базы данных</b>\n📍 <b>{clean_name}</b>\n\nВыберите период для удаления записей:"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📅 Сегодня", callback_data="clean_view_today"),
        types.InlineKeyboardButton("🗓 Неделя", callback_data="clean_view_week"),
        types.InlineKeyboardButton("📊 Месяц", callback_data="clean_view_month"),
        types.InlineKeyboardButton("🗂 Всё время", callback_data="clean_view_all")
    )
    markup.add(types.InlineKeyboardButton("✍️ Ручной ввод", callback_data="clean_view_manual"))
    markup.add(types.InlineKeyboardButton("🔙 К выбору группы", callback_data="clean_back_to_groups"))

    if edit:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

def show_clean_hours_menu(call, bot, begin_ts, end_ts, day_label):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton(f"🧨 Удалить ВСЕ за {day_label}", callback_data=f"clean_bulk_{begin_ts}_{end_ts}"))
    
    start_dt = datetime.datetime.fromtimestamp(int(begin_ts))
    btns = []
    for h in range(0, 24, 3):
        h_start = int(start_dt.replace(hour=h, minute=0, second=0).timestamp())
        h_end = int(start_dt.replace(hour=min(h+2, 23), minute=59, second=59).timestamp())
        btns.append(types.InlineKeyboardButton(f"⌚ {h:02d}-{h+2:02d}", callback_data=f"clean_drill_{h_start}_{h_end}_{h:02d}-{h+2:02d}"))
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
    bot.edit_message_text(f"⌚ Выберите интервал времени ({day_label}):", call.message.chat.id, call.message.message_id, reply_markup=markup)

def show_records_for_cleaning(call, bot, chat_id, begin_ts, end_ts, label, user_sessions):
    u_id = call.from_user.id
    if u_id in user_sessions:
        user_sessions[u_id].update({
            'clean_begin': begin_ts,
            'clean_end': end_ts,
            'clean_period_name': label
        })

    records = load_history_for_chat(chat_id, begin_ts, end_ts)
    markup = types.InlineKeyboardMarkup()
    
    if records:
        markup.add(types.InlineKeyboardButton(f"🧨 УДАЛИТЬ ВЕСЬ СПИСОК ({label})", 
                   callback_data=f"clean_bulk_{begin_ts}_{end_ts}"))

        for rec in records[:15]:
            time_str = datetime.datetime.fromtimestamp(rec['timestamp']).strftime('%H:%M')
            short_text = (rec.get('text') or "Сбор").replace('<', '&lt;').replace('>', '&gt;')
            short_text = short_text[:20] + "..." if len(short_text) > 20 else short_text
            
            markup.add(
                types.InlineKeyboardButton(f"🕒 {time_str} | {short_text}", callback_data="ignore"),
                types.InlineKeyboardButton("❌", callback_data=f"clean_rec_{rec['_id']}")
            )
    else:
        text = f"📍 <b>{label}</b>\n\n📭 Записи не найдены."
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
        return

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
    
    bot.edit_message_text(f"📍 <b>{label}</b>\n\nНажмите ❌ для удаления конкретного сбора:", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def ask_confirm_clean(message_or_call, chat_id, begin, end, period_name, session, bot):
    session.update({'clean_begin': begin, 'clean_end': end, 'clean_period_name': period_name})
    
    text = f"⚠️ <b>ПОДТВЕРЖДЕНИЕ</b>\n\nВы уверены, что хотите навсегда удалить ВСЕ записи за <b>{period_name}</b> для группы <code>{chat_id}</code>?"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ДА, УДАЛИТЬ", callback_data="clean_confirm_yes"),
        types.InlineKeyboardButton("❌ ОТМЕНА", callback_data="clean_back_to_periods")
    )
    
    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="HTML")

def execute_delete(call, bot, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id, {})
    chat_id = session.get('clean_chat_id')
    begin = session.get('clean_begin')
    end = session.get('clean_end')
    
    if not chat_id:
        bot.answer_callback_query(call.id, "❌ Ошибка сессии")
        return

    deleted = delete_history_records(chat_id, begin, end)
    bot.answer_callback_query(call.id, f"🗑 Удалено записей: {deleted}", show_alert=True)
    show_clean_periods_menu(call, session, bot)