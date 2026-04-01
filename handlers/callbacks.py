import datetime
import time
from database.mongo import save_known_group, load_history_for_chat, save_user_id
from utils.validators import validate_date

def handle_group_message(message, bot, active_collections, test_collection, known_groups, user_sessions):
    """Тихое сохранение участников групп"""
    try:
        if not message.from_user.is_bot:
            save_user_id(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
    except Exception as e:
        print(f"❌ Ошибка логирования: {e}")

def handle_private_text(message, bot, active_collections, test_collection, known_groups, user_sessions):
    """Обработка ручного ввода диапазона дат в ЛС"""
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
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
                    end = d2.timestamp() + 86399 # До конца дня
                    
                    records = load_history_for_chat(chat_id, begin, end)
                    all_p = []
                    for r in records:
                        all_p.extend(r.get('participants', []))
                    
                    from .list_functions import show_result_by_date, show_menu_periods_in_ls
                    show_result_by_date(message, chat_id, all_p, parts[0], parts[1], session, bot)
                    
                    # Сбрасываем шаг и возвращаем меню
                    session['step'] = "choice_period"
                    show_menu_periods_in_ls(message, session, bot)
                else:
                    bot.reply_to(message, "❌ Формат дат неверный. Попробуй: 01-01-2024 - 05-01-2024")
            except:
                bot.reply_to(message, "❌ Ошибка парсинга. Проверь пробелы и тире.")
        else:
            bot.reply_to(message, "✍️ Введите две даты через тире с пробелами.")