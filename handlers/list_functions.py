import datetime
from telebot import types
from database.mongo import load_history_for_chat
from utils.helpers import get_admin_groups

def escape_html(text):
    if not text: 
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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
    
    if hasattr(message, 'message_id'):
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.edit_message_text(text, message.message.chat.id, message.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_menu_periods_in_ls(message_or_call, session, bot):
    chat_id = session.get('list_chat_id')
    name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))
    text = f"📅 <b>Выберите период статистики:</b>\n{name_group}"
    
    markup = types.InlineKeyboardMarkup()
    
    # Теперь «Сегодня» и «Вчера» в одном ряду, без лишнего часа
    markup.row(
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="list_view_today"),
        types.InlineKeyboardButton("📅 Вчера", callback_data="list_view_yesterday")
    )
    markup.row(
        types.InlineKeyboardButton("📅 7 дней", callback_data="list_view_week"),
        types.InlineKeyboardButton("📅 Месяц", callback_data="list_view_month")
    )
    markup.row(
        types.InlineKeyboardButton("♾️ Всё время", callback_data="list_view_all")
    )
    markup.row(types.InlineKeyboardButton("⌨️ Ввести даты вручную", callback_data="list_view_manual"))
    markup.row(types.InlineKeyboardButton("🔙 Назад", callback_data="list_back_to_groups"))

    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_result_by_date(message_or_call, chat_id, begin_ts, end_ts, period_name, session, bot):
    records = load_history_for_chat(chat_id, begin_ts, end_ts)
    
    if not records:
        text = f"📭 За период <b>{period_name}</b> сборов не найдено."
    else:
        name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))
        lines = [
            f"📊 <b>Статистика:</b> {name_group}",
            f"📅 <b>Период:</b> {period_name}",
            f"🔄 <b>Всего сборов:</b> {len(records)}\n"
        ]
        
        for r in records:
            participants = r.get('participants', [])
            p_count = len(participants)
            dt = datetime.datetime.fromtimestamp(r.get('start_time', 0))
            time_label = dt.strftime("%H:%M")
            
            lines.append(f"⏱ <b>Время сбора: {time_label} ({p_count})</b>")
            
            if participants:
                for p in participants:
                    p_name = escape_html(p.get('name', 'Без имени'))
                    lines.append(f"{p_name}")
            else:
                lines.append("<i>Список пуст</i>")
            
            lines.append("") 

        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:3900] + "\n... (список слишком длинный)"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к периодам", callback_data="list_back_to_periods"))
    
    chat_id_to_send = message_or_call.message.chat.id if hasattr(message_or_call, 'message') else message_or_call.chat.id
    bot.send_message(chat_id_to_send, text, parse_mode="HTML", reply_markup=markup)

def show_today_hours_menu(call, session, bot):
    markup = types.InlineKeyboardMarkup(row_width=3)
    now = datetime.datetime.now()
    buttons = []

    for h in range(0, 24, 3):
        ts_start = now.replace(hour=h, minute=0, second=0).timestamp()
        ts_end = now.replace(hour=h+2, minute=59, second=59).timestamp()
        time_range = f"{h:02d}:00-{h+2:02d}:59"
        buttons.append(types.InlineKeyboardButton(text=time_range, callback_data=f"list_period_{ts_start}_{ts_end}_{time_range}"))
    
    day_start = now.replace(hour=0, minute=0, second=0).timestamp()
    markup.add(types.InlineKeyboardButton("🌅 Весь день", callback_data=f"list_period_{day_start}_{now.timestamp()}_Сегодня"))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="list_back_to_periods"))
    
    bot.edit_message_text("🕒 Выберите временной интервал за сегодня:", call.message.chat.id, call.message.message_id, reply_markup=markup)

def show_week_days_menu(call, session, bot):
    markup = types.InlineKeyboardMarkup(row_width=2)
    now = datetime.datetime.now()
    buttons = []
    for i in range(7):
        day = now - datetime.timedelta(days=i)
        ts_start = day.replace(hour=0, minute=0, second=0).timestamp()
        ts_end = day.replace(hour=23, minute=59, second=59).timestamp()
        date_str = day.strftime("%d.%m")
        label = "Сегодня" if i == 0 else "Вчера" if i == 1 else date_str
        buttons.append(types.InlineKeyboardButton(text=f"📅 {label}", callback_data=f"list_period_{ts_start}_{ts_end}_{date_str}"))
    
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="list_back_to_periods"))
    bot.edit_message_text("🗓 Выберите день недели:", call.message.chat.id, call.message.message_id, reply_markup=markup)