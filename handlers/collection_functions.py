import time
import math
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.mongo import get_all_members_ids, get_combined_settings, save_known_group, save_user_id,save_history_record
from utils.messages import (
    START_MESSAGES_MANDATORY, TEST_MESSAGES, COLLECT_BODY_ACTIVE, 
    COLLECT_ALREADY_RUNNING, TEST_BODY_ACTIVE
)

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    admin_id = message.from_user.id
    admin_username = message.from_user.username
    
    save_known_group(chat_id, message.chat.title)
    save_user_id(chat_id, admin_id, admin_username)
    
    configs = get_combined_settings(chat_id, admin_id)
    duration_sec = configs['duration']

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
    templates = TEST_MESSAGES if is_test else START_MESSAGES_MANDATORY
    num_templates = len(templates)
    
    if member_ids:
        chunk_size = math.ceil(len(member_ids) / num_templates)
        chunks = [member_ids[i:i + chunk_size] for i in range(0, len(member_ids), chunk_size)]
    else:
        chunks = []

    for i in range(num_templates):
        current_chunk = chunks[i] if i < len(chunks) else []
        tags_html = "".join([f'<a href="tg://user?id={m_id}">\u2060</a>' for m_id in current_chunk])
        
        welcome_text = templates[i].format(
            duration=duration_sec // 60,
            tags=tags_html
        )
        bot.send_message(chat_id, welcome_text, parse_mode="HTML")
        time.sleep(0.2) 

    extra_tags = ""
    if len(chunks) > num_templates:
        remaining_ids = [uid for chunk in chunks[num_templates:] for uid in chunk]
        extra_tags = "".join([f'<a href="tg://user?id={m_id}">\u2060</a>' for m_id in remaining_ids])

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Присоединиться (0)", callback_data="join_collection"))
    
    rem_initial = f"{duration_sec // 60}:00"
    body_template = TEST_BODY_ACTIVE if is_test else COLLECT_BODY_ACTIVE
    body_text = body_template.format(remaining=rem_initial, tags=extra_tags)
    
    sent_msg = bot.send_message(chat_id, body_text, reply_markup=markup, parse_mode="HTML")
    
    collection_dict[chat_id] = {
        'participants': [],
        'start_time': time.time(),
        'duration': duration_sec,
        'main_message_id': sent_msg.message_id,
        'tags': extra_tags, 
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
        bot.answer_callback_query(call.id, "❌ Сбор завершен или не найден.", show_alert=True)
        return

    user = call.from_user
    save_user_id(chat_id, user.id, user.username)

    if any(p.get('id') == user.id for p in col['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в списке!")
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
            message_id=call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, вы в деле!")
    except Exception:
        bot.answer_callback_query(call.id, "✅ Вы добавлены!")

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