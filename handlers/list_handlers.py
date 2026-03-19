def register_list_handlers(bot, active_collections, test_collection,
                           collection_history, known_groups, user_sessions):
    
    @bot.message_handler(commands=['list'])
    def handle_list(message):
        from .list_logic import show_participants_list
        show_participants_list(message, bot, active_collections, test_collection,
                              collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('period_'))
    def handle_period_callback(call):
        from .period_logic import handle_period_callback
        handle_period_callback(call, bot, active_collections, test_collection,
                              collection_history, known_groups, user_sessions)