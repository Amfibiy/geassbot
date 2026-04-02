import time
from database.history import save_history
from utils.helpers import is_admin, get_thread_id

def register_collection_handlers(bot, active_collections, test_collection, 
                                  collection_history, known_groups, user_sessions):
    
    @bot.message_handler(commands=['start_collect'])
    def handle_start(message):
        from .start_collection_logic import start_collection
        start_collection(message, bot, active_collections, test_collection,
                        collection_history, known_groups, user_sessions)
    
    @bot.message_handler(commands=['test'])
    def handle_test(message):
        from .test_collection_logic import start_test_collection
        start_test_collection(message, bot, active_collections, test_collection,
                             collection_history, known_groups, user_sessions)
    
    @bot.message_handler(commands=['stop'])
    def handle_stop(message):
        from .stop_collection_logic import stop_collection
        stop_collection(message, bot, active_collections, test_collection,
                       collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data == "join")
    def handle_join_button(call):
        from .join_logic import handle_join
        handle_join(call, bot, active_collections, test_collection,
                   collection_history, known_groups, user_sessions)