import json
import os
from config.settings import KNOWN_GROUPS_FILE

def load_known_groups():
    """Загружает список известных групп из файла"""
    try:
        if os.path.exists(KNOWN_GROUPS_FILE):
            with open(KNOWN_GROUPS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data)
        return set()
    except Exception as e:
        print(f"❌ Ошибка загрузки групп: {e}")
        return set()

def save_known_groups(known_groups):
    """Сохраняет список известных групп в файл"""
    try:
        with open(KNOWN_GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(known_groups), f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения групп: {e}")
        return False

def remove_inaccessible_groups(known_groups, bot):
    """Удаляет группы, где бот больше не админ"""
    from utils.helpers import is_bot_admin
    
    groups_to_remove = []
    for chat_id in list(known_groups):
        if not is_bot_admin(chat_id, bot):
            groups_to_remove.append(chat_id)
            print(f"❌ Группа {chat_id} недоступна")
    
    for chat_id in groups_to_remove:
        known_groups.remove(chat_id)
    
    return known_groups, len(groups_to_remove)