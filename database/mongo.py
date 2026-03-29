import os
import time
import datetime
from pymongo import MongoClient
import telebot # Убедись, что этот импорт есть в начале файла
import logging

MONGO_URL = os.getenv('MONGO_URI') or os.getenv('MONGO_URL')
client = MongoClient(MONGO_URL)
db = client['geassbot_db']

members_col = db['chat_members']       
history_col = db['collection_history'] 
groups_col = db['known_groups']        
def get_known_groups_for_admin(admin_id, bot, known_groups):
    """
    Возвращает словарь {chat_id: chat_title} для всех групп из known_groups,
    в которых пользователь с admin_id является администратором или создателем.
    """
    admin_groups = {}
    if not known_groups:
        return admin_groups
        
    for g_id in list(known_groups): # Используем list() для безопасной итерации
        try:
            member = bot.get_chat_member(g_id, admin_id)
            if member.status in ['creator', 'administrator']:
                chat = bot.get_chat(g_id)
                admin_groups[str(g_id)] = chat.title or f"Группа {g_id}"
        except telebot.apihelper.ApiTelegramException as e:
            logging.info(f"Не удалось проверить админа в группе {g_id}: {e.description}")
        except Exception as e:
             logging.info(f"Ошибка при получении информации о группе {g_id}: {e}")
            
    return admin_groups
def save_known_group(chat_id, title):
    """Сохраняет или обновляет данные о группе"""
    groups_col.update_one(
        {'chat_id': chat_id},
        {'$set': {'title': title, 'active': True}},
        upsert=True
    )

def get_known_groups():
    """Получает список ID всех активных групп"""
    cursor = groups_col.find({'active': True})
    return {item['chat_id'] for item in cursor}

def mark_group_inactive(chat_id):
    """Помечает группу неактивной (если бота выгнали)"""
    groups_col.update_one({'chat_id': chat_id}, {'$set': {'active': False}})

def save_user_id(chat_id, user_id, username=None, first_name=None):
    """Добавляет пользователя в базу чата для тегов"""
    members_col.update_one(
        {'chat_id': chat_id},
        {'$addToSet': {'members': {
            'user_id': user_id, 
            'username': username, 
            'first_name': first_name
        }}},
        upsert=True
    )

def get_all_members_ids(chat_id):
    """Получает список всех ID участников в чате"""
    doc = members_col.find_one({'chat_id': chat_id})
    if doc and 'members' in doc:
        return [m['user_id'] for m in doc['members']]
    return []

def save_history_record(record_data):
    """Сохраняет результат одного сбора"""
    record_data['timestamp'] = time.time()
    history_col.insert_one(record_data)

def load_history_for_chat(chat_id, start_ts=0, end_ts=None):
    """Загружает историю за период для /list"""
    if end_ts is None:
        end_ts = time.time()
    query = {
        'chat_id': chat_id,
        'end_time': {'$gte': start_ts, '$lte': end_ts}
    }
    return list(history_col.find(query).sort('end_time', -1))

def delete_history_records(chat_id, start_ts, end_ts):
    """Удаляет записи за конкретный период (для /clean)"""
    query = {
        'chat_id': chat_id,
        'end_time': {'$gte': start_ts, '$lte': end_ts}
    }
    result = history_col.delete_many(query)
    return result.deleted_count

def clear_all_history(chat_id):
    """Полностью удаляет историю чата"""
    result = history_col.delete_many({'chat_id': chat_id})
    return result.deleted_count

def add_user_by_username(chat_id, username, first_name=None):
    if not username:
        return False
    username = username.lstrip('@')
    
    members_col.update_one(
        {'chat_id': chat_id},
        {'$addToSet': {'members': {
            'user_id': f"manual_{username}", # Префикс, чтобы отличить от реальных ID
            'username': username, 
            'first_name': first_name or username
        }}},
        upsert=True
    )
    return True