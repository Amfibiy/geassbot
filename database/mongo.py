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

def load_history_for_chat(chat_id):
    """Загружает последние записи истории для конкретного чата"""
    return list(history_col.find({'chat_id': chat_id}).sort('date', -1).limit(10))

def get_history_records(chat_id, days=None):
    """Получает историю сборов (универсальная функция)"""
    query = {'chat_id': chat_id}
    if days:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        query['date'] = {'$gte': cutoff}
    return list(history_col.find(query).sort('date', -1))

def save_known_group(chat_id, title):
    """Сохраняет ID и название группы в базу данных"""
    history_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'last_activity': datetime.datetime.now()}},
        upsert=True
    )

def get_known_groups():
    """Получает список всех групп для восстановления состояния"""
    pipeline = [
        {"$group": {"_id": "$chat_id", "title": {"$first": "$title"}}},
        {"$project": {"chat_id": "$_id", "title": 1, "_id": 0}}
    ]
    return list(history_col.aggregate(pipeline))

def clear_history(chat_id=None):
    """Очищает историю"""
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
    """Возвращает список всех участников группы"""
    doc = members_col.find_one({'chat_id': chat_id})
    if doc and 'members' in doc:
        return doc['members']
    return []

def mark_group_inactive(chat_id):
    """Помечает группу как неактивную (например, если бота удалили)"""
    history_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'is_active': False, 'last_activity': datetime.datetime.now()}}
    )

def get_chat_settings(chat_id):
    """Получает настройки конкретного чата (если они есть)"""
    doc = members_col.find_one({'chat_id': chat_id})
    return doc.get('settings', {}) if doc else {}

def delete_history_records(chat_id):
    """Синоним для clear_history, который ищут хендлеры"""
    return clear_history(chat_id)

def get_all_members_ids(chat_id):
    """Возвращает список ID всех участников группы (если хендлеры ищут именно это название)"""
    doc = members_col.find_one({'chat_id': chat_id})
    if doc and 'members' in doc:
        return [m['user_id'] for m in doc['members']]
    return []