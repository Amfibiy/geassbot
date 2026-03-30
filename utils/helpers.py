import telebot
import logging
from database.mongo import save_known_group

known_groups = None
bot = None # Заполняется из main.py

def log_info(msg):
    logging.info(msg)

def get_thread_id(message):
    if hasattr(message, 'message_thread_id') and message.message_thread_id:
        return message.message_thread_id
    return None

def is_bot_admin(chat_id):
    """Проверяет, является ли сам бот админом в чате"""
    if bot is None: return False
    try:
        me = bot.get_me()
        member = bot.get_chat_member(chat_id, me.id)
        return member.status in ['administrator']
    except Exception:
        return False

def is_admin(chat_id, user_id):
    """Проверяет, является ли пользователь админом или создателем"""
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
            
        # Проверяем на создателя и админа
        return member.status in ['creator', 'administrator']
        
    except Exception as e:
        log_info(f"⚠️ Ошибка проверки админа: {e}")
        return False