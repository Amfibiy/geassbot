import time
from database.history import save_history
from utils.helpers import is_admin, get_thread_id

# Вместо отдельных файлов - импортируем из одного модуля
from .collection_functions import (
    start_collection,
    start_test_collection,
    stop_collection,
    handle_join
)

def register_collection_handlers(bot, active_collections, test_collection, 
                                  collection_history, known_groups, user_sessions):
    
    @bot.message_handler(commands=['start_collect'])
    def handle_start(message):
        start_collection(message, bot, active_collections, test_collection,
                        collection_history, known_groups, user_sessions)
    
    @bot.message_handler(commands=['test'])
    def handle_test(message):
        start_test_collection(message, bot, active_collections, test_collection,
                             collection_history, known_groups, user_sessions)
    
    @bot.message_handler(commands=['stop'])
    def handle_stop(message):
        stop_collection(message, bot, active_collections, test_collection,
                       collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data == "join")
    def handle_join_button(call):
        handle_join(call, bot, active_collections, test_collection,
                   collection_history, known_groups, user_sessions)