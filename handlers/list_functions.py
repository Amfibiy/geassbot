import time
import datetime
from telebot import types
from database.mongo import load_history_for_chat

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
    """Команда /list — показывает список доступных групп"""
    from database.mongo import get_known_groups
    groups = get_known_groups()
    if not groups:
        bot.send_message(message.chat.id, "📭 Список групп пуст.")
        return

    kb = types.InlineKeyboardMarkup()
    for g in groups:
        kb.add(types.InlineKeyboardButton(text=g.get('title', 'Группа'), callback_data=f"list_group_{g['chat_id']}"))
    
    bot.send_message(message.chat.id, "📋 **Выберите группу:**", reply_markup=kb, parse_mode="Markdown")

def handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    """Меню выбора периода времени"""
    chat_id = int(call.data.replace('list_group_', ''))
    kb = types.InlineKeyboardMarkup()
    
    kb.row(types.InlineKeyboardButton("Сегодня", callback_data=f"period_{chat_id}_today"),
           types.InlineKeyboardButton("Вчера", callback_data=f"period_{chat_id}_yesterday"))
    
    kb.row(types.InlineKeyboardButton("Неделя", callback_data=f"period_{chat_id}_week"),
           types.InlineKeyboardButton("Месяц", callback_data=f"period_{chat_id}_month"))
    
    # Кнопка для ручного ввода, которую мы добавили
    kb.add(types.InlineKeyboardButton("📅 Свой диапазон", callback_data=f"period_{chat_id}_custom"))
    kb.add(types.InlineKeyboardButton("📊 Всё время", callback_data=f"period_{chat_id}_all"))
    
    bot.edit_message_text(f"📅 **Группа:** `{chat_id}`\nВыберите период поиска:", 
                         call.message.chat.id, call.message.message_id, 
                         reply_markup=kb, parse_mode="Markdown")

def handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    """Логика быстрых кнопок и переключение в режим ручного ввода"""
    parts = call.data.split('_')
    chat_id, period = int(parts[1]), parts[2]
    
    now_dt = datetime.datetime.now()
    now_ts = now_dt.timestamp()
    begin, end = 0, now_ts

    # Если выбрали ручной ввод
    if period == "custom":
        user_sessions[call.from_user.id] = {'step': 'input_date_range', 'chat_id': chat_id}
        bot.send_message(call.message.chat.id, "✍️ Введите диапазон дат через тире:\n`01-01-2024 - 05-01-2024`", parse_mode="Markdown")
        return

    # Логика быстрых периодов
    if period == "today":
        begin = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    elif period == "yesterday":
        begin = (now_dt - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        end = begin + 86399
    elif period == "week":
        begin = now_ts - 604800
    elif period == "month":
        begin = now_ts - 2592000 # 30 дней

    records = load_history_for_chat(chat_id, begin, end)
    all_p = []
    for r in records:
        all_p.extend(r.get('participants', []))
    
    res_text, _ = format_participants_list(all_p)
    bot.send_message(call.message.chat.id, res_text, parse_mode="Markdown")

def show_result_by_date(message, chat_id, participants, d1, d2, session, bot):
    """Вызывается из callback_functions после успешного ввода текста"""
    res_text, _ = format_participants_list(participants)
    bot.send_message(message.chat.id, f"🗓 **Результат за {d1} — {d2}:**\n{res_text}", parse_mode="Markdown")

def show_menu_periods_in_ls(message, session, bot):
    """Возвращает кнопки выбора после вывода результата"""
    chat_id = session.get('chat_id')
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 К выбору периодов", callback_data=f"list_group_{chat_id}"))
    bot.send_message(message.chat.id, "Что-нибудь еще?", reply_markup=kb)