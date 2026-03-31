from database.mongo import delete_history_records

def register_clean_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def handle_clean_command(message):
        if message.chat.type == 'private':
            count = delete_history_records(message.chat.id)
            bot.send_message(message.chat.id, f"🧹 **Очистка завершена**\nУдалено периодов: {count}", parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ Эту команду можно использовать только в личных сообщениях боту.")