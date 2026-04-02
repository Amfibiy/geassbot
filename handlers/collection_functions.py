import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    if chat_id in collection_dict:
        bot.reply_to(message, "⚠️ Сбор уже идет!")
        return

    # --- 1. ГОТОВИМ СКРЫТЫЕ ТЕГИ ---
    raw_members = get_all_members_ids(chat_id) or []
    valid_ids = []
    
    for m in raw_members:
        # Извлекаем ID (защита от разного формата данных в базе)
        uid = m.get('user_id') if isinstance(m, dict) else m
        # Берем только числовые ID (игнорируем ручные добавления manual_...)
        if uid and str(uid).isdigit():
            valid_ids.append(uid)

    # Дробим список на чанки по 90 человек
    chunk_size = 90
    chunks = [valid_ids[i:i + chunk_size] for i in range(0, len(valid_ids), chunk_size)]

    def get_hidden_tags(chunk_index):
        """Возвращает строку с невидимыми упоминаниями для конкретного сообщения"""
        if chunk_index < len(chunks):
            # [\u200b] - невидимый пробел. tg://user?id= - ссылка на профиль
            return "".join([f"[\u200b](tg://user?id={uid})" for uid in chunks[chunk_index]])
        return ""

    # --- 2. ЗАПУСК УВЕДОМЛЕНИЙ (СТАРЫЕ СООБЩЕНИЯ) ---
    
    # 1. Сообщение о начале (индекс чанка 0)
    tags_0 = get_hidden_tags(0)
    bot.send_message(chat_id, f"🚀 **Сбор участников начался!**{tags_0}", parse_mode="Markdown")

    notifications_count = 2 if is_test else 5

    # 2. Промежуточные уведомления (индексы чанков от 1 до n-1)
    for i in range(1, notifications_count):
        tags_i = get_hidden_tags(i)
        # Parse mode нужен обязательно, чтобы невидимые ссылки сработали
        bot.send_message(chat_id, f"🔔 Внимание! Идет сбор участников ({i}/{notifications_count}){tags_i}", parse_mode="Markdown")
        time.sleep(1)

    # 3. Последнее уведомление с кнопкой (индекс чанка = notifications_count)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Присоединиться", callback_data="join_collection"))
    
    tags_final = get_hidden_tags(notifications_count)
    
    counter_msg = bot.send_message(
        chat_id, 
        f"👥 **Уведомление {notifications_count}/{notifications_count}**\n\nСобрано: 0\nОсталось времени: {COLLECTION_DURATION // 60}:00{tags_final}", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

    # --- 3. ЗАПИСЬ В ПАМЯТЬ И ТАЙМЕР ---
    collection_dict[chat_id] = {
        'chat_id': chat_id,
        'title': message.chat.title or "Группа",
        'start_time': time.time(),
        'participants': [],
        'counter_message_id': counter_msg.message_id,
        'is_test': is_test
    }

    threading.Timer(COLLECTION_DURATION, end_collection_by_timeout, args=[chat_id, bot, collection_dict]).start()

# --- ФУНКЦИИ ОСТАНОВКИ ---

def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = message.chat.id
    is_test = False
    
    collection = active_collections.pop(chat_id, None)
    if not collection:
        collection = test_collection.pop(chat_id, None)
        is_test = True

    if not collection:
        bot.reply_to(message, "⚠️ Нет активного сбора для остановки.")
        return

    # Сохраняем в историю (если не тест)
    if not is_test:
        save_history_record(collection)

    try:
        bot.edit_message_reply_markup(chat_id, collection['counter_message_id'], reply_markup=None)
    except:
        pass

    count = len(collection['participants'])
    text = "🛑 **Тестовый сбор досрочно завершен!**" if is_test else "🛑 **Сбор досрочно завершен!**"
    bot.send_message(chat_id, f"{text}\n👥 Итого собрано участников: {count}", parse_mode="Markdown")


def end_collection_by_timeout(chat_id, bot, collection_dict):
    if chat_id in collection_dict:
        collection = collection_dict.pop(chat_id)
        is_test = collection.get('is_test', False)
        
        # Сохраняем в историю
        if not is_test:
            save_history_record(collection)

        try:
            bot.edit_message_reply_markup(chat_id, collection['counter_message_id'], reply_markup=None)
        except:
            pass

        count = len(collection['participants'])
        text = "✅ **Время тестового сбора вышло!**" if is_test else "✅ **Время сбора вышло!**"
        bot.send_message(chat_id, f"{text}\n👥 Итого собрано участников: {count}", parse_mode="Markdown")

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    _start_generic_collection(message, bot, active_collections, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    _start_generic_collection(message, bot, test_collection, is_test=True)

def handle_join(call, bot, active_collections, test_collection):
    chat_id = call.message.chat.id
    collection = active_collections.get(chat_id) or test_collection.get(chat_id)

    if not collection:
        bot.answer_callback_query(call.id, "Сбор уже завершен или не начинался.", show_alert=True)
        return

    user_id = call.from_user.id
    if any(p['id'] == user_id for p in collection['participants']):
        bot.answer_callback_query(call.id, "Вы уже присоединились!", show_alert=True)
        return

    collection['participants'].append({
        'id': user_id,
        'username': call.from_user.username,
        'name': call.from_user.first_name
    })

    bot.answer_callback_query(call.id, "Вы успешно присоединились!")