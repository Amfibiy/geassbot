from .collection_functions import (
    start_collection,
    start_test_collection,
    stop_collection,
    handle_join
)
from utils.helpers import is_admin

def register_collection_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['start_collect'])
    def handle_start(message):
        if not is_admin(message.chat.id, message.from_user.id):
            bot.reply_to(message, "❌ Только для администраторов группы")
            return
        start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.message_handler(commands=['test'])
    def handle_test(message):
        if not is_admin(message.chat.id, message.from_user.id):
            bot.reply_to(message, "❌ Только для администраторов группы")
            return
        start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.message_handler(commands=['stop'])
    def handle_stop(message):
        if not is_admin(message.chat.id, message.from_user.id):
            bot.reply_to(message, "❌ Только для администраторов группы")
            return
        stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data == "join")
    def handle_join_button(call):
        handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions)