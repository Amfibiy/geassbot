import datetime
from telebot import types
from database.mongo import load_history_for_chat,get_user_internal_tag,get_combined_settings
from utils.helpers import get_admin_groups,escape_html,get_tz_offset_hours

def show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    if not admin_groups:
        bot.send_message(message.chat.id, "📭 <b>Список групп пуст.</b>\nНапишите любое сообщение в вашей группе с ботом, чтобы она зарегистрировалась.", parse_mode="HTML")
        return
    user_sessions[user_id]['step'] = 'list_wait_group_id'

    text = "📋 <b>Ваши доступные группы:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = escape_html(g.get('title', 'Группа'))
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"list_group_{c_id}"))

    text += "\n👇 <b>Выберите группу кнопкой или просто отправьте её ID сообщением:</b>"
    
    chat_id = message.chat.id if hasattr(message, 'chat') else message.message.chat.id
    if hasattr(message, 'message_id'):
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.edit_message_text(text, chat_id, message.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_menu_periods_in_ls(message_or_call, session, bot):
    chat = message_or_call.message.chat if hasattr(message_or_call, 'message') else message_or_call.chat
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="list_view_today"),
        types.InlineKeyboardButton("📅 Вчера", callback_data="list_view_yesterday")
    )
    markup.row(
        types.InlineKeyboardButton("🗓 Неделя", callback_data="list_view_week"),
        types.InlineKeyboardButton("📆 Месяц", callback_data="list_view_month")
    )
    markup.row(types.InlineKeyboardButton("♾️ Всё время", callback_data="list_view_all"))
    markup.row(types.InlineKeyboardButton("⌨️ Ввести даты вручную", callback_data="list_view_manual"))
    markup.row(types.InlineKeyboardButton("🔙 Назад к группам", callback_data="list_back_to_groups"))

    chat_id = session.get('list_chat_id')
    name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))
    text = f"📅 <b>Выберите период для:</b>\n{name_group}"

    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_result_by_date(call_or_msg, chat_id, begin_ts, end_ts, period_name, session, bot, back_cb="list_back_to_periods"):
    records = load_history_for_chat(chat_id, float(begin_ts), float(end_ts))
    
    unique_participants = {}
    for r in records:
        for p in r.get('participants', []):
            u_id = p.get('id') or p.get('user_id') 
            if u_id and u_id not in unique_participants:
                unique_participants[u_id] = {
                    'name': p.get('name', 'Аноним'),
                    'username': p.get('username')
                }

    count = len(unique_participants)
    name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))
    
    text = f"📊 <b>Статистика: {name_group}</b>\n"
    text += f"📅 Период: <b>{period_name}</b>\n"
    text += f"👥 Всего участников: <b>{count}</b>\n\n"

    if count > 0:
        text += "<b>Список участников:</b>\n"
        for i, (u_id, info) in enumerate(unique_participants.items(), 1):
            name_escaped = escape_html(info['name'])
            
            mention = f'<a href="tg://user?id={u_id}">{name_escaped}</a>'
            
            tag = get_user_internal_tag(chat_id, u_id)
            tag_display = f" (<code>{escape_html(tag)}</code>)" if tag else ""
            
            text += f"{i}. {mention}{tag_display}\n"
    else:
        text += "<i>За этот период данных нет.</i>"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))

    cid = call_or_msg.message.chat.id if hasattr(call_or_msg, 'message') else call_or_msg.chat.id
    mid = call_or_msg.message.message_id if hasattr(call_or_msg, 'message') else None

    if mid:
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="HTML")

def show_all_time_menu(call, session, bot):
    markup = types.InlineKeyboardMarkup(row_width=2)
    chat_id = session.get('list_chat_id')
    settings = get_combined_settings(chat_id, call.from_user.id)
    offset = get_tz_offset_hours(settings.get('timezone', 'МСК+2'))
    
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=offset)
    
    markup.add(types.InlineKeyboardButton("♾️ Вся история", callback_data=f"list_period_0_{int(now.timestamp())}_Вся история"))
    
    buttons = []
    first_day_of_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(12):
        m_start = first_day_of_current
        for _ in range(i):
            m_start = (m_start - datetime.timedelta(days=1)).replace(day=1)
            
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1) - datetime.timedelta(seconds=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1) - datetime.timedelta(seconds=1)
        
        begin_utc = (m_start - datetime.timedelta(hours=offset)).timestamp()
        end_utc = (m_end - datetime.timedelta(hours=offset)).timestamp()
        
        label = m_start.strftime("%m.%Y")
        buttons.append(types.InlineKeyboardButton(
            text=f"📅 {label}", 
            callback_data=f"list_mview_{int(begin_utc)}_{int(end_utc)}_{label}"
        ))
    
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="list_back_to_periods"))
    bot.edit_message_text("📂 <b>Архив по месяцам:</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_weeks_of_month_menu(call, bot, begin_ts, end_ts, month_label, back_cb="list_back_to_periods"):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(f"📊 Весь месяц ({month_label})", callback_data=f"list_period_{begin_ts}_{end_ts}_Месяц {month_label}"))
    
    curr = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    end_dt = datetime.datetime.fromtimestamp(int(float(end_ts)))
    
    w_idx = 1
    while curr <= end_dt:
        w_end = (curr + datetime.timedelta(days=6)).replace(hour=23, minute=59, second=59)
        if w_end > end_dt: w_end = end_dt
        
        lbl = f"{curr.strftime('%d.%m')}-{w_end.strftime('%d.%m')}"
        markup.add(types.InlineKeyboardButton(f"🗓 Неделя {w_idx} ({lbl})", callback_data=f"list_wview_{int(curr.timestamp())}_{int(w_end.timestamp())}_{lbl}"))
        curr = w_end + datetime.timedelta(seconds=1)
        w_idx += 1
        
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    bot.edit_message_text(f"📍 Месяц: <b>{month_label}</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_days_of_week_menu(call, bot, begin_ts, end_ts, week_label, back_cb="list_back_to_periods"):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(f"📊 Вся неделя ({week_label})", callback_data=f"list_period_{begin_ts}_{end_ts}_Неделя {week_label}"))
    
    curr = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    end_dt = datetime.datetime.fromtimestamp(int(float(end_ts)))
    
    btns = []
    while curr <= end_dt:
        d_end = curr.replace(hour=23, minute=59, second=59)
        lbl = curr.strftime('%d.%m')
        btns.append(types.InlineKeyboardButton(lbl, callback_data=f"list_dview_{int(curr.timestamp())}_{int(d_end.timestamp())}_{lbl}"))
        curr += datetime.timedelta(days=1)
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    bot.edit_message_text(f"📅 Дни недели (<b>{week_label}</b>):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_hours_of_day_menu(call, bot, begin_ts, end_ts, day_label, back_cb="list_back_to_periods"):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton(f"📊 Весь день ({day_label})", callback_data=f"list_period_{begin_ts}_{end_ts}_{day_label}"))
    start_dt_utc = datetime.datetime.fromtimestamp(int(float(begin_ts)), datetime.timezone.utc)
    
    btns = []
    for h in range(0, 24, 3):
        h_start = start_dt_utc + datetime.timedelta(hours=h)
        h_end = h_start + datetime.timedelta(hours=2, minutes=59, seconds=59)

        tr = f"{h:02d}:00-{h+2:02d}:59"
        btns.append(types.InlineKeyboardButton(
            tr, 
            callback_data=f"list_period_{int(h_start.timestamp())}_{int(h_end.timestamp())}_{day_label} {tr}"
        ))
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    bot.edit_message_text(f"🕒 Время за <b>{day_label}</b> (локальное):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")