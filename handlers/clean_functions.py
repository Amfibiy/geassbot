import datetime
from telebot import types
from database.mongo import delete_history_records, delete_history_record_by_id, load_history_for_chat
from utils.helpers import get_admin_groups

def escape_html(text):
    if not text: return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def handle_clean(message, bot, user_sessions, edit=False):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    if not admin_groups:
        text = "📭 <b>Список групп пуст.</b>\nДобавьте бота в группу и выдайте права администратора."
        if edit:
            bot.edit_message_text(text, message.chat.id, message.message_id, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, text, parse_mode="HTML")
        return

    user_sessions[user_id]['step'] = 'clean_wait_group_id'
    text = "🧹 <b>Выберите группу для очистки:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = escape_html(g.get('title', 'Группа'))
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(f"{i}. {title}", callback_data=f"clean_group_{c_id}"))
    
    if edit:
        bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_clean_periods_menu(call_or_msg, session, bot):
    cid = call_or_msg.message.chat.id if hasattr(call_or_msg, 'message') else call_or_msg.chat.id
    mid = call_or_msg.message.message_id if hasattr(call_or_msg, 'message') else None
    
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
    name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))
    text = f"🧹 <b>Выберите период для очистки:</b>\n{name_group}"

    if mid:
        try:
            bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="HTML")
        except Exception:
            bot.send_message(cid, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="HTML")
        
def show_clean_all_time_menu(call, session, bot):
    markup = types.InlineKeyboardMarkup(row_width=2)
    now = datetime.datetime.now(datetime.timezone.utc)
    markup.add(types.InlineKeyboardButton("🔥 Вся история (УДАЛИТЬ)", callback_data=f"clean_period_0_{int(now.timestamp())}_Вся история"))
    
    buttons = []
    for i in range(12):
        f_day = (now.replace(day=1) - datetime.timedelta(days=i*31)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if f_day.month == 12:
            next_m = f_day.replace(year=f_day.year + 1, month=1)
        else:
            next_m = f_day.replace(month=f_day.month + 1)
        l_day = next_m - datetime.timedelta(seconds=1)
        
        label = f_day.strftime("%m.%Y")
        buttons.append(types.InlineKeyboardButton(text=f"📅 {label}", callback_data=f"clean_mview_{int(f_day.timestamp())}_{int(l_day.timestamp())}_{label}"))
    
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
    bot.edit_message_text("📂 <b>Архив по месяцам (очистка):</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_clean_weeks_menu(call, bot, begin_ts, end_ts, month_label):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(f"🗑 Весь месяц ({month_label})", callback_data=f"clean_period_{begin_ts}_{end_ts}_Месяц {month_label}"))
    
    curr = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    end_dt = datetime.datetime.fromtimestamp(int(float(end_ts)))
    
    w_idx = 1
    while curr <= end_dt:
        w_end = (curr + datetime.timedelta(days=6)).replace(hour=23, minute=59, second=59)
        if w_end > end_dt: w_end = end_dt
        
        lbl = f"{curr.strftime('%d.%m')}-{w_end.strftime('%d.%m')}"
        markup.add(types.InlineKeyboardButton(f"🗓 Неделя {w_idx} ({lbl})", callback_data=f"clean_wview_{int(curr.timestamp())}_{int(w_end.timestamp())}_{lbl}"))
        curr = w_end + datetime.timedelta(seconds=1)
        w_idx += 1
        
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_view_all"))
    bot.edit_message_text(f"📍 Очистка за месяц: <b>{month_label}</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_clean_days_menu(call, bot, begin_ts, end_ts, week_label):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(f"🗑 Вся неделя ({week_label})", callback_data=f"clean_period_{begin_ts}_{end_ts}_Неделя {week_label}"))
    
    curr = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    end_dt = datetime.datetime.fromtimestamp(int(float(end_ts)))
    
    btns = []
    while curr <= end_dt:
        d_end = curr.replace(hour=23, minute=59, second=59)
        lbl = curr.strftime('%d.%m')
        btns.append(types.InlineKeyboardButton(lbl, callback_data=f"clean_dview_{int(curr.timestamp())}_{int(d_end.timestamp())}_{lbl}"))
        curr += datetime.timedelta(days=1)
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_view_all"))
    bot.edit_message_text(f"📅 Дни недели (<b>{week_label}</b>):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_clean_hours_menu(call, bot, begin_ts, end_ts, day_label):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton(f"🗑 Весь день ({day_label})", callback_data=f"clean_period_{begin_ts}_{end_ts}_{day_label}"))
    
    start_dt = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    btns = []
    for h in range(0, 24, 3):
        h_start = start_dt.replace(hour=h, minute=0, second=0)
        h_end = h_start.replace(hour=min(h+2, 23), minute=59, second=59)
        
        tr = f"{h:02d}:00-{h_end.hour:02d}:59"
        btns.append(types.InlineKeyboardButton(tr, callback_data=f"clean_period_{int(h_start.timestamp())}_{int(h_end.timestamp())}_{day_label} {tr}"))
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
    bot.edit_message_text(f"🕒 Время за <b>{day_label}</b>:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_records_for_cleaning(call_or_msg, bot, chat_id, begin, end, label, user_sessions):
    user_id = call_or_msg.from_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id].update({
        'clean_view_begin': begin,
        'clean_view_end': end,
        'clean_view_label': label,
        'clean_chat_id': chat_id
    })

    records = load_history_for_chat(chat_id, float(begin), float(end))
    records = sorted(records, key=lambda x: x.get('timestamp', 0), reverse=True)[:15]

    markup = types.InlineKeyboardMarkup()
    
    if not records:
        text = f"📭 В периоде <b>{label}</b> записей не найдено."
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
    else:
        text = f"🗑 <b>Удаление записей ({label}):</b>\n\nВыберите запись или удалите всё разом."
        
        for r in records:
            r_id = str(r['_id'])
            dt = datetime.datetime.fromtimestamp(r.get('timestamp', 0)).strftime('%d.%m %H:%M')
            count = len(r.get('participants', []))
            markup.add(types.InlineKeyboardButton(f"🕒 {dt} — {count} чел. [УДАЛИТЬ ❌]", callback_data=f"clean_rec_{r_id}"))

        markup.add(types.InlineKeyboardButton(f"🔥 УДАЛИТЬ ВСЕ ЗА {label}", callback_data=f"clean_bulk_{begin}_{end}"))
        markup.add(types.InlineKeyboardButton("🔙 К выбору периода", callback_data="clean_back_to_periods"))

    cid = call_or_msg.message.chat.id if hasattr(call_or_msg, 'message') else call_or_msg.chat.id
    mid = call_or_msg.message.message_id if hasattr(call_or_msg, 'message') else None

    if mid:
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="HTML")

def ask_confirm_clean(call, chat_id, begin, end, period_name, session, bot):
    session.update({'clean_begin': begin, 'clean_end': end, 'clean_period_name': period_name})
    text = f"⚠️ <b>ПОДТВЕРЖДЕНИЕ</b>\n\nВы уверены, что хотите навсегда удалить ВСЕ записи за <b>{period_name}</b> для группы <code>{chat_id}</code>?"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ДА, УДАЛИТЬ", callback_data="clean_confirm_yes"),
        types.InlineKeyboardButton("❌ ОТМЕНА", callback_data="clean_back_to_periods")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def execute_delete(call, bot, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id, {})
    chat_id = session.get('clean_chat_id')
    begin = session.get('clean_begin')
    end = session.get('clean_end')
    
    count = delete_history_records(chat_id, begin, end)
    bot.answer_callback_query(call.id, f"✅ Удалено записей: {count}", show_alert=True)
    show_clean_periods_menu(call, session, bot)