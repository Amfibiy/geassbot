import time
import sys
import logging
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin, get_thread_id
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', mode='a')
    ]
)

def log_info(msg):
    logging.info(msg)

def get_mention_string(chunk):
    """Создает строку из невидимых упоминаний для пачки пользователей"""
    invisible_char = "​"  # Нулевой символ
    return "".join([f"[{invisible_char}](tg://user?id={uid})" for uid in chunk])

def send_silent_mentions(bot, chat_id, thread_id, overflow_chunks):
    """Отправляет и удаляет сообщения только для тех, кто не поместился в основные"""
    for chunk in overflow_chunks:
        try:
            mentions = get_mention_string(chunk)
            msg = bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=f"Уведомление {mentions}",
                parse_mode="Markdown"
            )
            bot.delete_message(chat_id, msg.message_id)
            time.sleep(1)
        except Exception as e:
            log_info(f"Ошибка при тихом упоминании: {e}")

def create_counter_message(quantity, left):
    text = f"📊 **Сбор участников!**\n👥 Уже присоединилось: {quantity}\n⏱ Осталось времени: {int(left // 60)} мин {int(left % 60)} сек"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Присоединиться", callback_data="join_collection"))
    return text, kb

def update_collection_counter(chat_id, collect, bot, current_time):
    passed = current_time - collect['start_time']
    left = max(0, COLLECTION_DURATION - passed)
    quantity = len(collect['participants'])
    new_text, new_keyboard = create_counter_message(quantity, left)
    
    try:
        if collect.get('counter_message_id'):
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=collect['counter_message_id'],
                text=new_text,
                reply_markup=new_keyboard,
                parse_mode="Markdown"
            )
    except Exception:
        pass # Игнорируем ошибку, если текст не изменился

def handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions):
    """Логика обработки нажатия кнопки 'Присоединиться'"""
    chat_id = call.message.chat.id
    storage = active_collections if chat_id in active_collections else test_collection if chat_id in test_collection else None
    
    if not storage or chat_id not in storage:
        bot.answer_callback_query(call.id, "❌ Сбор завершен или не активен", show_alert=True)
        return

    collection = storage[chat_id]
    user = call.from_user

    # Проверка на повторное нажатие
    if any(p['id'] == user.id for p in collection['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в списке!")
        return
    
    # Добавляем пользователя
    collection['participants'].append({
        'id': user.id,
        'name': user.first_name,
        'username': user.username,
        'join_time': time.time()
    })

    bot.answer_callback_query(call.id, "🎉 Вы успешно присоединились!")
    update_collection_counter(chat_id, collection, bot, time.time())

def finish_collection(chat_id, bot, storage, is_test=False):
    if chat_id not in storage:
        return
    collect = storage.pop(chat_id)
    quantity = len(collect['participants'])
    
    text = f"🛑 **Сбор завершен!**\n👥 Итого участников: {quantity}"
    try:
        if collect.get('counter_message_id'):
            bot.edit_message_text(chat_id=chat_id, message_id=collect['counter_message_id'], text=text, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, text, parse_mode="Markdown")
        
    if not is_test:
        save_history_record({
            'chat_id': chat_id,
            'type': 'collection',
            'participants': collect['participants'],
            'start_time': collect['start_time'],
            'end_time': time.time()
        })

def run_collection_timer(chat_id, bot, storage, duration, is_test):
    end_time = time.time() + duration
    while time.time() < end_time and chat_id in storage:
        time.sleep(10) # Обновляем счетчик каждые 10 секунд (можно подстроить)
        if chat_id in storage:
            update_collection_counter(chat_id, storage[chat_id], bot, time.time())
            
    if chat_id in storage:
        finish_collection(chat_id, bot, storage, is_test)

def start_collection_base(message, bot, active_collections, test_collection, is_test=False):
    chat_id = message.chat.id
    if chat_id in active_collections or chat_id in test_collection:
        bot.reply_to(message, "⚠️ Сбор уже идет в этой группе!")
        return
        
    storage = test_collection if is_test else active_collections
    text, kb = create_counter_message(0, COLLECTION_DURATION)
    msg = bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
    
    storage[chat_id] = {
        'start_time': time.time(),
        'participants': [],
        'counter_message_id': msg.message_id
    }
    
    # Запускаем фоновый таймер
    threading.Thread(target=run_collection_timer, args=(chat_id, bot, storage, COLLECTION_DURATION, is_test)).start()

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    start_collection_base(message, bot, active_collections, test_collection, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    start_collection_base(message, bot, active_collections, test_collection, is_test=True)

def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = message.chat.id
    if chat_id in active_collections:
        finish_collection(chat_id, bot, active_collections, is_test=False)
    elif chat_id in test_collection:
        finish_collection(chat_id, bot, test_collection, is_test=True)
    else:
        bot.reply_to(message, "⚠️ Нет активных сборов для остановки.")