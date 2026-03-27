from .collection_functions import (
    start_collection,
    start_test_collection,
    stop_collection,
    handle_join
)
from utils.helpers import admin_only

def register_collection_handlers(bot, active_collections, test_collection, 
                                  collection_history, known_groups, user_sessions):
    
    @bot.message_handler(commands=['start_collect'])
    @admin_only
    def handle_start(message):
        start_collection(message, bot, active_collections, test_collection,
                        collection_history, known_groups, user_sessions)
    
    @bot.message_handler(commands=['test'])
    @admin_only
    def handle_test(message):
        start_test_collection(message, bot, active_collections, test_collection,
                             collection_history, known_groups, user_sessions)
    
    @bot.message_handler(commands=['stop'])
    @admin_only
    def handle_stop(message):
        stop_collection(message, bot, active_collections, test_collection,
                       collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data == "join")
    def handle_join_button(call):
        handle_join(call, bot, active_collections, test_collection,
                   collection_history, known_groups, user_sessions)