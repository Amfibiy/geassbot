import time
from .collection_functions import (
    start_collection,
    start_test_collection,
    stop_collection,
    handle_join
)
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin
from database.mongo import save_user_id

def register_collection_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    @bot.message_handler(commands=['collect'])
    def handle_start(message):
        if message.chat.type not in ['group', 'supergroup']: return
        if not is_admin(message.chat.id, message.from_user.id, bot):
            bot.reply_to(message, "❌ Только для администраторов")
            return
        start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.message_handler(commands=['test'])
    def handle_test(message):
        if message.chat.type not in ['group', 'supergroup']: return
        if not is_admin(message.chat.id, message.from_user.id, bot):
            bot.reply_to(message, "❌ Только для администраторов")
            return
        start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.message_handler(commands=['stop'])
    def handle_stop(message):
        if message.chat.type not in ['group', 'supergroup']: return
        if not is_admin(message.chat.id, message.from_user.id, bot):
            bot.reply_to(message, "❌ Только для администраторов")
            return
        stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data == 'join_collection')
    def join_callback(call):
        handle_join(call, bot, active_collections, test_collection)
    
    @bot.message_reaction_handler()
    def handle_reaction(message_reaction):
        chat_id = message_reaction.chat.id
        user_id = message_reaction.user.id

        target_col = active_collections.get(chat_id) or test_collection.get(chat_id)
    
        if not target_col or message_reaction.message_id != target_col.get('main_message_id'):
            return
        
        if not message_reaction.new_reaction:
            return

        user = message_reaction.user
        if not any(p['id'] == user_id for p in target_col['participants']):
            name = user.first_name or "Участник"
            target_col['participants'].append({
                'id': user_id,
                'name': name,
                'username': user.username
                })
            save_user_id(chat_id, user_id, user.username, name)

            count = len(target_col['participants'])
            elapsed = int(time.time() - target_col['start_time'])
            rem = max(0, target_col['duration'] - elapsed)
            remaining_str = f"{rem // 60:02d}:{rem % 60:02d}"

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(f"✅ Присоединиться ({count})", callback_data="join_collection"))

            try:
                new_text = target_col['main_template'].format(
                    duration=target_col['duration'] // 60,
                    remaining=remaining_str,
                    tags=target_col['remaining_tags'],
                    count=count
                )
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=target_col['main_message_id'],
                    text=new_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            except Exception:
                pass
            