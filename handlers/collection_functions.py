import time
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids
from utils.messages import START_MESSAGES, TEST_START_MSG, COLLECT_ALREADY_RUNNING

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = int(message.chat.id)
    
    if chat_id in collection_dict:
        col = collection_dict[chat_id]
        elapsed = int(time.time() - col['start_time'])
        rem = max(0, COLLECTION_DURATION - elapsed)
        
        status_text = COLLECT_ALREADY_RUNNING.format(
            count=len(col['participants']),
            elapsed=elapsed // 60,
            remaining=f"{rem // 60:02d}:{rem % 60:02d}"
        )
        bot.reply_to(message, status_text, parse_mode="HTML")
        return

    title = message.chat.title or f"Группа {chat_id}"
    admin_name = message.from_user.username or message.from_user.first_name

    text = TEST_START_MSG.format(admin=admin_name) if is_test else random.choice(START_MESSAGES)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Присоединиться (0)", callback_data="join_collection"))
    
    sent_msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
    
    collection_dict[chat_id] = {
        'chat_id': chat_id,
        'title': title,
        'main_message_id': sent_msg.message_id,
        'start_time': time.time(),
        'participants': [],
        'is_test': is_test
    }

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    _start_generic_collection(message, bot, active_collections, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    _start_generic_collection(message, bot, test_collection, is_test=True)

def handle_join(call, bot, active_collections, test_collection):
    chat_id = int(call.message.chat.id)
    col = active_collections.get(chat_id) or test_collection.get(chat_id)

    if not col:
        bot.answer_callback_query(call.id, "❌ Сбор уже завершен.", show_alert=True)
        return

    user = call.from_user
    
    # Проверка на наличие в списке (по ID или по нику)
    is_member = False
    for p in col['participants']:
        if p.get('id') == user.id:
            is_member = True
            break
        if p.get('username') and user.username and p['username'].lower() == user.username.lower():
            # Обогащаем "ручного" игрока его ID
            p['id'] = user.id
            p['name'] = user.first_name
            is_member = True
            break
            
    if is_member:
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
        bot.edit_message_reply_markup(chat_id, col['main_message_id'], reply_markup=markup)
    except Exception:
        pass

    bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, вы в деле!")

def stop_collection_automatically(chat_id, bot, coll_dict, is_test):
    c_id = int(chat_id)
    col = coll_dict.pop(c_id, None)
    if not col: return

    if not is_test:
        save_history_record(col)
        
    final_text = f"🏁 <b>Сбор завершен!</b>\nУчастников: {len(col['participants'])}"
    
    try:
        bot.edit_message_text(final_text, c_id, col['main_message_id'], parse_mode="HTML")
    except Exception:
        bot.send_message(c_id, final_text, parse_mode="HTML")

def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = int(message.chat.id)
    if chat_id in active_collections:
        stop_collection_automatically(chat_id, bot, active_collections, False)
        bot.reply_to(message, "🛑 Сбор остановлен.")
    elif chat_id in test_collection:
        stop_collection_automatically(chat_id, bot, test_collection, True)
        bot.reply_to(message, "🛑 Тест остановлен.")
    else:
        bot.reply_to(message, "❌ Нет активных сборов.")