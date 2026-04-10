import pymongo
import datetime
from config.settings import MONGO_URI

# Подключение к базе данных
client = pymongo.MongoClient(MONGO_URI)
db = client['telegram_bot_db']

# Коллекции
history_col = db['collection_history']
members_col = db['chat_members']

def save_known_group(chat_id, title):
    """Сохраняет или обновляет данные о группе"""
    history_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'last_activity': datetime.datetime.now()}},
        upsert=True
    )

def get_known_groups():
    """Возвращает список всех зарегистрированных групп"""
    pipeline = [
        {"$group": {"_id": "$chat_id", "title": {"$first": "$title"}}},
        {"$project": {"chat_id": "$_id", "title": 1, "_id": 0}}
    ]
    return list(history_col.aggregate(pipeline))

def get_group_by_id(chat_id):
    """Поиск группы по её ID"""
    try:
        return history_col.find_one({'chat_id': int(chat_id)})
    except (ValueError, TypeError):
        return None

def save_history_record(collection_data):
    """Сохраняет результаты, используя только username и ID (без имен)"""
    # Фильтруем участников, оставляя только ID и Username
    clean_participants = []
    for p in collection_data.get('participants', []):
        clean_participants.append({
            'id': p.get('id'), # в твоем коде используется ключ 'id'
            'username': p.get('username')
        })

    record = {
        'chat_id': collection_data['chat_id'],
        'title': collection_data.get('title', 'Сбор'),
        'date': datetime.datetime.now(),
        'participants': clean_participants,
        'count': len(clean_participants)
    }
    
    if record['count'] > 0:
        history_col.insert_one(record)
        save_known_group(record['chat_id'], record['title'])

def load_history_for_chat(chat_id, begin_ts=None, end_ts=None):
    """Загружает историю сборов за указанный период"""
    query = {'chat_id': chat_id}
    if begin_ts and end_ts:
        query['date'] = {
            '$gte': datetime.datetime.fromtimestamp(begin_ts),
            '$lte': datetime.datetime.fromtimestamp(end_ts)
        }
    return list(history_col.find(query).sort('date', -1))

def delete_history_records(chat_id, period_type, *args):
    """*args предотвращает ошибку '3 arguments given'"""
    now = datetime.datetime.now()
    query = {'chat_id': int(chat_id)}
    
    if period_type == 'today':
        query['date'] = {'$gte': now.replace(hour=0, minute=0, second=0)}
    elif period_type == '7days':
        query['date'] = {'$gte': now - datetime.timedelta(days=7)}
    
    history_col.delete_many(query)

def clear_all_history():
    """Полная очистка всей коллекции истории (админ-функция)"""
    history_col.delete_many({})

def save_user_id(chat_id, user_id, username, first_name):
    """Обновляет данные пользователя и время его последней активности"""
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
    """Добавляет пользователя по username (для команды /add)"""
    username = username.replace('@', '')
    result = members_col.update_one(
        {'chat_id': chat_id, 'username': username},
        {'$set': {'last_seen': datetime.datetime.now()}},
        upsert=True
    )
    return result.acknowledged

def get_all_members_ids(chat_id):
    """Получает список всех ID участников группы"""
    members = members_col.find({'chat_id': chat_id}, {'user_id': 1})
    return [m['user_id'] for m in members]