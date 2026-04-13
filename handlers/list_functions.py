import datetime
from telebot import types
import pytz
from database.mongo import load_history_for_chat
from utils.helpers import get_admin_groups

user_tz = pytz.timezone('Asia/Yekaterinburg')

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
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="list_view_today"),
        types.InlineKeyboardButton("📅 Вчера", callback_data="list_view_yesterday")
    )
    markup.row(
        types.InlineKeyboardButton("📅 Неделя", callback_data="list_view_week"),
        types.InlineKeyboardButton("📅 Месяц", callback_data="list_view_month")
    )
    markup.row(types.InlineKeyboardButton("♾️ Всё время", callback_data="list_view_all"))
    markup.row(types.InlineKeyboardButton("⌨️ Ввести даты вручную", callback_data="list_view_manual"))
    markup.row(types.InlineKeyboardButton("🔙 Назад к группам", callback_data="list_back_to_groups"))

    chat_id = session.get('list_chat_id')
    name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))
    text = f"📅 <b>Выберите период для:</b>\n{name_group}"

    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_result_by_date(call_or_msg, chat_id, begin_ts, end_ts, period_name, session, bot):
    records = load_history_for_chat(chat_id, begin_ts, end_ts)
    
    unique_participants = {}
    for r in records:
        for p in r.get('participants', []):
            u_id = p.get('user_id')
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
            name = escape_html(info['name'])
            username = info['username']
            if username:
                text += f"{i}. {name} (@{username})\n"
            else:
                text += f"{i}. {name}\n"
    else:
        text += "<i>За этот период данных нет.</i>"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 К выбору периода", callback_data="list_back_to_periods"))

    if hasattr(call_or_msg, 'message'):
        bot.edit_message_text(text, call_or_msg.message.chat.id, call_or_msg.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(call_or_msg.chat.id, text, reply_markup=markup, parse_mode="HTML")
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

def show_months_menu(call, session, bot):
    markup = types.InlineKeyboardMarkup(row_width=2)
    now = datetime.datetime.now(user_tz)
    buttons = []
    for i in range(6):
        first_day = (now.replace(day=1) - datetime.timedelta(days=i*31)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if first_day.month == 12:
            next_m = first_day.replace(year=first_day.year + 1, month=1)
        else:
            next_m = first_day.replace(month=first_day.month + 1)
        last_day = next_m - datetime.timedelta(seconds=1)
        
        label = first_day.strftime("%m.%Y")
        buttons.append(types.InlineKeyboardButton(text=label, callback_data=f"list_period_{first_day.timestamp()}_{last_day.timestamp()}_{label}"))
    
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="list_back_to_periods"))
    bot.edit_message_text("🗓 Выберите месяц:", call.message.chat.id, call.message.message_id, reply_markup=markup)