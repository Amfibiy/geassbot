from .list_functions import (
    show_participants_list,
    handle_list_group_callback,
    handle_period_callback
)

def register_list_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['list'])
    def handle_list(message):
        if message.chat.type in ['group', 'supergroup']:
            # Логика для группы: показываем участников с никами
            chat_id = message.chat.id
            col = active_collections.get(chat_id) or test_collection.get(chat_id)
            if col:
                count = len(col['participants'])
                if count == 0:
                    bot.reply_to(message, "📋 **Статус сбора:**\nПока никто не присоединился.", parse_mode="Markdown")
                else:
                    lines = [f"📋 **Статус сбора (участников: {count}):**\n"]
                    for i, p in enumerate(col['participants'], 1):
                        username = f" (@{p['username']})" if p.get('username') else ""
                        lines.append(f"{i}. {p['name']}{username}")
                    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")
            else:
                bot.reply_to(message, "📭 В данный момент активных сборов нет.")
        else:
            # Логика для ЛС
            show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_group_'))
    def handle_list_group_callback_handler(call):
        handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('period_'))
    def handle_period_callback_handler(call):
        handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)