import json
import os
import time
from config.settings import HISTORY_FILE, HISTORY_DAYS

def load_history():
    """Загружает историю сборов из файла"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        return {}
    except Exception as e:
        print(f"❌ Ошибка загрузки истории: {e}")
        return {}

def save_history(collection_history):
    """Сохраняет историю сборов в файл"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            data = {str(k): v for k, v in collection_history.items()}
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения истории: {e}")
        return False

def cleanup_old_records(chat_id, collection_history):
    """Удаляет старые записи из истории"""
    if chat_id not in collection_history:
        return collection_history
    
    current_time = time.time()
    max_age = HISTORY_DAYS * 86400
    new_records = []
    
    for record in collection_history[chat_id]:
        age = current_time - record['end_time']
        if age <= max_age:
            new_records.append(record)
    
    collection_history[chat_id] = new_records
    return collection_history