from database.mongo import save_known_group, load_history_for_chat, save_user_id
from utils.validators import validate_date

def handle_my_chat_member(update, bot, active_collections, test_collection, known_groups, user_sessions):
    """Регистрация бота при добавлении в группу"""
    try:
        chat = update.chat
        if update.new_chat_member.status in ['member', 'administrator'] and chat.type in ['group', 'supergroup']:
            chat_id = chat.id
            chat_title = chat.title or f"Группа {chat_id}"
            if chat_id not in known_groups:
                known_groups.add(chat_id)
                save_known_group(chat_id, chat_title)
                print(f"✅ Группа добавлена в базу: {chat_title}")
    except Exception as e:
        print(f"❌ Ошибка в my_chat_member: {e}")

def handle_group_message(message, bot, active_collections, test_collection, known_groups, user_sessions):
    """Логирование активности в группах"""
    try:
        chat_id = message.chat.id
        if chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_group(chat_id, message.chat.title or f"Группа {chat_id}")

        if not message.from_user.is_bot:
            save_user_id(
                chat_id=chat_id,
                user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
    except Exception as e:
        print(f"❌ Ошибка в handle_group_message: {e}")

def handle_private_text(message, bot, active_collections, test_collection, known_groups, user_sessions):
    """Обработка текстовых ответов пользователя в ЛС"""
    try:
        user_id = message.from_user.id
        if user_id not in user_sessions:
            if message.text.lower() in ['привет', 'старт']:
                bot.reply_to(message, "👋 Используйте /list для просмотра истории.")
            return

        session = user_sessions[user_id]
        step = session.get('step')
        chat_id = session.get('chat_id')

        # Обработка ручного ввода диапазона дат
        if step == "input_date_range":
            text = message.text.strip()
            
            if text.lower() == '/cancel':
                session['step'] = "choice_period"
                from .list_functions import show_menu_periods_in_ls
                show_menu_periods_in_ls(message, session, bot)
                return

            if " - " in text:
                parts = text.split(" - ")
                if len(parts) == 2:
                    d1_str, d2_str = parts[0].strip(), parts[1].strip()
                    d1 = validate_date(d1_str)
                    d2 = validate_date(d2_str)
                    
                    if d1 and d2:
                        begin = d1.timestamp()
                        # Добавляем 23:59:59 к конечной дате
                        end = d2.timestamp() + 86399
                        
                        records = load_history_for_chat(chat_id, begin, end)
                        all_p = []
                        for r in records:
                            all_p.extend(r.get('participants', []))
                        
                        if not all_p:
                            bot.send_message(message.chat.id, f"📭 За период {d1_str} — {d2_str} данных нет.")
                        else:
                            from .list_functions import show_result_by_date
                            show_result_by_date(message, chat_id, all_p, d1_str, d2_str, session, bot)
                        
                        # После вывода результата возвращаем кнопки периодов
                        session['step'] = "choice_period"
                        from .list_functions import show_menu_periods_in_ls
                        show_menu_periods_in_ls(message, session, bot)
                    else:
                        bot.reply_to(message, "❌ Неверный формат дат. Нужно: ДД-ММ-ГГГГ - ДД-ММ-ГГГГ")
                else:
                    bot.reply_to(message, "❌ Используйте формат: Дата1 - Дата2")
            else:
                bot.reply_to(message, "✍️ Введите диапазон (напр. 01-03-2024 - 31-03-2024) или /cancel")

    except Exception as e:
        print(f"❌ Ошибка в handle_private_text: {e}")