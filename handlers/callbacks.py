from database.mongo import load_history_for_chat, save_user_id, save_known_group
from utils.validators import validate_date
from .list_functions import show_result_by_date, show_menu_periods_in_ls
from .collection_functions import handle_join
from telebot import types 

def handle_group_message(message, bot, active_collections, test_collection, known_groups, user_sessions):
    try:
        chat_id = message.chat.id
        
        if chat_id not in known_groups:
            save_known_group(chat_id, message.chat.title or f"Группа {chat_id}")
            known_groups.add(chat_id)
        
        if not message.from_user.is_bot:
            save_user_id(
                chat_id=chat_id,
                user_id=message.from_user.id,
                username=message.from_user.username,
            )
    except Exception:
        pass

def handle_private_text(message, bot, active_collections, test_collection, known_groups, user_sessions):
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    if not session: return
    if message.text == "❌ Отмена":
        session['step'] = None
        bot.send_message(
            message.chat.id, 
            "🏠 Действие отменено.", 
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    if session and session.get('step') == "input_date_range":
        text = message.text.strip()
        chat_id = session.get('chat_id')

        if " - " in text:
            try:
                parts = text.split(" - ")
                d1 = validate_date(parts[0].strip())
                d2 = validate_date(parts[1].strip())
                
                if d1 and d2:
                    begin = d1.timestamp()
                    end = d2.replace(hour=23, minute=59, second=59).timestamp()
                    
                    records = load_history_for_chat(chat_id, begin, end)
                    all_p = []
                    for r in records:
                        all_p.extend(r.get('participants', []))
                    
                    show_result_by_date(message, chat_id, begin, end, f"{parts[0]} — {parts[1]}", session, bot)
                    
                    session['step'] = "choice_period"
                    show_menu_periods_in_ls(message, session, bot)
                else:
                    bot.reply_to(message, "❌ Формат дат неверный. Попробуй: 01-01-2024 - 05-01-2024")
            except Exception as e:
                bot.reply_to(message, f"❌ Произошла ошибка: {e}")
        else:
            bot.reply_to(message, "✍️ Используйте формат: ДД-ММ-ГГГГ - ДД-ММ-ГГГГ")

def register_callbacks(bot, active_collections, test_collection, known_groups, user_sessions):

    @bot.message_handler(func=lambda m: m.chat.type in ['group', 'supergroup'])
    def group_msg(message):
        handle_group_message(message, bot, active_collections, test_collection, known_groups, user_sessions)

    @bot.message_handler(func=lambda m: m.chat.type == 'private')
    def private_msg(message):
        handle_private_text(message, bot, active_collections, test_collection, known_groups, user_sessions)