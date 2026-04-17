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
    """Полная функция запуска сбора с регистрацией инициатора"""
    chat_id = message.chat.id
    admin_id = message.from_user.id
    admin_username = message.from_user.username
    
    save_known_group(chat_id, message.chat.title)
    save_user_id(chat_id, admin_id, admin_username)
    
    configs = get_combined_settings(chat_id, admin_id)
    limit_min = configs['duration'] // 60

    if chat_id in collection_dict:
        bot.reply_to(message, "⚠️ Сбор уже запущен!")
        return

    member_ids = get_all_members_ids(chat_id)
    all_tags = "".join([f'<a href="tg://user?id={m_id}">\u2060</a>' for m_id in member_ids])

    if is_test:
        bot.send_message(chat_id, TEST_HEADER.format(duration=limit_min, tags=all_tags), parse_mode="HTML")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"✅ Присоединиться (0)", callback_data="join_collection"))
        
        sent_msg = bot.send_message(chat_id, TEST_BODY_ACTIVE, reply_markup=markup, parse_mode="HTML")
        
        collection_dict[chat_id] = {
            'participants': [],
            'start_time': time.time(),
            'duration': configs['duration'],
            'main_message_id': sent_msg.message_id,
            'title': "Тестовый сбор"
        }
    else:
        random_start_msg = random.choice(START_MESSAGES_MANDATORY)
        bot.send_message(chat_id, random_start_msg.format(duration=limit_min, tags=all_tags), parse_mode="HTML")
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"✅ Присоединиться (0)", callback_data="join_collection"))
        
        sent_msg = bot.send_message(chat_id, COLLECT_BODY_ACTIVE, reply_markup=markup, parse_mode="HTML")
        
        collection_dict[chat_id] = {
            'participants': [],
            'start_time': time.time(),
            'duration': configs['duration'],
            'main_message_id': sent_msg.message_id,
            'title': "Обычный сбор"
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