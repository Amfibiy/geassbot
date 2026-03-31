import os
import time
from datetime import datetime, timedelta
from pymongo import MongoClient
import logging

MONGO_URL = os.getenv('MONGO_URI') or os.getenv('MONGO_URL')
client = MongoClient(MONGO_URL)
db = client['geassbot_db']

members_col = db['chat_members']       
history_col = db['collection_history'] 
groups_col = db['known_groups']         

def save_known_group(chat_id, title):
    groups_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'active': True}},
        upsert=True
    )

def get_known_groups():
    """Возвращает список словарей активных групп [{chat_id, title}, ...]"""
    return list(groups_col.find({'active': True}))

def mark_group_inactive(chat_id):
    groups_col.update_one({'chat_id': chat_id}, {'$set': {'active': False}})

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

def add_user_by_username(chat_id, username, first_name=None):
    """Ручное добавление в базу по нику (в любое время)"""
    if not username: return False
    username = username.lstrip('@')
    now = time.time()
    
    result = members_col.update_one(
        {'chat_id': chat_id, 'members.username': username},
        {'$set': {'members.$.last_seen': now}}
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

def get_all_members_ids(chat_id):
    doc = members_col.find_one({'chat_id': chat_id})
    if doc and 'members' in doc:
        return [m['user_id'] for m in doc['members']]
    return []

def clear_all_members():
    """ПОЛНАЯ ОЧИСТКА базы участников (для сброса структуры)"""
    return members_col.delete_many({}).deleted_count

def save_history_record(record_data):
    record_data['timestamp'] = time.time()
    history_col.insert_one(record_data)

def load_history_for_chat(chat_id, start_ts=0, end_ts=None):
    if end_ts is None:
        end_ts = time.time()
    query = {
        'chat_id': chat_id,
        'timestamp': {'$gte': start_ts, '$lte': end_ts}
    }
    return list(history_col.find(query).sort('timestamp', -1))

def delete_history_records(chat_id, start_ts, end_ts):
    query = {
        'chat_id': chat_id,
        'timestamp': {'$gte': start_ts, '$lte': end_ts}
    }
    result = history_col.delete_many(query)
    return result.deleted_count

def clear_all_history(chat_id):
    result = history_col.delete_many({'chat_id': chat_id})
    return result.deleted_count

def cleanup_old_history():
    """Автоочистка истории сборов старше 90 дней (квартал)"""
    quarter_ago = time.time() - (90 * 24 * 60 * 60)
    result = history_col.delete_many({'timestamp': {'$lt': quarter_ago}})
    return result.deleted_count