from database.mongo import save_known_group, save_user_id

def handle_group_message(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = message.chat.id
    if chat_id not in known_groups:
        known_groups.add(chat_id)
        save_known_group(chat_id, message.chat.title or f"Группа {chat_id}")
    try:
        chat_id = message.chat.id
        if chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_group(chat_id, message.chat.title or f"Группа {chat_id}")
            print(f"📡 Новая группа зарегистрирована: {message.chat.title}", flush=True)

        # Сохраняем/обновляем юзера
        if not message.from_user.is_bot:
            save_user_id(
                chat_id=chat_id,
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
    except Exception as e:
        print(f"❌ Ошибка в handle_group_message: {e}")