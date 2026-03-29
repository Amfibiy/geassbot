import telebot
import logging
from database.mongo import save_known_group

known_groups = None
bot = None

def log_info(msg):
    logging.info(msg)

def get_thread_id(message):
    if hasattr(message, 'message_thread_id') and message.message_thread_id:
        return message.message_thread_id
    return None

def is_bot_admin(chat_id):
    try:
        me = bot.get_me()
        member = bot.get_chat_member(chat_id, me.id)
        return member.status in ['administrator']
    except Exception:
        return False

def is_admin(chat_id, user_id):

    if chat_id == user_id:
        return False
        
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if known_groups is not None and chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_group(chat_id, f"Группа {chat_id}")
            log_info(f"✅ Группа {chat_id} добавлена в список известных")
            
        return member.status in ['creator', 'administrator']
        
    except telebot.apihelper.ApiTelegramException as e:
        log_info(f"⚠️ Ошибка проверки админа в {chat_id}: {e.description}")
        return False
    except Exception as e:
        log_info(f"❌ Непредвиденная ошибка в is_admin: {e}")
        return False