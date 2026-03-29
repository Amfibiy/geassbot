import os
import time
import datetime
from pymongo import MongoClient
import telebot
import logging

MONGO_URL = os.getenv('MONGO_URI') or os.getenv('MONGO_URL')
client = MongoClient(MONGO_URL)
db = client['geassbot_db']

members_col = db['chat_members']       
history_col = db['collection_history'] 
groups_col = db['known_groups']         

def get_known_groups_for_admin(admin_id, bot, known_groups):
    admin_groups = {}
    if not known_groups:
        return admin_groups
    for g_id in list(known_groups):
        try:
            member = bot.get_chat_member(g_id, admin_id)
            if member.status in ['creator', 'administrator']:
                chat = bot.get_chat(g_id)
                admin_groups[str(g_id)] = chat.title or f"Группа {g_id}"
        except Exception as e:
            logging.info(f"Ошибка проверки админа в {g_id}: {e}")
    return admin_groups

def save_user_id(chat_id, user_id, username=None, first_name=None):
    """Обновляет ник существующего юзера по ID или добавляет нового"""
    now = time.time()
    username = username.lstrip('@') if username else None

    result = members_col.update_one(
        {'chat_id': chat_id, 'members.user_id': user_id},
        {'$set': {
            'members.$.username': username,
            'members.$.first_name': first_name,
            'members.$.last_seen': now
        }}
    )

    if result.matched_count == 0:
        members_col.update_one(
            {'chat_id': chat_id},
            {'$push': {'members': {
                'user_id': user_id, 
                'username': username, 
                'first_name': first_name,
                'last_seen': now
            }}},
            upsert=True
        )

def save_known_group(chat_id, title):
    groups_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'active': True}},
        upsert=True
    )

def get_known_groups():
    cursor = groups_col.find({'active': True})
    return {item['chat_id'] for item in cursor}

def mark_group_inactive(chat_id):
    groups_col.update_one({'chat_id': chat_id}, {'$set': {'active': False}})

def get_all_members_ids(chat_id):
    doc = members_col.find_one({'chat_id': chat_id})
    if doc and 'members' in doc:
        return [m['user_id'] for m in doc['members']]
    return []

def save_history_record(record_data):
    """Сохраняет результат сбора с меткой времени"""
    record_data['timestamp'] = time.time()
    history_col.insert_one(record_data)

def load_history_for_chat(chat_id, start_ts=0, end_ts=None):
    """Загружает историю для команды /list (ЭТОЙ ФУНКЦИИ НЕ ХВАТАЛО)"""
    if end_ts is None:
        end_ts = time.time()
    query = {
        'chat_id': chat_id,
        'timestamp': {'$gte': start_ts, '$lte': end_ts}
    }
    return list(history_col.find(query).sort('timestamp', -1))

def delete_history_records(chat_id, start_ts, end_ts):
    """Удаляет записи за период для команды /clean"""
    query = {
        'chat_id': chat_id,
        'timestamp': {'$gte': start_ts, '$lte': end_ts}
    }
    result = history_col.delete_many(query)
    return result.deleted_count

def clear_all_history(chat_id):
    result = history_col.delete_many({'chat_id': chat_id})
    return result.deleted_count

def add_user_by_username(chat_id, username, first_name=None):
    if not username:
        return False
    username = username.lstrip('@')
    now = time.time()
    
    result = members_col.update_one(
        {'chat_id': chat_id, 'members.username': username},
        {'$set': {
            'members.$.first_name': first_name or username,
            'members.$.last_seen': now
        }}
    )

    if result.matched_count == 0:
        manual_id = f"manual_{username}"
        members_col.update_one(
            {'chat_id': chat_id},
            {'$push': {'members': {
                'user_id': manual_id, 
                'username': username, 
                'first_name': first_name or username,
                'last_seen': now
            }}},
            upsert=True
        )
    return True