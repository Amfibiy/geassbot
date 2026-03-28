from .list_functions import (
    show_participants_list,
    handle_list_group_callback,
    handle_period_callback
)
from utils.helpers import is_admin

def register_list_handlers(bot, active_collections, test_collection,
                           collection_history, known_groups, user_sessions):
    
    @bot.message_handler(commands=['list'])
    def handle_list(message):
        if message.chat.type != "private":
            if not is_admin(message.chat.id, message.from_user.id):
                bot.reply_to(message, "❌ Только для администраторов группы")
                return
        show_participants_list(message, bot, active_collections, test_collection,
                              collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_group_'))
    def handle_list_group_callback_handler(call):
        handle_list_group_callback(call, bot, active_collections, test_collection,
                                   collection_history, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('period_'))
    def handle_period_callback_handler(call):
        handle_period_callback(call, bot, active_collections, test_collection,
                               collection_history, known_groups, user_sessions)