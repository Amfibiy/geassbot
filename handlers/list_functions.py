import time
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

    text = "📋 <b>Ваши доступные группы:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = escape_html(g.get('title', 'Группа'))
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"list_group_{c_id}"))

    # ИЗМЕНЕНИЕ: Убрали кнопку ручного ввода, изменили подсказку
    text += "\n👇 <b>Выберите группу кнопкой или просто отправьте её ID сообщением:</b>"
    
    if hasattr(message, 'message_id'):
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    else:
        bot.edit_message_text(text, message.message.chat.id, message.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_menu_periods_in_ls(message_or_call, session, bot):
    chat_id = session.get('list_chat_id')
    name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))

    text = f"📅 <b>Выберите период для группы:</b>\n{name_group}\n(ID: <code>{chat_id}</code>)"
    
    markup = types.InlineKeyboardMarkup()
    # Группируем по 2 кнопки в ряд
    markup.row(
        types.InlineKeyboardButton("🕒 1 час", callback_data="list_period_1h"),
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="list_period_today")
    )
    markup.row(
        types.InlineKeyboardButton("📅 Вчера", callback_data="list_period_yesterday"),
        types.InlineKeyboardButton("📅 7 дней", callback_data="list_period_week")
    )
    markup.row(
        types.InlineKeyboardButton("📅 Месяц", callback_data="list_period_month"),
        types.InlineKeyboardButton("♾️ Всё время", callback_data="list_period_all")
    )
    markup.row(types.InlineKeyboardButton("⌨️ Ввести даты вручную", callback_data="list_period_manual"))
    markup.row(types.InlineKeyboardButton("🔙 Назад к списку", callback_data="list_back_to_groups"))

    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_result_by_date(message_or_call, chat_id, begin_ts, end_ts, period_name, session, bot):
    records = load_history_for_chat(chat_id, begin_ts, end_ts)
    
    filtered = []
    for r in records:
        if begin_ts and end_ts:
            if begin_ts <= r['date'].timestamp() <= end_ts:
                filtered.append(r)
        else:
            filtered.append(r)

    if not filtered:
        text = f"📭 За период <b>{period_name}</b> сборов не найдено."
    else:
        unique_users = {}
        for r in filtered:
            for p in r.get('participants', []):
                uid = p['id']
                if uid not in unique_users:
                    unique_users[uid] = {'data': p, 'count': 0}
                unique_users[uid]['count'] += 1
        
        name_group = escape_html(session.get('name_group', f"Группа {chat_id}"))
        lines = [f"📊 <b>Статистика:</b> {name_group}"]
        lines.append(f"📅 <b>Период:</b> {period_name}")
        lines.append(f"🔄 <b>Проведено сборов:</b> {len(filtered)}")
        lines.append(f"👥 <b>Уникальных участников:</b> {len(unique_users)}\n")
        
        sorted_users = sorted(unique_users.values(), key=lambda x: x['count'], reverse=True)
        
        for i, u_info in enumerate(sorted_users, 1):
            p = u_info['data']
            count = u_info['count']
            username = f"@{escape_html(p.get('username'))}" if p.get('username') else "Скрыт"
            uid = p.get('id', 'Неизвестно')
            lines.append(f"{i}. {username} (Участий: <b>{count}</b>) (ID: <code>{uid}</code>)")
            
        text = "\n".join(lines)
        
        if len(text) > 4000:
            text = text[:3900] + "\n... (список обрезан из-за лимитов)"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к периодам", callback_data="list_back_to_periods"))
    
    chat_to_send = message_or_call.message.chat.id if hasattr(message_or_call, 'message') else message_or_call.chat.id
    
    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, chat_to_send, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_to_send, text, reply_markup=markup, parse_mode="HTML")