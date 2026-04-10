import time
import datetime
from telebot import types
from database.mongo import load_history_for_chat
from utils.helpers import get_admin_groups

def show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions):
    """Показывает стартовое меню выбора группы для просмотра статистики"""
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    if not admin_groups:
        bot.send_message(message.chat.id, "📭 <b>Список групп пуст.</b>\nДобавьте бота в группу и выдайте права администратора.", parse_mode="HTML")
        return

    text = "📋 <b>Ваши доступные группы:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = g.get('title', 'Группа').replace('<', '&lt;').replace('>', '&gt;')
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"list_group_{c_id}"))

    text += "\n👇 <b>Нажмите на кнопку выше</b>\nили отправьте ID группы (включая минус) вручную:"
    
    user_sessions[user_id]['step'] = 'list_input_id'
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_menu_periods_in_ls(message_or_call, session, bot):
    """Единое меню выбора периода для /list"""
    chat_id = session.get('list_chat_id')
    name_group = session.get('name_group', f"Группа {chat_id}").replace('<', '&lt;').replace('>', '&gt;')
    
    text = f"📊 <b>Статистика:</b> {name_group}\nID: <code>{chat_id}</code>\n\n📅 <b>Выберите период:</b>"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Сегодня", callback_data="list_period_today"),
        types.InlineKeyboardButton("Вчера", callback_data="list_period_yesterday")
    )
    markup.row(
        types.InlineKeyboardButton("Неделя", callback_data="list_period_week"),
        types.InlineKeyboardButton("Всё время", callback_data="list_period_all")
    )
    markup.row(
        types.InlineKeyboardButton("✍️ Вручную", callback_data="list_period_manual")
    )
    
    if hasattr(message_or_call, 'message'): # Если это callback
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else: # Если это сообщение (ручной ввод ID)
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_result_by_date(message_or_call, chat_id, begin_ts, end_ts, period_name, session, bot):
    """Вывод итоговой статистики за выбранный период"""
    all_records = load_history_for_chat(chat_id)
    
    # Фильтруем записи
    if begin_ts and end_ts:
        filtered = [r for r in all_records if begin_ts <= r['date'].timestamp() <= end_ts]
    else:
        filtered = all_records # Для "Всё время"

    if not filtered:
        text = f"📭 За период <b>{period_name}</b> записей не найдено."
    else:
        # Собираем уникальных участников
        unique_users = {}
        for r in filtered:
            for p in r.get('participants', []):
                uid = p['id']
                if uid not in unique_users:
                    unique_users[uid] = p
        
        name_group = session.get('name_group', f"Группа {chat_id}").replace('<', '&lt;').replace('>', '&gt;')
        lines = [f"📊 <b>Статистика:</b> {name_group}"]
        lines.append(f"📅 <b>Период:</b> {period_name}")
        lines.append(f"🔄 <b>Проведено сборов:</b> {len(filtered)}")
        lines.append(f"👥 <b>Уникальных участников:</b> {len(unique_users)}\n")
        
        for i, p in enumerate(unique_users.values(), 1):
            username = f"@{p['username']}" if p.get('username') else "Скрыт"
            uid = p.get('id', '???')
            lines.append(f"{i}. {username} (ID: {uid})")
            
        text = "\n".join(lines)
        
        # Обрезка для лимитов Telegram
        if len(text) > 4000:
            text = text[:4000] + "\n\n... <i>Список обрезан из-за лимита символов</i>"

    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, parse_mode="HTML")
    else:
        bot.send_message(message_or_call.chat.id, text, parse_mode="HTML")