import telebot
import logging
from database.mongo import save_known_group

known_groups = None
bot = None # Это заполнится автоматически из main.py

def log_info(msg):
    logging.info(msg)

def get_thread_id(message):
    if hasattr(message, 'message_thread_id') and message.message_thread_id:
        return message.message_thread_id
    return None

def is_admin(chat_id, user_id):
    # Если это личка, админов не существует
    if chat_id == user_id:
        return False
        
    if bot is None:
        log_info("❌ Ошибка: Helpers не получили объект bot!")
        return False

    try:
        member = bot.get_chat_member(chat_id, user_id)
        
        if known_groups is not None and chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_group(chat_id, f"Группа {chat_id}")
            log_info(f"✅ Группа {chat_id} добавлена в список известных")
            
        # Теперь бот точно увидит и тебя (creator), и твоих админов
        return member.status in ['creator', 'administrator']
        
    except Exception as e:
        log_info(f"⚠️ Ошибка проверки админа: {e}")
        return False