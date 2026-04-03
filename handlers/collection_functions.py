import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids
from utils.messages import (
    START_MESSAGES, TEST_START_MSG, STOP_COLLECT_CONFIRM, 
    STOP_TEST_CONFIRM, COLLECT_ALREADY_RUNNING
)

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    
    # Защита от дублирования сбора с выводом подробной статистики
    if chat_id in collection_dict:
        col = collection_dict[chat_id]
        elapsed_sec = int(time.time() - col['start_time'])
        elapsed_mins = elapsed_sec // 60
        
        rem_sec = max(0, COLLECTION_DURATION - elapsed_sec)
        rem_mins = rem_sec // 60
        rem_secs = rem_sec % 60
        
        text = COLLECT_ALREADY_RUNNING.format(
            count=len(col['participants']),
            elapsed=elapsed_mins,
            remaining=f"{rem_mins:02d}:{rem_secs:02d}"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
        return

    # --- 1. ГОТОВИМ СКРЫТЫЕ ТЕГИ ---
    raw_members = get_all_members_ids(chat_id) or []
    valid_ids = []
    
    for m in raw_members:
        uid = m.get('user_id') if isinstance(m, dict) else m
        if uid and str(uid).isdigit():
            valid_ids.append(uid)

    chunk_size = 90
    chunks = [valid_ids[i:i + chunk_size] for i in range(0, len(valid_ids), chunk_size)]

    def get_hidden_tags(chunk_index):
        if chunk_index < len(chunks):
            return "".join([f"[\u200b](tg://user?id={uid})" for uid in chunks[chunk_index]])
        return ""

    # --- 2. ЗАПУСК УВЕДОМЛЕНИЙ ---
    duration_mins = COLLECTION_DURATION // 60

    if is_test:
        # Для теста: 1 информационное сообщение + 1 сообщение со счетчиком
        tags_0 = get_hidden_tags(0)
        admin_name = message.from_user.username or message.from_user.first_name
        msg1 = TEST_START_MSG.format(admin=admin_name)
        bot.send_message(chat_id, f"{msg1}{tags_0}", parse_mode="Markdown")
        time.sleep(0.5)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Стать первым участником", callback_data="join_collection"))
        tags_1 = get_hidden_tags(1)
        
        counter_text = (
            "📊 **Счётчики:**\n"
            "👥 Пока никто не присоединился\n"
            f"⏰ Осталось времени: {duration_mins:02d}:00\n\n"
            f"👇 Нажмите кнопку чтобы присоединиться{tags_1}"
        )
        counter_msg = bot.send_message(chat_id, counter_text, reply_markup=markup, parse_mode="Markdown")

    else:
        # Для обычного сбора: 4 анонса + 1 сообщение со счетчиком
        for i in range(4):
            tags = get_hidden_tags(i)
            bot.send_message(chat_id, f"{START_MESSAGES[i]}{tags}", parse_mode="Markdown")
            time.sleep(0.5)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Стать первым участником", callback_data="join_collection"))
        tags_final = get_hidden_tags(4)
        
        counter_text = (
            "📊 **Счётчики:**\n"
            "👥 Пока никто не присоединился\n"
            f"⏰ Осталось времени: {duration_mins:02d}:00\n\n"
            f"👇 Нажмите кнопку чтобы присоединиться{tags_final}"
        )
        counter_msg = bot.send_message(chat_id, counter_text, reply_markup=markup, parse_mode="Markdown")

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

    # Сохраняем историю только для реальных сборов
    if not is_test:
        save_history_record(collection)

    try:
        bot.edit_message_reply_markup(chat_id, collection['counter_message_id'], reply_markup=None)
    except:
        pass

    # Разные ответы для /stop в зависимости от типа сбора
    text = STOP_TEST_CONFIRM if is_test else STOP_COLLECT_CONFIRM
    bot.reply_to(message, text)


def end_collection_by_timeout(chat_id, bot, collection_dict):
    if chat_id in collection_dict:
        collection = collection_dict.pop(chat_id)
        is_test = collection.get('is_test', False)
        
        if not is_test:
            save_history_record(collection)

        try:
            bot.edit_message_reply_markup(chat_id, collection['counter_message_id'], reply_markup=None)
        except:
            pass

        count = len(collection['participants'])
        text = "✅ **Время тестового сбора вышло!**" if is_test else "✅ **Время сбора вышло!**"
        bot.send_message(chat_id, f"{text}\n👥 Итого собрано участников: {count}", parse_mode="Markdown")


# --- ОБРАБОТЧИКИ ---

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    _start_generic_collection(message, bot, active_collections, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    _start_generic_collection(message, bot, test_collection, is_test=True)

def handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions):
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