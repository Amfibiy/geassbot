import time
import datetime
from telebot import types
from database.mongo import load_history_for_chat
from utils.helpers import get_admin_groups

def format_participants_list(participants):
    """Группировка участников по ID, чтобы список был уникальным"""
    unique_participants = {p['id']: p for p in participants if isinstance(p, dict) and 'id' in p}
    count = len(unique_participants)
    if count == 0:
        return "📭 Записей не найдено.", 0
    
    text = f"👥 **Уникальных участников: {count}**\n\n"
    for p_id, p in unique_participants.items():
        name = p.get('name', 'Без имени')
        username = f" (@{p['username']})" if p.get('username') else ""
        text += f"• {name}{username}\n"
    return text, count

def show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    
    if not admin_groups:
        bot.send_message(message.chat.id, "📭 **Список групп пуст.**\nДобавьте бота в группу и выдайте права администратора.")
        return

    text = "📋 **Ваши доступные группы:**\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = g.get('title', 'Группа')
        c_id = g.get('chat_id')
        text += f"{i}. **{title}**\n└ `ID: {c_id}`\n\n"
        markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"list_group_{c_id}"))

    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def show_menu_periods_in_ls(message, session, bot):
    """Вспомогательная функция для вывода меню периодов"""
    chat_id = session.get('chat_id')
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📅 Сегодня", callback_data=f"period_today_{chat_id}"),
        types.InlineKeyboardButton("📅 Вчера", callback_data=f"period_yesterday_{chat_id}"),
        types.InlineKeyboardButton("📅 Неделя", callback_data=f"period_week_{chat_id}"),
        types.InlineKeyboardButton("📅 Месяц", callback_data=f"period_month_{chat_id}"),
        types.InlineKeyboardButton("✍️ Ввести даты", callback_data=f"period_custom_{chat_id}")
    )
    bot.send_message(message.chat.id, "📊 **Выберите период для статистики:**", reply_markup=kb, parse_mode="Markdown")

def handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    user_id = call.from_user.id
    chat_id = int(call.data.split('_')[-1])
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['chat_id'] = chat_id
    user_sessions[user_id]['step'] = "choice_period"
    
    show_menu_periods_in_ls(call.message, user_sessions[user_id], bot)
    bot.answer_callback_query(call.id)

def handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    parts = call.data.split('_')
    period = parts[1]
    chat_id = int(parts[2])
    
    if period == "custom":
        user_id = call.from_user.id
        if user_id not in user_sessions: user_sessions[user_id] = {}
        user_sessions[user_id]['step'] = "input_date_range"
        user_sessions[user_id]['chat_id'] = chat_id
        bot.send_message(call.message.chat.id, "✍️ Введите диапазон дат в формате `ДД-ММ-ГГГГ - ДД-ММ-ГГГГ`\nНапример: `01-01-2024 - 05-01-2024`", parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    now_ts = time.time()
    now_dt = datetime.datetime.fromtimestamp(now_ts)
    
    if period == "today":
        begin = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        end = now_ts
    elif period == "yesterday":
        begin = (now_dt - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        end = begin + 86399
    elif period == "week":
        begin = now_ts - 604800
        end = now_ts
    elif period == "month":
        begin = now_ts - 2592000
        end = now_ts

    records = load_history_for_chat(chat_id, begin, end)
    all_p = []
    for r in records:
        all_p.extend(r.get('participants', []))
    
    res_text, _ = format_participants_list(all_p)
    bot.send_message(call.message.chat.id, res_text, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

def show_result_by_date(message, chat_id, participants, d1, d2, session, bot):
    """Вызывается из callback_functions после успешного ввода текста"""
    res_text, _ = format_participants_list(participants)
    bot.send_message(message.chat.id, f"📊 **Статистика за период {d1} — {d2}:**\n\n{res_text}", parse_mode="Markdown")