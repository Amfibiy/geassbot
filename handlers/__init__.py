from .commands import register_commands
from .collection import register_collection_handlers
from .list_handlers import register_list_handlers
from .clean_handlers import register_clean_handlers
from .callbacks import register_callbacks

def register_all_handlers(bot, active_collections, test_collection, 
                         collection_history, known_groups, user_sessions):
    register_commands(bot)
    register_collection_handlers(bot, active_collections, test_collection, 
                                collection_history, known_groups, user_sessions)
    register_list_handlers(bot, active_collections, test_collection, 
                          collection_history, known_groups, user_sessions)
    register_clean_handlers(bot, active_collections, test_collection, 
                           collection_history, known_groups, user_sessions)
    register_callbacks(bot, active_collections, test_collection, 
                      collection_history, known_groups, user_sessions)