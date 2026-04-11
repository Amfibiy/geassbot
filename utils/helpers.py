import logging
from datetime import datetime
from database.mongo import get_known_groups

def is_admin(chat_id, user_id, bot):
    if chat_id == user_id: 
        return False 
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception as e:
        logging.info(f"Ошибка проверки админа в {chat_id}: {e}")
        return False

def is_bot_admin(chat_id, bot):
    try:
        me = bot.get_me()
        member = bot.get_chat_member(chat_id, me.id)
        return member.status == 'administrator'
    except Exception as e:
        logging.info(f"Ошибка проверки прав бота в {chat_id}: {e}")
        return False

def get_admin_groups(user_id, bot):
    all_groups = get_known_groups()
    admin_groups = []
    
    for g in all_groups:
        try:
            chat_id = int(g['chat_id'])
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ['creator', 'administrator']:
                admin_groups.append(g)
        except Exception:
            continue
    return admin_groups

def format_date(ts):
    return datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M')

def get_thread_id(message):
    return message.message_thread_id if message.is_topic_message else None