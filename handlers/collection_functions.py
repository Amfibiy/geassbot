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

import time
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    admin_id = message.from_user.id
    if chat_id in collection_dict:
        bot.send_message(chat_id, COLLECT_ALREADY_RUNNING, parse_mode="HTML")
        return
    member_ids = get_all_members_ids(chat_id)

    bot_me = bot.get_me()
    if bot_me.id in member_ids:
        member_ids.remove(bot_me.id)

    m_count = len(member_ids)
    
    save_known_group(chat_id, message.chat.title, member_count=m_count)
    if not message.from_user.is_bot:
        save_user_id(chat_id, admin_id, message.from_user.username)

    configs = get_combined_settings(chat_id, admin_id)
    duration_sec = configs['duration']

    templates = TEST_MESSAGES if is_test else START_MESSAGES_MANDATORY
    chosen_template = random.choice(templates)
    tags_html = ""
    for uid in member_ids:
        tags_html += f'<a href="tg://user?id={uid}">\u200b</a>'

    text = chosen_template.format(
        duration=duration_sec // 60,
        tags=tags_html
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ Присоединиться (0)", callback_data="join_collection"))

    try:
        sent_msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
        
        collection_dict[chat_id] = {
            'main_message_id': sent_msg.message_id,
            'start_time': time.time(),
            'duration': duration_sec,
            'participants': [],  
            'admin_id': admin_id,
            'is_test': is_test
        }
    except Exception as e:
        print(f"❌ Ошибка при запуске сбора: {e}")
        bot.send_message(chat_id, "⚠️ Не удалось запустить сбор. Проверьте права бота.")

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