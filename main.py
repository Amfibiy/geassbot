def check_all_groups_at_startup():
    """Проверяет группы при запуске"""
    print("🔍 Проверка групп при запуске...")
    try:
        # ИСПРАВЛЕНО: добавил callback_query
        updates = bot.get_updates(offset=0, allowed_updates=['message', 'callback_query'], limit=1000)
        found_groups = set()
        max_update_id = 0
        me = bot.get_me()
        
        for update in updates:
            max_update_id = max(max_update_id, update.update_id)
            if update.message and update.message.chat.type in ['group', 'supergroup']:
                chat = update.message.chat
                chat_id = chat.id
                try:
                    bot_member = bot.get_chat_member(chat_id, me.id)
                    if bot_member.status in ['administrator', 'creator']:
                        found_groups.add(chat_id)
                        print(f"✅ Бот найден в группе: {chat.title} (ID: {chat_id})")
                except:
                    pass
        
        global known_groups
        old_count = len(known_groups)
        known_groups.update(found_groups)
        
        if len(known_groups) > old_count:
            save_known_groups(known_groups)
            print(f"📋 Добавлено {len(known_groups) - old_count} новых групп")
        print(f"📋 Всего известно: {len(known_groups)} групп")
        
        from config.settings import OFFSET_FILE
        if max_update_id > 0:
            with open(OFFSET_FILE, 'w') as f:
                f.write(str(max_update_id + 1))
                
    except Exception as e:
        print(f"❌ Ошибка при проверке групп: {e}")