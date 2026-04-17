import time
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids,get_combined_settings,save_known_group,save_user_id
from utils.messages import (
    START_MESSAGES_MANDATORY, COLLECT_BODY_ACTIVE, 
    TEST_HEADER, TEST_BODY_ACTIVE
)

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    admin_id = message.from_user.id
    
    # Регистрация
    save_known_group(chat_id, message.chat.title)
    save_user_id(chat_id, admin_id, message.from_user.username)
    
    configs = get_combined_settings(chat_id, admin_id)
    duration_sec = configs['duration']
    
    # Если сбор уже идет
    if chat_id in collection_dict:
        col = collection_dict[chat_id]
        elapsed_sec = int(time.time() - col['start_time'])
        rem_sec = max(0, col['duration'] - elapsed_sec)
        
        rem_fmt = f"{rem_sec // 60}:{rem_sec % 60:02d}"
        
        status_text = COLLECT_ALREADY_RUNNING.format(
            count=len(col['participants']),
            elapsed=elapsed_sec // 60,
            remaining=rem_fmt
        )
        bot.reply_to(message, status_text, parse_mode="HTML")
        return

    member_ids = get_all_members_ids(chat_id)
    all_tags = "".join([f'<a href="tg://user?id={m_id}">\u2060</a>' for m_id in member_ids])

    # Выбираем случайное приветственное сообщение
    if is_test:
        welcome_text = TEST_HEADER.format(duration=duration_sec // 60, tags=all_tags)
    else:
        welcome_text = random.choice(START_MESSAGES_MANDATORY).format(duration=duration_sec // 60, tags=all_tags)

    bot.send_message(chat_id, welcome_text, parse_mode="HTML")

    # Создаем сообщение с кнопкой
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Присоединиться (0)", callback_data="join_collection"))
    
    # Начальный текст таймера
    rem_initial = f"{duration_sec // 60}:00"
    body_text = (TEST_BODY_ACTIVE if is_test else COLLECT_BODY_ACTIVE).format(remaining=rem_initial, tags=all_tags)
    
    sent_msg = bot.send_message(chat_id, body_text, reply_markup=markup, parse_mode="HTML")
    
    collection_dict[chat_id] = {
        'participants': [],
        'start_time': time.time(),
        'duration': duration_sec,
        'main_message_id': sent_msg.message_id,
        'tags': all_tags, # Сохраняем теги, чтобы не генерить их каждый раз
        'is_test': is_test
    }
def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = message.chat.id
    is_test = False
    col = active_collections.pop(chat_id, None)
    if not col:
        col = test_collection.pop(chat_id, None)
        is_test = True
    if not col:
        bot.reply_to(message, "❌ Нет активного сбора для остановки.")
        return

    quantity = len(col['participants'])
    final_text = f"""✅ *Сбор завершён!*
        
👥 Участников: {quantity}
⏰ Завершено досрочно
{'🎉 Спасибо!' if quantity > 0 else '😔 Никто не присоединился'}"""

    bot.send_message(chat_id, final_text, parse_mode="Markdown")
    
    if not is_test and len(col['participants']) > 0:
        save_history_record(col)

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if message.chat.type == 'private':
        bot.reply_to(message, "🏰 **В ЛС нельзя запустить сбор.**")
        return
    _start_generic_collection(message, bot, active_collections, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if message.chat.type == 'private':
        bot.reply_to(message, "🧪 **В ЛС нельзя запустить тест.**")
        return
    _start_generic_collection(message, bot, test_collection, is_test=True)

def handle_join(call, bot, collection_dict):
    chat_id = call.message.chat.id
    col = collection_dict.get(chat_id)
    
    if not col:
        bot.answer_callback_query(call.id, "❌ Сбор завершен или не найден.", show_alert=True)
        return

    user = call.from_user
    
    save_user_id(chat_id, user.id, user.username)

    if any(p.get('id') == user.id for p in col['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в списке участников!")
        return

    col['participants'].append({
        'id': user.id, 
        'username': user.username, 
        'name': user.first_name
    })
    
    count = len(col['participants'])
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ Присоединиться ({count})", callback_data="join_collection"))
    
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=col['main_message_id'],
            reply_markup=markup
        )
    except Exception as e:
        print(f"Ошибка обновления кнопок: {e}")

    bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, вы в деле!")

def stop_collection_automatically(chat_id, bot, coll_dict, is_test):
    col = coll_dict.pop(int(chat_id), None)
    if not col: return

    quantity = len(col['participants'])
    final_text = f"""✅ *Сбор завершён!*
        
👥 Участников: {quantity}
⏰ Время вышло
{'🎉 Спасибо!' if quantity > 0 else '😔 Никто не присоединился'}"""

    bot.send_message(chat_id, final_text, parse_mode="Markdown")
    
    if not is_test and quantity > 0:
        save_history_record(col)