from .list_functions import (
    show_participants_list,
    handle_list_group_callback,
    handle_period_callback
)
from utils.helpers import is_admin
from .clean_functions import handle_cancel_clean

def register_list_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['list'])
    def handle_list(message):
        chat_id = message.chat.id
        
        # Если это ГРУППА: показываем только статус текущего сбора (без кнопок)
        if message.chat.type in ["group", "supergroup"]:
            if chat_id in active_collections:
                coll = active_collections[chat_id]
                found = len(coll.get('found_ids', []))
                total = coll.get('total_count', 0)
                bot.send_message(chat_id, f"📊 *Текущий сбор:*\nСобрано: {found} из {total}", parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ Сейчас нет активного сбора.")
            return

        # Если это ЛС: запускаем твою стандартную функцию с периодами
        show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions)

    # Колбэки оставляем как были
    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_group_'))
    def handle_list_group_callback_handler(call):
        handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('period_'))
    def handle_period_callback_handler(call):
        handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_clean")
    def cancel_cb(call):
        handle_cancel_clean(call, bot)