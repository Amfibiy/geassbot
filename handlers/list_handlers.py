from .list_functions import (
    show_participants_list,
    handle_period_callback
)
from utils.helpers import admin_only

def register_list_handlers(bot, active_collections, test_collection,
                           collection_history, known_groups, user_sessions):
    
    @bot.message_handler(commands=['list'])
    @admin_only
    def handle_list(message):
        show_participants_list(message, bot, active_collections, test_collection,
                              collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('period_'))
    def handle_period_callback_handler(call):
        handle_period_callback(call, bot, active_collections, test_collection,
                              collection_history, known_groups, user_sessions)