import pymongo
import datetime
from config.settings import MONGO_URI

client = pymongo.MongoClient(MONGO_URI)
db = client['telegram_bot_db']
history_col = db['collection_history']
groups_col = db['registered_groups']
members_col = db['chat_members']

def save_known_group(chat_id, title):
    existing = groups_col.find_one({'chat_id': int(chat_id)})
    if not existing:
        print(f"🆕 [DB] Зарегистрирована новая группа: {title} ({chat_id})", flush=True)

    groups_col.update_one(
        {'chat_id': int(chat_id)},
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
    clean_participants = []
    for p in collection_data.get('participants', []):
        clean_participants.append({
            'id': p.get('id'),
            'username': p.get('username')
        })

    record = {
        'chat_id': int(collection_data['chat_id']),
        'title': collection_data.get('title', 'Сбор'),
        'date': datetime.datetime.now(),
        'participants': clean_participants,
        'count': len(clean_participants)
    }
    
    history_col.insert_one(record)
    save_known_group(record['chat_id'], record['title'])
    print(f"💾 [DB] Сохранен сбор: {record['title']} ({record['count']} чел.)", flush=True)

def load_history_for_chat(chat_id, begin_ts=None, end_ts=None):
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
    members_col.update_one(
        {'chat_id': int(chat_id), 'user_id': int(user_id)},
        {'$set': {
            'username': username,
            'last_seen': datetime.datetime.now()
        }},
        upsert=True
    )

def add_user_by_username(chat_id, username):
    username = username.replace('@', '')
    result = members_col.update_one(
        {'chat_id': int(chat_id), 'username': username},
        {'$setOnInsert': {'user_id': None, 'last_seen': datetime.datetime.now()}},
        upsert=True
    )
    return result.upserted_id is not None or result.modified_count > 0

def get_all_members_ids(chat_id):
    docs = members_col.find({'chat_id': int(chat_id)}, {'user_id': 1})
    return [d['user_id'] for d in docs if d.get('user_id')]