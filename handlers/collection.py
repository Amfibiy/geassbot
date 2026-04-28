from .collection_functions import (
    start_collection,
    start_test_collection,
    stop_collection,
    handle_join
)
from utils.helpers import is_admin

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