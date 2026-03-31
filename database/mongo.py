import os
import time
from pymongo import MongoClient

# Настройка подключения
MONGO_URL = os.getenv('MONGO_URI') or os.getenv('MONGO_URL')
client = MongoClient(MONGO_URL)
db = client['geassbot_db']

# Коллекции
members_col = db['chat_members']       
history_col = db['collection_history'] 
groups_col = db['known_groups']         

# --- РАБОТА С ГРУППАМИ ---

def save_known_group(chat_id, title):
    groups_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'active': True}},
        upsert=True
    )

def mark_group_inactive(chat_id):
    groups_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'active': False}}
    )

def get_known_groups():
    return list(groups_col.find({'active': True}))


def save_user_id(chat_id, user_id, username=None, first_name=None):
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

def get_all_members_ids(chat_id):
    doc = members_col.find_one({'chat_id': chat_id})
    if doc and 'members' in doc:
        return [m['user_id'] for m in doc['members']]
    return []

def add_user_by_username(chat_id, username, first_name=None):
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

# --- ИСТОРИЯ СБОРА ---

def save_history_record(record_data):
    record_data['timestamp'] = time.time()
    history_col.insert_one(record_data)

def load_history_for_chat(chat_id):
    # Возвращаем историю, отсортированную по времени (сначала новые)
    return list(history_col.find({'chat_id': chat_id}).sort('timestamp', -1))

def delete_history_records(chat_id):
    # Полная очистка истории для конкретного чата
    return history_col.delete_many({'chat_id': chat_id}).deleted_count

def clear_all_history():
    return history_col.delete_many({}).deleted_count

def cleanup_old_history():
    quarter_ago = time.time() - (90 * 24 * 60 * 60)
    return history_col.delete_many({'timestamp': {'$lt': quarter_ago}}).deleted_count