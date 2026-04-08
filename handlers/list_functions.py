import time
import datetime
from telebot import types
from database.mongo import load_history_for_chat, get_group_by_id
from utils.helpers import get_admin_groups

def show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    
    if not admin_groups:
        bot.send_message(message.chat.id, "📭 **Список групп пуст.**\nДобавьте бота в группу и выдайте права администратора.", parse_mode="Markdown")
        return

    text = "📋 **Ваши доступные группы:**\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = g.get('title', 'Группа')
        c_id = g.get('chat_id')
        text += f"{i}. **{title}** (`{c_id}`)\n"
        markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"list_group_{c_id}"))

    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def show_menu_periods_in_ls(message_or_call, session, bot):
    chat_id = session.get('chat_id')
    name_group = session.get('name_group', f"ID: {chat_id}")
    
    text = f"📊 **Статистика для:** {name_group}\nВыберите период:"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📅 Сегодня", callback_data="period_today"))
    markup.add(types.InlineKeyboardButton("🔙 Вчера", callback_data="period_yesterday"))
    markup.add(types.InlineKeyboardButton("📆 За неделю", callback_data="period_week"))
    markup.add(types.InlineKeyboardButton("🗓 За месяц", callback_data="period_month"))
    markup.add(types.InlineKeyboardButton("✍️ Ручной ввод дат", callback_data="period_manual"))
    
    # Редактируем сообщение, если кликнули по кнопке, или отправляем новое, если ввели ID текстом
    if hasattr(message_or_call, 'message_id') and not getattr(message_or_call, 'text', '').startswith('-'):
        bot.edit_message_text(text, message_or_call.chat.id, message_or_call.message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="Markdown")

def handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = int(call.data.replace('list_group_', ''))
    user_id = call.from_user.id
    
    group = get_group_by_id(chat_id)
    if not group:
        bot.answer_callback_query(call.id, "❌ Группа не найдена")
        return

    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Полностью инициализируем сессию, чтобы кнопки работали
    user_sessions[user_id] = {
        'chat_id': chat_id,
        'name_group': group['title'],
        'step': 'choice_period'
    }
    
    show_menu_periods_in_ls(call.message, user_sessions[user_id], bot)
    bot.answer_callback_query(call.id)

def format_participants_list(participants):
    """Группировка участников по ID, чтобы список был уникальным"""
    unique_participants = {p['id']: p for p in participants if isinstance(p, dict) and 'id' in p}
    count = len(unique_participants)
    if count == 0:
        return "📭 Записей не найдено.", 0
    
    text = f"👥 **Уникальных участников: {count}**\n\n"
    for p_id, p in unique_participants.items():
        name = p.get('name', 'Без имени').replace('*', '\\*').replace('_', '\\_')
        username = f" (@{p['username']})" if p.get('username') else ""
        text += f"• {name}{username}\n"
    return text, count

def show_result_by_date(message, chat_id, participants, date_start, date_end, session, bot):
    text_list, count = format_participants_list(participants)
    header = f"📊 **Отчет:** {session.get('name_group', '')}\n📅 Период: {date_start} - {date_end}\n\n"
    bot.send_message(message.chat.id, header + text_list, parse_mode="Markdown")

def handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    user_id = call.from_user.id
    if user_id not in user_sessions or 'chat_id' not in user_sessions[user_id]:
        bot.answer_callback_query(call.id, "❌ Сессия истекла. Введите /list снова.", show_alert=True)
        return

    period = call.data.replace('period_', '')
    chat_id = user_sessions[user_id]['chat_id']
    
    if period == "manual":
        user_sessions[user_id]['step'] = "input_date_range"
        bot.send_message(call.message.chat.id, "✍️ Введите диапазон дат в формате `ДД-ММ-ГГГГ - ДД-ММ-ГГГГ`\nНапример: `01-01-2024 - 05-01-2024`", parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    now_ts = time.time()
    now_dt = datetime.datetime.fromtimestamp(now_ts)
    
    if period == "today":
        begin = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        end = now_ts
        d_str = "Сегодня"
    elif period == "yesterday":
        begin = (now_dt - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        end = begin + 86399
        d_str = "Вчера"
    elif period == "week":
        begin = now_ts - 604800
        end = now_ts
        d_str = "Последние 7 дней"
    elif period == "month":
        begin = now_ts - 2592000
        end = now_ts
        d_str = "Последние 30 дней"

    records = load_history_for_chat(chat_id, begin, end)
    all_p = []
    for r in records:
        all_p.extend(r.get('participants', []))
        
    show_result_by_date(call.message, chat_id, all_p, d_str, d_str, user_sessions[user_id], bot)
    bot.answer_callback_query(call.id)