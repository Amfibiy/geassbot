import logging
import datetime
from database.mongo import get_known_groups

def is_admin(chat_id, user_id, bot):
    if chat_id == user_id: 
        return False 
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False

def is_bot_admin(chat_id, bot):
    try:
        me = bot.get_me()
        member = bot.get_chat_member(chat_id, me.id)
        return member.status == 'administrator'
    except Exception:
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
    return datetime.datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M')

def get_thread_id(message):
    return message.message_thread_id if message.is_topic_message else None

def get_tz_offset_hours(tz_string):
    base_offset = 3  
    if not tz_string or tz_string == "МСК":
        return base_offset
    try:
        if "+" in tz_string:
            return base_offset + int(tz_string.split("+")[1])
        elif "-" in tz_string:
            return base_offset - int(tz_string.split("-")[1])
    except:
        pass
    return base_offset

def get_localized_timestamps(tz_string, period="today"):
    offset = get_tz_offset_hours(tz_string)
    now_utc = datetime.datetime.utcnow()
    now_local = now_utc + datetime.timedelta(hours=offset)
    
    if period == "today":
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = now_local
    elif period == "yesterday":
        start_local = (now_local - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local.replace(hour=23, minute=59, second=59)
    
    start_utc = start_local - datetime.timedelta(hours=offset)
    end_utc = end_local - datetime.timedelta(hours=offset)
    
    return int(start_utc.timestamp()), int(end_utc.timestamp())