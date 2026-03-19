from .callback_functions import (
    handle_my_chat_member,
    handle_group_message,
    handle_private_text
)

def register_callbacks(bot, active_collections, test_collection,
                       collection_history, known_groups, user_sessions):
    
    @bot.my_chat_member_handler()
    def handle_my_chat_member_handler(update):
        handle_my_chat_member(update, bot, active_collections, test_collection,
                             collection_history, known_groups, user_sessions)
    
    @bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
    def handle_group_message_handler(message):
        handle_group_message(message, bot, active_collections, test_collection,
                           collection_history, known_groups, user_sessions)
    
    @bot.message_handler(func=lambda message: message.chat.type == "private")
    def handle_private_text_handler(message):
        handle_private_text(message, bot, active_collections, test_collection,
                          collection_history, known_groups, user_sessions)