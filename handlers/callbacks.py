def register_callbacks(bot, active_collections, test_collection,
                       collection_history, known_groups, user_sessions):
    
    @bot.my_chat_member_handler()
    def handle_my_chat_member(update):
        from .member_handler import handle_my_chat_member
        handle_my_chat_member(update, bot, active_collections, test_collection,
                             collection_history, known_groups, user_sessions)
    
    @bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
    def handle_group_message(message):
        from .group_handler import handle_group_message
        handle_group_message(message, bot, active_collections, test_collection,
                           collection_history, known_groups, user_sessions)
    
    @bot.message_handler(func=lambda message: message.chat.type == "private")
    def handle_private_text(message):
        from .private_handler import handle_private_text
        handle_private_text(message, bot, active_collections, test_collection,
                          collection_history, known_groups, user_sessions)