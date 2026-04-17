import time
import math
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.mongo import (
    get_all_members_ids, get_combined_settings, save_known_group, 
    save_user_id, save_history_record, get_group_member_count
)
from utils.messages import (
    START_MESSAGES_MANDATORY, TEST_MESSAGES, COLLECT_BODY_ACTIVE, 
    COLLECT_ALREADY_RUNNING, TEST_BODY_ACTIVE
)
from config.settings import EMOJI_LIST

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    admin_id = message.from_user.id
    m_count = bot.get_chat_member_count(chat_id)
    save_known_group(chat_id, message.chat.title, member_count=m_count)
    save_user_id(chat_id, admin_id, message.from_user.username)
    
    configs = get_combined_settings(chat_id, admin_id)
    duration_sec = configs['duration']

    if chat_id in collection_dict:
        return

    member_ids = get_all_members_ids(chat_id)
    templates = TEST_MESSAGES if is_test else START_MESSAGES_MANDATORY
    num_templates = len(templates)

    if member_ids:
        chunk_size = math.ceil(len(member_ids) / num_templates)
        chunks = [member_ids[i:i + chunk_size] for i in range(0, len(member_ids), chunk_size)]
    else:
        chunks = []

    for i in range(num_templates):
        current_chunk = chunks[i] if i < len(chunks) else []

        emoji_tags = " ".join([
            f'<a href="tg://user?id={m_id}">{random.choice(EMOJI_LIST)}</a>' 
            for m_id in current_chunk
        ])
        
        welcome_text = templates[i].format(
            duration=duration_sec // 60,
            tags=f"\n{emoji_tags}\n" if emoji_tags else ""
        )
        bot.send_message(chat_id, welcome_text, parse_mode="HTML")
        time.sleep(0.3) 

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Присоединиться (0)", callback_data="join_collection"))
    
    body_template = TEST_BODY_ACTIVE if is_test else COLLECT_BODY_ACTIVE
    sent_msg = bot.send_message(
        chat_id, 
        body_template.format(remaining=f"{duration_sec // 60}:00", tags=""), 
        reply_markup=markup, 
        parse_mode="HTML"
    )
    
    collection_dict[chat_id] = {
        'participants': [],
        'start_time': time.time(),
        'duration': duration_sec,
        'main_message_id': sent_msg.message_id,
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

def handle_join(call, bot, active_collections, test_collection):
    chat_id = call.message.chat.id
    col = active_collections.get(chat_id) or test_collection.get(chat_id)
    
    if not col:
        bot.answer_callback_query(call.id, "❌ Сбор завершен.")
        return

    user = call.from_user
    if any(p['id'] == user.id for p in col['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в деле!")
        return

    col['participants'].append({'id': user.id, 'username': user.username, 'name': user.first_name})
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ Присоединиться ({len(col['participants'])})", callback_data="join_collection"))
    
    try:
        bot.edit_message_reply_markup(
        chat_id=chat_id, 
        message_id=col['main_message_id'], 
        reply_markup=markup
        )
        bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, добавлен!")
    except Exception:
        bot.answer_callback_query(call.id, "✅ Успешно!")

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