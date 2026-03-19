import time
import datetime
from database.groups import save_known_groups

def get_thread_id(message):
    """Получает ID темы форума из сообщения"""
    return message.message_thread_id if hasattr(message, 'message_thread_id') else None

def is_admin(chat_id, user_id, bot, known_groups):
    """Проверяет, является ли пользователь администратором"""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_groups(known_groups)
        return member.status in ['creator', 'administrator']
    except Exception:
        if chat_id in known_groups:
            known_groups.remove(chat_id)
            save_known_groups(known_groups)
        return False

def is_bot_admin(chat_id, bot):
    """Проверяет, является ли бот администратором в группе"""
    try:
        me = bot.get_me()
        member = bot.get_chat_member(chat_id, me.id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def format_time_left(seconds):
    """Форматирует оставшееся время"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def get_current_timestamp():
    """Возвращает текущий timestamp"""
    return time.time()