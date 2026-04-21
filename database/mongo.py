import pymongo
import datetime
from config.settings import MONGO_URI
from bson import ObjectId
import re

client = pymongo.MongoClient(MONGO_URI)
db = client['telegram_bot_db']
history_col = db['collection_history']
groups_col = db['registered_groups']
members_col = db['chat_members']
settings_col = db['group_settings']
admin_prefs_col = db['admin_preferences']


def save_known_group(chat_id, title):
    c_id = int(chat_id)
    actual_count = members_col.count_documents({'chat_id': c_id})
    
    groups_col.update_one(
        {'chat_id': c_id},
        {'$set': {
            'title': title, 
            'last_activity': datetime.datetime.now(),
            'member_count': actual_count
        }},
        upsert=True
    )

def get_group_member_count(chat_id):
    group = groups_col.find_one({'chat_id': int(chat_id)})
    return group.get('member_count', 0) if group else 0

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

def save_user_id(chat_id, u_id, username):
    c_id = int(chat_id)
    clean_username = username.replace("@", "").strip() if username else None

    existing_user = members_col.find_one({'chat_id': c_id, 'user_id': u_id})
    
    members_col.update_one(
        {'chat_id': c_id, 'user_id': u_id},
        {'$set': {
            'username': clean_username,
            'last_seen': datetime.datetime.now()
        }},
        upsert=True
    )
    
    update_group_actual_count(c_id)
    
    return existing_user is None

def update_group_actual_count(chat_id):
    actual_count = members_col.count_documents({'chat_id': int(chat_id)})
    groups_col.update_one(
        {'chat_id': int(chat_id)},
        {'$set': {'member_count': actual_count}}
    )

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
        'timezone': a_set.get('timezone', 'МСК+2')
    }

def get_all_members_ids(chat_id):
    c_id = int(chat_id)
    settings = settings_col.find_one({'chat_id': c_id}) or {}
    exceptions = settings.get('exceptions', [])
    members = members_col.find({
        'chat_id': c_id, 
        'user_id': {'$nin': exceptions}
    })
    return [m['user_id'] for m in members]

def delete_history_record_by_id(record_id):
    try:
        result = history_col.delete_one({'_id': ObjectId(record_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"❌ Ошибка при удалении записи {record_id}: {e}")
        return False
    
def add_to_exceptions(chat_id, username):
    clean_name = username.replace("@", "").strip()
    user = members_col.find_one({
        'chat_id': int(chat_id), 
        'username': re.compile(f"^{clean_name}$", re.I)
    })
    
    if not user:
        return False, f"Пользователь @{clean_name} не найден. Он должен быть участником группы."
    
    settings_col.update_one(
        {'chat_id': int(chat_id)},
        {'$addToSet': {'exceptions': user['user_id']}},
        upsert=True
    )
    return True, f"✅ @{user['username']} добавлен в исключения."

def get_exceptions_list(chat_id):
    settings = settings_col.find_one({'chat_id': int(chat_id)}) or {}
    ex_ids = settings.get('exceptions', [])
    if not ex_ids:
        return []
    
    users = members_col.find({'chat_id': int(chat_id), 'user_id': {'$in': ex_ids}})
    return [f"@{u['username']}" for u in users if u.get('username')]

def clear_all_exceptions(chat_id):
    settings_col.update_one(
        {'chat_id': int(chat_id)},
        {'$set': {'exceptions': []}}
    )