import time
import datetime
from database.groups import save_known_groups

# Эти переменные будут доступны глобально
known_groups = None
collection_history = None
bot = None

def get_thread_id(message):
    """Получает ID темы форума из сообщения"""
    return message.message_thread_id if hasattr(message, 'message_thread_id') else None

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        if known_groups is not None and chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_groups(known_groups)
            print(f"✅ Группа {chat_id} добавлена")
        return member.status in ['creator', 'administrator']
    except Exception:
        return False
    
def is_bot_admin(chat_id):
    """Проверяет, является ли бот администратором в группе"""
    global bot
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