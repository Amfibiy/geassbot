import time
import random
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids
from utils.messages import START_MESSAGES, TEST_START_MSG, COLLECT_ALREADY_RUNNING

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    
    if chat_id in collection_dict:
        col = collection_dict[chat_id]
        elapsed = int(time.time() - col['start_time'])
        rem = max(0, COLLECTION_DURATION - elapsed)
        text = COLLECT_ALREADY_RUNNING.format(
            count=len(col['participants']),
            elapsed=elapsed // 60,
            remaining=f"{rem // 60:02d}:{rem % 60:02d}"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
        return

    member_ids = get_all_members_ids(chat_id)
    hidden_tags = "".join([f'<a href="tg://user?id={m_id}">\u200b</a>' for m_id in member_ids])

    base_text = TEST_START_MSG if is_test else random.choice(START_MESSAGES)
    full_text = f"{base_text}{hidden_tags}"

    msg = bot.send_message(chat_id, full_text, parse_mode="HTML")
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Присоединиться", callback_data="join_collection"))
    
    counter_msg = bot.send_message(chat_id, "📊 **Запуск счетчика...**", reply_markup=markup, parse_mode="Markdown")

    collection_dict[chat_id] = {
        'start_time': time.time(),
        'participants': [],
        'main_message_id': msg.message_id,
        'counter_message_id': counter_msg.message_id,
        'title': message.chat.title,
        'chat_id': chat_id
    }

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

# ЭТОЙ ФУНКЦИИ НЕ ХВАТАЛО:
def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = message.chat.id
    is_test = False
    col = active_collections.pop(chat_id, None)
    
    if not col:
        col = test_collection.pop(chat_id, None)
        is_test = True

    if col:
        if not is_test:
            save_history_record(col)
        
        text = "🏁 **Сбор остановлен вручную!**"
        bot.send_message(chat_id, f"{text}\n👥 Собрано участников: {len(col['participants'])}", parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Нет активных сборов для остановки.")

# ЭТОЙ ФУНКЦИИ ТОЖЕ МОГЛО НЕ ХВАТАТЬ:
def handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = call.message.chat.id
    col = active_collections.get(chat_id) or test_collection.get(chat_id)

    if not col:
        bot.answer_callback_query(call.id, "❌ Сбор уже завершен.", show_alert=True)
        return

    user = call.from_user
    if any(p['id'] == user.id for p in col['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в списке!")
        return

    col['participants'].append({'id': user.id, 'name': user.first_name, 'username': user.username})
    bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, вы в деле!")

def stop_collection_automatically(chat_id, bot, collection_dict, is_test):
    col = collection_dict.pop(chat_id, None)
    if col:
        if not is_test:
            save_history_record(col)
        text = "🏁 **Сбор завершен!**"
        bot.send_message(chat_id, f"{text}\n👥 Итого собрано: {len(col['participants'])}", parse_mode="Markdown")