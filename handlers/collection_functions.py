import time
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids,get_combined_settings
from utils.messages import START_MESSAGES, TEST_START_MSG, COLLECT_ALREADY_RUNNING

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    admin_id = message.from_user.id
    
    configs = get_combined_settings(chat_id, admin_id)
    current_limit = configs['duration']
    limit_min = current_limit // 60

    if chat_id in collection_dict:
        col = collection_dict[chat_id]
        elapsed = int(time.time() - col['start_time'])
        rem = max(0, col['duration'] - elapsed)
        
        status_text = COLLECT_ALREADY_RUNNING.format(
            remaining=f"{rem // 60:02d}:{rem % 60:02d}"
        )
        bot.reply_to(message, status_text, parse_mode="HTML")
        return

    member_ids = get_all_members_ids(chat_id)

    if is_test:
        text = TEST_START_MSG.text = TEST_START_MSG.format(duration=limit_min)
    else:
        raw_text = random.choice(START_MESSAGES)
        text = raw_text.format(duration=limit_min)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ Присоединиться", callback_data="join_collection"))

    sent_msg = bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

    collection_dict[chat_id] = {
        'chat_id': chat_id,              
        'main_message_id': sent_msg.message_id,
        'start_time': time.time(),
        'duration': current_limit,
        'participants': [],
        'all_known_ids': member_ids,
        'title': message.chat.title,
        'admin_id': admin_id,
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

def handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions):
    # Принудительно делаем chat_id числом
    chat_id = int(call.message.chat.id)
    col = active_collections.get(chat_id) or test_collection.get(chat_id)

    if not col:
        bot.answer_callback_query(call.id, "❌ Сбор уже завершен.", show_alert=True)
        return

    user = call.from_user
    # Проверка на наличие участника
    if any(p.get('id') == user.id for p in col['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в списке!")
        return

    # Добавляем данные, которые нужны для /list в mongo.py
    col['participants'].append({
        'id': user.id, 
        'username': user.username, 
        'name': user.first_name
    })
    
    count = len(col['participants'])
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ Присоединиться ({count})", callback_data="join_collection"))
    
    try:
        # Обновляем именно то сообщение, где кнопка
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=col['main_message_id'],
            reply_markup=markup
        )
    except Exception as e:
        print(f"Ошибка обновления кнопки: {e}")

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