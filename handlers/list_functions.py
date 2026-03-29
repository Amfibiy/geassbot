import time
import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.mongo import load_history_for_chat

def show_current_collection_in_group(message, collect, bot):
    quantity = len(collect.get('participants', []))
    passed = time.time() - collect['start_time']
    from config.settings import COLLECTION_DURATION
    left = max(0, COLLECTION_DURATION - passed)
    
    minutes_pass = int(passed // 60)
    minutes_left = int(left // 60)
    seconds_left = int(left % 60)
    
    status_text = f"""📊 *Текущий статус сбора:*
👥 Участников: {quantity}
⏱️ Прошло времени: {minutes_pass} мин
⏰ Осталось: {minutes_left:02d}:{seconds_left:02d}"""
    bot.reply_to(message, status_text, parse_mode="Markdown")

def show_menu_periods_in_ls(message, session, bot):
    name = session.get('name_group', f"Группа {session.get('chat_id')}")
    text_menu = f"""📂 *Группа:* {name}

*Выберите период для просмотра статистики:*
1️⃣ Текущий сбор
2️⃣ Сегодня
3️⃣ Вчера
4️⃣ Неделя
5️⃣ Месяц
6️⃣ Квартал
7️⃣ Год
8️⃣ Всё время
9️⃣ Свой период (даты)

👇 Отправьте номер (1-9) или введите дату в формате ДД-ММ-ГГГГ"""
    
    bot.reply_to(message, text_menu, parse_mode="Markdown")

def format_participants_list(participants):
    unique_participants = {p['id']: p for p in participants if isinstance(p, dict) and 'id' in p}
    count = len(unique_participants)
    text = f"👥 Уникальных участников: {count}\n\n"
    for p_id, p in unique_participants.items():
        name = p.get('name', 'Без имени')
        username = f" (@{p['username']})" if p.get('username') else ""
        text += f"• {name}{username}\n"
    return text, count

def show_result_at_date(message, chat_id, participants, date_str, session, bot):
    users_text, count = format_participants_list(participants)
    text = f"📅 *Результаты за {date_str}*\n\n" + users_text
    bot.reply_to(message, text, parse_mode="Markdown")

def show_result_by_date(message, chat_id, participants, date1_str, date2_str, session, bot):
    users_text, count = format_participants_list(participants)
    text = f"📅 *Результаты с {date1_str} по {date2_str}*\n\n" + users_text
    bot.reply_to(message, text, parse_mode="Markdown")

def show_period_in_ls(message, chat_id, period_type, session, bot):
    now = time.time()
    begin = 0
    end = now
    
    if period_type == 'день':
        begin = datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    elif period_type == 'неделя':
        begin = now - 604800
    elif period_type == 'месяц':
        begin = now - 2592000
    elif period_type == 'квартал':
        begin = now - (90 * 86400)
    elif period_type == 'год':
        begin = now - (365 * 86400)
    elif period_type == 'всё':
        begin = 0
        
    records = load_history_for_chat(chat_id, begin, end)
    all_participants = []
    for r in records:
        all_participants.extend(r.get('participants', []))
        
    if not all_participants:
        bot.reply_to(message, f"📭 За период '{period_type.capitalize()}' записей не найдено.")
        return
        
    users_text, count = format_participants_list(all_participants)
    text = f"📊 *Результаты за период: {period_type.capitalize()}*\n\n" + users_text
    bot.reply_to(message, text, parse_mode="Markdown")

# --- ФУНКЦИИ ДЛЯ ИНЛАЙН КНОПОК ---
def show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions):
    keyboard = InlineKeyboardMarkup()
    if message.chat.type == "private":
        for g_id in known_groups:
            try:
                chat_info = bot.get_chat(g_id)
                keyboard.add(InlineKeyboardButton(chat_info.title, callback_data=f"list_group_{g_id}"))
            except: continue
        bot.reply_to(message, "Выберите группу для просмотра статистики:", reply_markup=keyboard)
    else:
        if message.chat.id in active_collections:
            show_current_collection_in_group(message, active_collections[message.chat.id], bot)
        else:
            bot.reply_to(message, "📭 В этой группе сейчас нет активного сбора. Используйте /list в ЛС бота для истории.")

def handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = int(call.data.replace('list_group_', ''))
    user_sessions[call.from_user.id] = {'chat_id': chat_id, 'step': 'choice_period'}
    
    keyboard = InlineKeyboardMarkup()
    keyboard.row(InlineKeyboardButton("Текущий сбор", callback_data="period_1"))
    keyboard.row(InlineKeyboardButton("Сегодня", callback_data="period_2"), InlineKeyboardButton("Вчера", callback_data="period_3"))
    keyboard.row(InlineKeyboardButton("Неделя", callback_data="period_4"), InlineKeyboardButton("Месяц", callback_data="period_5"))
    keyboard.add(InlineKeyboardButton("📅 Выбрать даты", callback_data="period_9"))
    
    bot.edit_message_text("Выберите период:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=keyboard)

def handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id)
    if not session: return

    period_key = call.data
    chat_id = session['chat_id']
    now = time.time()
    
    if period_key == "period_1":
        if chat_id in active_collections:
            show_current_collection_in_group(call.message, active_collections[chat_id], bot)
        else:
            bot.answer_callback_query(call.id, "📭 Нет активного сбора")
        return

    begin, end = 0, now
    if period_key == "period_2":
        begin = datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    elif period_key == "period_3":
        begin = (datetime.datetime.now() - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0).timestamp()
        end = begin + 86400
    elif period_key == "period_4":
        begin = now - 604800
    elif period_key == "period_9":
        session['step'] = "wait_custom_date"
        bot.edit_message_text("Введите период в формате: `ДД-ММ-ГГГГ - ДД-ММ-ГГГГ`", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return

    records = load_history_for_chat(chat_id, begin, end)
    all_participants = []
    for r in records:
        all_participants.extend(r.get('participants', []))
            
    if not all_participants:
        bot.send_message(call.message.chat.id, "📭 За этот период записей не найдено.")
    else:
        users_text, count = format_participants_list(all_participants)
        bot.send_message(call.message.chat.id, f"📊 *Результаты за период:*\n\n{users_text}", parse_mode="Markdown")