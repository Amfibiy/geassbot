import pymongo
import datetime
from config.settings import MONGO_URI

# Подключение к MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client['telegram_bot_db']

# Коллекции
history_col = db['collection_history']
members_col = db['chat_members']

def save_history_record(collection_data):
    """Сохраняет завершенный сбор в историю"""
    record = {
        'chat_id': collection_data['chat_id'],
        'title': collection_data['title'],
        'date': datetime.datetime.now(),
        'participants': collection_data['participants'],
        'count': len(collection_data['participants'])
    }
    history_col.insert_one(record)

def get_history_records(chat_id, days=None):
    """Получает историю сборов для конкретной группы"""
    query = {'chat_id': chat_id}
    if days:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        query['date'] = {'$gte': cutoff}
    
    return list(history_col.find(query).sort('date', -1))

def get_known_groups():
    """Получает список всех групп, где был бот (для восстановления стейта)"""
    pipeline = [
        {"$group": {"_id": "$chat_id", "title": {"$first": "$title"}}},
        {"$project": {"chat_id": "$_id", "title": 1, "_id": 0}}
    ]
    return list(history_col.aggregate(pipeline))

def clear_history(chat_id=None):
    """Очищает историю. Если chat_id не передан — чистит всё."""
    if chat_id:
        history_col.delete_many({'chat_id': chat_id})
    else:
        history_col.delete_many({})

def save_user_id(chat_id, user_id, username, first_name):
    """Сохраняет участника группы при его активности"""
    members_col.update_one(
        {'chat_id': chat_id},
        {
            '$addToSet': {
                'members': {
                    'user_id': user_id,
                    'username': username,
                    'first_name': first_name,
                    'last_seen': datetime.datetime.now()
                }
            }
        },
        upsert=True
    )

def get_all_members_ids(chat_id):
    """Возвращает список всех участников группы (для скрытых тегов)"""
    doc = members_col.find_one({'chat_id': chat_id})
    if doc and 'members' in doc:
        return doc['members']
    return []

def save_known_group(chat_id, title):
    """Сохраняет ID и название группы в базу данных"""
    history_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'last_activity': datetime.datetime.now()}},
        upsert=True
    )