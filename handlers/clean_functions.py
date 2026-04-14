import datetime
from telebot import types
from database.mongo import delete_history_records, delete_history_record_by_id, load_history_for_chat
from utils.helpers import get_admin_groups

def handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    if not admin_groups:
        bot.send_message(message.chat.id, "📭 <b>Список групп пуст.</b>", parse_mode="HTML")
        return

    user_sessions[user_id]['step'] = 'clean_wait_group_id'

    text = "🧹 <b>Выберите группу для очистки:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = g.get('title', 'Группа').replace('<', '&lt;').replace('>', '&gt;')
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"clean_group_{c_id}"))

    text += "\n👇 Или введите ID группы вручную:"
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_clean_periods_menu(call, session, bot):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="clean_view_today"),
        types.InlineKeyboardButton("📅 Вчера", callback_data="clean_view_yesterday")
    )
    markup.row(
        types.InlineKeyboardButton("🗓 Неделя", callback_data="clean_view_week"),
        types.InlineKeyboardButton("📆 Месяц", callback_data="clean_view_month")
    )
    markup.row(types.InlineKeyboardButton("♾️ Всё время", callback_data="clean_view_all"))
    markup.row(types.InlineKeyboardButton("⌨️ Ввести даты вручную", callback_data="clean_view_manual"))
    markup.row(types.InlineKeyboardButton("🔙 Назад к группам", callback_data="clean_back_to_groups"))

    chat_id = session.get('clean_chat_id')
    text = f"🧹 <b>Выберите период для ОЧИСТКИ в группе:</b>\n<code>{chat_id}</code>"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

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

def show_records_for_cleaning(call, chat_id, begin_ts, end_ts, label, bot):
    records = list(load_history_for_chat(chat_id, begin_ts, end_ts))
    
    if not records:
        bot.answer_callback_query(call.id, "❌ Сборов за это время не найдено", show_alert=True)
        return

    text = f"🗑 <b>Выберите сбор для удаления ({label}):</b>"
    markup = types.InlineKeyboardMarkup()
    
    for rec in records:
        dt = datetime.datetime.fromtimestamp(rec['timestamp']).strftime('%H:%M (%d.%m)')
        count = len(rec.get('participants', []))
        btn_text = f"❌ Сбор {dt} ({count} чел.)"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"clean_rec_{str(rec['_id'])}"))
    
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

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