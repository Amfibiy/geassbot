from .clean_functions import (
    handle_clean,
    handle_clean_group_callback,
    handle_clean_action_callback,
    handle_confirm_callback
)

def register_clean_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def handle_clean_command(message):
        # Работает только в ЛС
        if message.chat.type == 'private':
            handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions)
        else:
            bot.reply_to(message, "⚠️ Очистка истории доступна только в ЛС.")

    # Выбор группы
    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_group_'))
    def clean_group_cb(call):
        handle_clean_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)
    
    # Выбор периода (Сегодня/Вчера/Все)
    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_action_'))
    def clean_action_cb(call):
        handle_clean_action_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)
    
    # Кнопка "Да, удалить" (Подтверждение)
    @bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_clean_'))
    def confirm_cb(call):
        handle_confirm_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)