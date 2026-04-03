import pymongo
import datetime
from config.settings import MONGO_URI

# Подключение
client = pymongo.MongoClient(MONGO_URI)
db = client['telegram_bot_db']

# Коллекции
history_col = db['collection_history']
members_col = db['chat_members']

def save_known_group(chat_id, title):
    """Сохраняет группу в базу (используется в callback_functions.py)"""
    history_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'last_activity': datetime.datetime.now()}},
        upsert=True
    )

def get_known_groups():
    """Получает список всех групп (используется в clean_functions.py)"""
    pipeline = [
        {"$group": {"_id": "$chat_id", "title": {"$first": "$title"}}},
        {"$project": {"chat_id": "$_id", "title": 1, "_id": 0}}
    ]
    return list(history_col.aggregate(pipeline))

def save_history_record(collection_data):
    """Сохраняет итоги сбора (используется в collection_functions.py)"""
    record = {
        'chat_id': collection_data['chat_id'],
        'title': collection_data['title'],
        'date': datetime.datetime.now(),
        'participants': collection_data['participants'],
        'count': len(collection_data['participants'])
    }
    history_col.insert_one(record)

def load_history_for_chat(chat_id, begin=None, end=None):
    """Загружает историю (используется в list_functions.py и callback_functions.py)"""
    query = {'chat_id': chat_id}
    if begin and end:
        query['date'] = {
            '$gte': datetime.datetime.fromtimestamp(begin),
            '$lte': datetime.datetime.fromtimestamp(end)
        }
    return list(history_col.find(query).sort('date', -1))

def delete_history_records(chat_id):
    """Удаляет историю конкретного чата (используется в clean_functions.py)"""
    history_col.delete_many({'chat_id': chat_id})

def clear_all_history():
    """Полная очистка (используется в clean_functions.py)"""
    history_col.delete_many({})

def save_user_id(chat_id, user_id, username, first_name):
    """Логирует юзера (используется в callbacks.py)"""
    members_col.update_one(
        {'chat_id': chat_id, 'user_id': user_id},
        {'$set': {
            'username': username,
            'first_name': first_name,
            'last_seen': datetime.datetime.now()
        }},
        upsert=True
    )

def add_user_by_username(chat_id, username):
    """Для команды /add (используется в commands.py)"""
    # Упрощенная логика: просто помечаем, что мы 'знаем' этот ник для этого чата
    members_col.update_one(
        {'chat_id': chat_id, 'username': username.replace('@', '')},
        {'$set': {'added_manually': True, 'date': datetime.datetime.now()}},
        upsert=True
    )
    return True

def get_all_members_ids(chat_id):
    """Получает всех участников (используется в collection_functions.py)"""
    cursor = members_col.find({'chat_id': chat_id})
    return [{'id': m['user_id'], 'username': m.get('username')} for m in cursor if 'user_id' in m]