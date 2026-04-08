from .clean_functions import (
    handle_clean, 
    handle_clean_group_id_input, 
    show_clean_actions,
    handle_confirm_clean,
    execute_delete
)

def register_clean_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def clean_command(message):
        if message.chat.type == 'private':
            handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions)
        else:
            bot.reply_to(message, "⚠️ Очистка истории доступна только в ЛС.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_group_'))
    def clean_group_cb(call):
        user_id = call.from_user.id
        chat_id = call.data.replace('clean_group_', '')
        show_clean_actions(call.message.chat.id, chat_id, "Выбранная группа", bot, user_sessions, user_id)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_action_'))
    def clean_action_cb(call):
        user_id = call.from_user.id
        action = call.data.replace('clean_action_', '')
        user_sessions[user_id]['clean_type'] = action
        handle_confirm_clean(call, bot, user_sessions)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "do_actual_clean")
    def do_clean_final_cb(call):
        execute_delete(call, bot, user_sessions)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_clean")
    def cancel_clean_cb(call):
        bot.edit_message_text("❌ Очистка отменена.", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    # Обработка текстового ввода (ID или номера действий)
    @bot.message_handler(func=lambda m: m.chat.type == 'private' and m.from_user.id in user_sessions)
    def handle_clean_text_input(message):
        user_id = message.from_user.id
        step = user_sessions[user_id].get('step')
        
        if step == "clean_wait_id":
            handle_clean_group_id_input(message, bot, user_sessions)
        elif step == "clean_wait_action":
            # Можно добавить обработку цифр 1-7, но пока оставим кнопки
            pass