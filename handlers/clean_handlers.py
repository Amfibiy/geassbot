from .clean_functions import (
    handle_clean,
    handle_clean_group_callback,
    handle_clean_action_callback,
    handle_confirm_callback
)

def register_clean_handlers(bot, active_collections, test_collection,
                            collection_history, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def handle_clean_command(message):
        handle_clean(message, bot, active_collections, test_collection,
                    collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_group_'))
    def handle_clean_group_callback_handler(call):
        handle_clean_group_callback(call, bot, active_collections, test_collection,
                                   collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_action_'))
    def handle_clean_action_callback_handler(call):
        handle_clean_action_callback(call, bot, active_collections, test_collection,
                                    collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
    def handle_confirm_callback_handler(call):
        handle_confirm_callback(call, bot, active_collections, test_collection,
                               collection_history, known_groups, user_sessions)