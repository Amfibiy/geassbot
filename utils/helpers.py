import telebot
import logging
from database.mongo import save_known_group

# Глобальные переменные (инициализируются в main.py)
known_groups = None
bot = None

def log_info(msg):
    logging.info(msg)

def is_admin(chat_id, user_id):
    """
    Проверяет права администратора. 
    В ЛС всегда возвращает False для групповых команд.
    """
    if chat_id == user_id:
        return False
        
    try:
        member = bot.get_chat_member(chat_id, user_id)
        
        # Автоматическое добавление группы в базу, если её там нет
        if known_groups is not None and chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_group(chat_id, f"Группа {chat_id}")
            log_info(f"✅ Группа {chat_id} добавлена в список известных")
            
        return member.status in ['creator', 'administrator']
        
    except telebot.apihelper.ApiTelegramException as e:
        log_info(f"⚠️ Ошибка проверки админа в {chat_id}: {e.description}")
        # Можно отправить сообщение в чат, если это критично:
        # bot.send_message(chat_id, "⚠️ Ошибка связи с Telegram API. Попробуйте позже.")
        return False
    except Exception as e:
        log_info(f"❌ Непредвиденная ошибка в is_admin: {e}")
        return False