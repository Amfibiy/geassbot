import datetime
import time
from database.mongo import delete_history_records, clear_all_history
from database.mongo import get_known_groups_for_admin
from telebot import types
from utils.validators import validate_date

def handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if message.chat.type != "private":
        bot.reply_to(message, "❌ Эту команду нужно использовать в личных сообщениях боту.")
        return

    admin_id = message.from_user.id
    admin_groups = get_known_groups_for_admin(admin_id, bot, known_groups)

    if not admin_groups:
        bot.reply_to(message, "📭 У вас нет доступных групп для управления историей.")
        return

    markup = types.InlineKeyboardMarkup()
    for g_id, g_title in admin_groups.items():
        markup.add(types.InlineKeyboardButton(text=g_title, callback_data=f"clean_group_{g_id}"))

    bot.send_message(message.chat.id, "🧹 **Очистка истории**\nВыберите группу для управления данными:", 
                     reply_markup=markup, parse_mode="Markdown")
def do_clean(message, chat_id, clean_type, parameter, bot):
    """Главная функция для выполнения очистки базы данных"""
    now = time.time()
    
    if clean_type == 'всё':
        deleted = clear_all_history(chat_id)
        bot.reply_to(message, f"✅ Вся история этой группы успешно удалена из базы.\nУдалено записей: {deleted}")
        return
    
    begin = 0
    end = now
    
    if clean_type == "сегодня":
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0)
        begin = today.timestamp()
        end = begin + 86400
        
    elif clean_type == "вчера":
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        begin = yesterday.replace(hour=0, minute=0, second=0).timestamp()
        end = begin + 86400
        
    elif clean_type == "неделя":
        begin = now - 604800
        
    elif clean_type == "месяц":
        begin = now - 2592000
        
    elif clean_type == "дата" and parameter:
        date_obj = validate_date(parameter)
        if date_obj:
            begin = date_obj.timestamp()
            end = begin + 86400
        else:
            bot.reply_to(message, "❌ Ошибка: неверный формат даты.")
            return
            
    elif clean_type == "период" and parameter:
        try:
            parts = parameter.split('-')
            if len(parts) >= 6:
                date1_str = f"{parts[0].strip()}-{parts[1].strip()}-{parts[2].strip()}"
                date2_str = f"{parts[3].strip()}-{parts[4].strip()}-{parts[5].strip()}"
                date1 = validate_date(date1_str)
                date2 = validate_date(date2_str)
                if date1 and date2:
                    begin = date1.timestamp()
                    end = date2.timestamp() + 86400
                else:
                    bot.reply_to(message, "❌ Ошибка: неверный формат дат.")
                    return
            else:
                bot.reply_to(message, "❌ Ошибка: неверный формат периода.")
                return
        except Exception as e:
            bot.reply_to(message, "❌ Произошла ошибка при разборе периода.")
            return
            
    else:
        bot.reply_to(message, "❌ Неизвестный тип очистки.")
        return
    deleted = delete_history_records(chat_id, begin, end)
    bot.reply_to(message, f"✅ Очистка завершена. Удалено записей: {deleted}")

def handle_clean_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    """Выбор действия для конкретной группы"""
    chat_id = call.data.replace("clean_group_", "")
    markup = types.InlineKeyboardMarkup()
    
    actions = [
        ("Сегодня", "today"), ("Вчера", "yesterday"),
        ("Неделя", "week"), ("Месяц", "month"),
        ("Указать дату", "date"), ("Весь период", "all")
    ]
    
    for text, action in actions:
        markup.add(types.InlineKeyboardButton(text=text, callback_data=f"clean_action_{chat_id}_{action}"))
    
    bot.edit_message_text("Выберите, что именно нужно удалить:", 
                         call.message.chat.id, call.message.message_id, reply_markup=markup)

def handle_clean_action_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    """Подтверждение удаления (финальный шаг перед очисткой)"""
    # Формат: clean_action_ID_action
    parts = call.data.split('_')
    chat_id = parts[2]
    action = parts[3]
    
    # Сохраняем данные в сессию, чтобы знать, что чистить после подтверждения
    user_id = call.from_user.id
    if user_id not in user_sessions: user_sessions[user_id] = {}
    
    user_sessions[user_id]['clean_chat_id'] = chat_id
    user_sessions[user_id]['clean_type'] = action
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_clean_{chat_id}"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_clean"))
    
    bot.edit_message_text(f"⚠️ **Вы уверены?**\nЭто действие нельзя будет отменить.", 
                         call.message.chat.id, call.message.message_id, 
                         reply_markup=markup, parse_mode="Markdown")

def handle_confirm_callback(call, bot, active_collections, test_collection, known_groups, user_sessions):
    """Финальное выполнение очистки после подтверждения"""
    user_id = call.from_user.id
    session = user_sessions.get(user_id, {})
    
    chat_id = session.get('clean_chat_id')
    clean_type = session.get('clean_type')
    
    if not chat_id or not clean_type:
        bot.answer_callback_query(call.id, "❌ Ошибка сессии. Попробуйте заново.")
        return
    do_clean(call.message, chat_id, clean_type, None, bot)
    
    session.pop('clean_chat_id', None)
    session.pop('clean_type', None)
    
    bot.edit_message_text("✅ Данные успешно удалены.", call.message.chat.id, call.message.message_id)

def handle_cancel_clean(call, bot):
    """Отмена операции очистки"""
    bot.edit_message_text("❌ Операция отменена.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id, "Отменено")