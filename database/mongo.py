import pymongo
import datetime
from config.settings import MONGO_URI
from bson import ObjectId

client = pymongo.MongoClient(MONGO_URI)
db = client['telegram_bot_db']
history_col = db['collection_history']
groups_col = db['registered_groups']
members_col = db['chat_members']
settings_col = db['group_settings']
admin_prefs_col = db['admin_preferences']


def save_known_group(chat_id, title):
    c_id = int(chat_id)
    existing = groups_col.find_one({'chat_id': c_id})
    if not existing:
        print(f"🆕 [DB] Зарегистрирована новая группа: {title} ({c_id})", flush=True)

    groups_col.update_one(
        {'chat_id': c_id},
        {'$set': {'title': title, 'last_activity': datetime.datetime.now()}},
        upsert=True
    )

def get_known_groups():
    return list(groups_col.find({}, {'_id': 0, 'chat_id': 1, 'title': 1}))

def get_group_by_id(chat_id):
    try:
        return groups_col.find_one({'chat_id': int(chat_id)})
    except (ValueError, TypeError):
        return None

def save_history_record(collection_data):
    chat_id = int(collection_data['chat_id'])
    save_known_group(chat_id, collection_data.get('title', f"Группа {chat_id}"))
    clean_participants = []
    for p in collection_data.get('participants', []):
        clean_participants.append({
            'id': p.get('id'),
            'username': p.get('username'),
            'name': p.get('name', 'Участник')
        })
    record = {
        'chat_id': chat_id,
        'title': collection_data.get('title'),
        'date': datetime.datetime.now(), 
        'participants': clean_participants,
        'is_test': collection_data.get('is_test', False)
    }
    history_col.insert_one(record)
    print(f"✅ [DB] Сбор в чате {chat_id} сохранен отдельно.")

def load_history_for_chat(chat_id, begin_ts, end_ts):
    query = {'chat_id': int(chat_id)}
    if begin_ts and end_ts:
        query['date'] = {
            '$gte': datetime.datetime.fromtimestamp(begin_ts),
            '$lte': datetime.datetime.fromtimestamp(end_ts)
        }
    return list(history_col.find(query).sort('date', -1))

def delete_history_records(chat_id, period_type, *args):
    now = datetime.datetime.now()
    query = {'chat_id': int(chat_id)}
    
    if period_type == 'today':
        query['date'] = {'$gte': now.replace(hour=0, minute=0, second=0, microsecond=0)}
    elif period_type == '7days':
        query['date'] = {'$gte': now - datetime.timedelta(days=7)}
    
    history_col.delete_many(query)

def clear_all_history():
    history_col.delete_many({})

def save_user_id(chat_id, user_id, username, first_name=None):
    c_id = int(chat_id)
    u_id = int(user_id)
    clean_username = username.replace('@', '') if username else None
    
    existing_user = members_col.find_one({'chat_id': c_id, 'user_id': u_id})
    
    if clean_username:
        members_col.update_one(
            {'chat_id': c_id, 'username': clean_username, 'user_id': None},
            {'$set': {'user_id': u_id, 'last_seen': datetime.datetime.now()}}
        )

    members_col.update_one(
        {'chat_id': c_id, 'user_id': u_id},
        {'$set': {
            'username': clean_username,
            'last_seen': datetime.datetime.now()
        }},
        upsert=True
    )

    return existing_user is None

def update_group_duration(chat_id, duration_min):
    settings_col.update_one(
        {'chat_id': int(chat_id)},
        {'$set': {'default_duration': int(duration_min) * 60}},
        upsert=True
    )

def update_admin_timezone(admin_id, tz_string):
    admin_prefs_col.update_one(
        {'admin_id': int(admin_id)},
        {'$set': {'timezone': tz_string}},
        upsert=True
    )

def get_combined_settings(chat_id, admin_id):
    g_set = settings_col.find_one({'chat_id': int(chat_id)}) or {}
    a_set = admin_prefs_col.find_one({'admin_id': int(admin_id)}) or {}
    return {
        'duration': g_set.get('default_duration', 1800),
        'timezone': a_set.get('timezone', 'МСК')
    }

def get_all_members_ids(chat_id):
    members = members_col.find({'chat_id': int(chat_id)})
    return [m['user_id'] for m in members if m.get('user_id') is not None]

def delete_history_record_by_id(record_id):
    try:
        result = history_col.delete_one({'_id': ObjectId(record_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"❌ Ошибка при удалении записи {record_id}: {e}")
        return False