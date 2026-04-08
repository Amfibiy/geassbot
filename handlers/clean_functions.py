import time
from telebot import types
from database.mongo import delete_history_records
from utils.helpers import get_admin_groups
from utils.validators import validate_id

def handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions):
    """Начало процесса очистки (выбор группы)"""
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    text = "🧹 <b>Выберите группу для очистки:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    if admin_groups:
        for i, g in enumerate(admin_groups, 1):
            title = g.get('title', 'Группа')
            c_id = g.get('chat_id')
            text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
            markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"clean_group_{c_id}"))
    else:
        text += "<i>Список администрируемых групп пуст.</i>\n"

    text += "\n👇 <b>Нажмите на кнопку выше</b>\nили отправьте ID группы (включая минус) вручную:"
    
    user_sessions[user_id]['step'] = "clean_wait_id"
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def handle_clean_group_id_input(message, bot, user_sessions):
    """Обработка ручного ввода ID группы для очистки"""
    user_id = message.from_user.id
    chat_id = validate_id(message.text)
    
    if not chat_id:
        bot.reply_to(message, "❌ Неверный формат ID. Попробуйте еще раз или используйте /clean")
        return

    # Переходим к выбору действия для этого ID
    show_clean_actions(message.chat.id, chat_id, "Введенная группа", bot, user_sessions, user_id)

def show_clean_actions(chat_to_send, target_chat_id, group_name, bot, user_sessions, user_id):
    """Показ меню выбора периода очистки"""
    user_sessions[user_id]['clean_chat_id'] = target_chat_id
    
    text = f"""🧹 *Очистка истории: {group_name}*

*Выберите действие:*

1️⃣ Удалить всё
2️⃣ Удалить за сегодня
3️⃣ Удалить за вчера
4️⃣ Удалить за последние 7 дней
5️⃣ Удалить за последние 30 дней
6️⃣ Удалить за конкретную дату
7️⃣ Удалить за период (дата1 - дата2)

👇 Отправьте номер действия (1-7) или нажмите кнопку:"""

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("1️⃣ Всё", callback_data="clean_action_all"),
        types.InlineKeyboardButton("2️⃣ Сегодня", callback_data="clean_action_today"),
        types.InlineKeyboardButton("3️⃣ Вчера", callback_data="clean_action_yesterday"),
        types.InlineKeyboardButton("4️⃣ 7 дней", callback_data="clean_action_7days"),
        types.InlineKeyboardButton("5️⃣ 30 дней", callback_data="clean_action_30days")
    ]
    markup.add(*buttons)
    
    user_sessions[user_id]['step'] = "clean_wait_action"
    bot.send_message(chat_to_send, text, reply_markup=markup, parse_mode="Markdown")

def handle_confirm_clean(call, bot, user_sessions):
    """Подтверждение удаления"""
    user_id = call.from_user.id
    session = user_sessions.get(user_id, {})
    chat_id = session.get('clean_chat_id')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"do_actual_clean"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_clean")
    )
    
    bot.edit_message_text(
        f"⚠️ **Вы уверены, что хотите очистить историю для ID `{chat_id}`?**\nЭто действие необратимо.",
        call.message.chat.id, 
        call.message.message_id,
        reply_markup=markup, 
        parse_mode="Markdown"
    )

def execute_delete(call, bot, user_sessions):
    """Финальное удаление из БД после подтверждения"""
    user_id = call.from_user.id
    session = user_sessions.get(user_id, {})
    
    chat_id = session.get('clean_chat_id')
    action = session.get('clean_type') # Получаем тип: 'all', 'today', '7days' и т.д.
    
    if not chat_id or not action:
        bot.answer_callback_query(call.id, "❌ Ошибка: данные сессии потеряны.", show_alert=True)
        return

    try:
        # 1. Раскомментируем и вызываем реальное удаление
        # В mongo.py функция delete_history_records принимает chat_id и тип периода
        delete_history_records(chat_id, action) 
        
        # 2. Обновляем сообщение для пользователя
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ **Очистка завершена!**\n\nВсе записи типа `{action}` для группы `{chat_id}` были удалены.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Ошибка при удалении: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка при обращении к базе данных.", show_alert=True)
    
    # Сбрасываем сессию
    session['step'] = None
    session.pop('clean_type', None)