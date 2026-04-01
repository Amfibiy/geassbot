import time
import datetime
from telebot import types
from database.mongo import load_history_for_chat

def format_participants_list(participants):
    unique_participants = {p['id']: p for p in participants if isinstance(p, dict) and 'id' in p}
    count = len(unique_participants)
    if count == 0: return "📭 Записей не найдено.", 0
    
    text = f"👥 **Уникальных участников: {count}**\n\n"
    for p_id, p in unique_participants.items():
        name = p.get('name', 'Без имени')
        username = f" (@{p['username']})" if p.get('username') else ""
        text += f"• {name}{username}\n"
    return text, count

def show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions):
    # 1. Если вызвано в группе
    if message.chat.type != "private":
        storage = active_collections.get(message.chat.id) or test_collection.get(message.chat.id)
        if storage:
            quantity = len(storage.get('participants', []))
            passed = time.time() - storage['start_time']
            status_text = (
                f"📊 **Текущий статус сбора:**\n"
                f"👥 Участников: {quantity}\n"
                f"⏱️ Прошло: {int(passed // 60)} мин."
            )
            bot.reply_to(message, status_text, parse_mode="Markdown")
        else:
            bot.reply_to(message, "📭 Активного сбора нет. Историю смотрите в ЛС бота.")
        return

    # 2. Если вызвано в ЛС
    groups = list(known_groups.find({"active": True}))
    if not groups:
        return bot.send_message(message.chat.id, "📭 **Групп не обнаружено**\nБот еще не сохранял данные чатов.", parse_mode="Markdown")

    res = "📂 **Выберите группу для просмотра статистики:**\n\n"
    kb = types.InlineKeyboardMarkup()
    for i, g in enumerate(groups, 1):
        gid = g['chat_id']
        title = g.get('title', f"Чат {gid}")
        res += f"{i}. <code>{gid}</code> — <b>{title}</b>\n"
        kb.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"list_group_{gid}"))
    
    res += "\n💡 _Нажмите кнопку или отправьте номер из списка._"
    bot.send_message(message.chat.id, res, reply_markup=kb, parse_mode="HTML")

def handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = int(str(call.data).replace('list_group_', ''))
    user_sessions[call.from_user.id] = {'chat_id': chat_id, 'step': 'choice_period'}
    
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("Сегодня", callback_data=f"period_{chat_id}_today"),
           types.InlineKeyboardButton("Вчера", callback_data=f"period_{chat_id}_yesterday"))
    kb.row(types.InlineKeyboardButton("Неделя", callback_data=f"period_{chat_id}_week"),
           types.InlineKeyboardButton("Месяц", callback_data=f"period_{chat_id}_month"))
    kb.add(types.InlineKeyboardButton("📊 Всё время", callback_data=f"period_{chat_id}_all"))
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_clean"))
    
    bot.edit_message_text(f"📅 **Группа {chat_id}**\nВыберите период:", 
                         chat_id=call.message.chat.id, message_id=call.message.message_id, 
                         reply_markup=kb, parse_mode="Markdown")

def handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    parts = call.data.split('_')
    chat_id, period = int(parts[1]), parts[2]
    now = time.time()
    begin, end = 0, now
    
    if period == "today": begin = datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    elif period == "yesterday":
        begin = (datetime.datetime.now() - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0).timestamp()
        end = begin + 86400
    elif period == "week": begin = now - 604800
    elif period == "month": begin = now - 2592000

    records = load_history_for_chat(chat_id, begin, end)
    all_participants = []
    for r in records: all_participants.extend(r.get('participants', []))
            
    users_text, _ = format_participants_list(all_participants)
    bot.send_message(call.message.chat.id, f"📊 **Результаты ({period}):**\n\n{users_text}", parse_mode="Markdown")