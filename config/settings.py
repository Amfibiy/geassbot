import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

HISTORY_DAYS = int(os.getenv('HISTORY_DAYS', 90))
MAX_UPDATES_LIMIT = int(os.getenv('MAX_UPDATES_LIMIT', 1000))
EMOJI_LIST = ["🔥", "⚔️", "🛡", "⚡️", "🌟", "💠", "🔱", "🎯", "🌪", "✨"]

MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGO_URL')