import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Токен бота (обязательно)
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# Настройки
COLLECTION_DURATION = int(os.getenv('COLLECTION_DURATION', 1800))
HISTORY_DAYS = int(os.getenv('HISTORY_DAYS', 90))
MAX_UPDATES_LIMIT = int(os.getenv('MAX_UPDATES_LIMIT', 1000))

# Пути к файлам
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Создаём папку data если её нет
os.makedirs(DATA_DIR, exist_ok=True)

# Файлы данных
HISTORY_FILE = os.path.join(DATA_DIR, 'collection_history.json')
KNOWN_GROUPS_FILE = os.path.join(DATA_DIR, 'known_groups.json')
OFFSET_FILE = os.path.join(DATA_DIR, 'last_update_offset.txt')