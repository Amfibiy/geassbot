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
    """Сохраняет группу в базу"""
    history_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'last_activity': datetime.datetime.now()}},
        upsert=True
    )

def get_known_groups():
    """Получает список всех групп"""
    pipeline = [
        {"$group": {"_id": "$chat_id", "title": {"$first": "$title"}}},
        {"$project": {"chat_id": "$_id", "title": 1, "_id": 0}}
    ]
    return list(history_col.aggregate(pipeline))

def get_group_by_id(chat_id):
    """Найти группу по ID (для ручного ввода в ЛС)"""
    try:
        return history_col.find_one({'chat_id': int(chat_id)})
    except:
        return None

def save_history_record(collection_data):
    """Сохраняет итоги сбора"""
    record = {
        'chat_id': collection_data['chat_id'],
        'title': collection_data['title'],
        'date': datetime.datetime.now(),
        'participants': collection_data['participants']
    }
    history_col.insert_one(record)

def load_history_for_chat(chat_id, begin_ts, end_ts):
    """Загружает историю сборов по датам"""
    begin_dt = datetime.datetime.fromtimestamp(begin_ts)
    end_dt = datetime.datetime.fromtimestamp(end_ts)
    return list(history_col.find({
        'chat_id': chat_id,
        'date': {'$gte': begin_dt, '$lte': end_dt}
    }))

def delete_history_records(chat_id, begin_ts=None, end_ts=None):
    """Удаляет историю для группы"""
    if begin_ts and end_ts:
        begin_dt = datetime.datetime.fromtimestamp(begin_ts)
        end_dt = datetime.datetime.fromtimestamp(end_ts)
        history_col.delete_many({
            'chat_id': chat_id,
            'date': {'$gte': begin_dt, '$lte': end_dt}
        })
    else:
        history_col.delete_many({'chat_id': chat_id})

def clear_all_history():
    """Полная очистка базы"""
    history_col.delete_many({})

def save_user_id(chat_id, user_id, username, first_name):
    """Логирует юзера и очищает имя от символов Markdown"""
    clean_name = str(first_name).replace('*', '').replace('_', '').replace('`', '') if first_name else "Без имени"
    members_col.update_one(
        {'chat_id': chat_id, 'user_id': user_id},
        {'$set': {
            'username': username,
            'first_name': clean_name,
            'last_seen': datetime.datetime.now()
        }},
        upsert=True
    )

def add_user_by_username(chat_id, username):
    """Для команды /add"""
    members_col.update_one(
        {'chat_id': chat_id, 'username': username.replace('@', '')},
        {'$set': {'added_manually': True, 'date': datetime.datetime.now()}},
        upsert=True
    )
    return True

def get_all_members_ids(chat_id):
    """Получает всех участников группы"""
    cursor = members_col.find({'chat_id': chat_id}, {'user_id': 1})
    return [doc['user_id'] for doc in cursor if 'user_id' in doc]

def mark_group_inactive(chat_id):
    pass