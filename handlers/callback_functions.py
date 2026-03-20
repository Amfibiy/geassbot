from database.groups import save_known_groups
from utils.validators import validate_date, validate_id
from utils.helpers import is_admin

def handle_my_chat_member(update, bot, active_collections, test_collection,
                          collection_history, known_groups, user_sessions):
    try:
        chat = update.chat
        new_status = update.new_chat_member.status
        if new_status in ['member', 'administrator'] and chat.type in ['group', 'supergroup']:
            chat_id = chat.id
            chat_title = chat.title if chat.title else f"Группа {chat_id}"
            if chat_id not in known_groups:
                known_groups.add(chat_id)
                save_known_groups(known_groups)
                print(f"✅ Бот добавлен в группу: {chat_title} (ID: {chat_id})")
    except Exception as e:
        print(f"❌ Ошибка в my_chat_member_handler: {e}")

def handle_group_message(message, bot, active_collections, test_collection,
                         collection_history, known_groups, user_sessions):
    try:
        chat_id = message.chat.id
        chat_title = message.chat.title if message.chat.title else f"Группа {chat_id}"
        if chat_id not in known_groups:
            known_groups.add(chat_id)
            save_known_groups(known_groups)
            print(f"✅ Обнаружена группа через сообщение: {chat_title} (ID: {chat_id})")
    except Exception as e:
        print(f"❌ Ошибка в group_message_handler: {e}")

def handle_private_text(message, bot, active_collections, test_collection,
                        collection_history, known_groups, user_sessions):
    user_id = message.from_user.id
    text = message.text.strip()
    session = user_sessions.get(user_id)
    
    if not session:
        bot.reply_to(message,
            "❓ Используйте /list для просмотра групп\n"
            "или /clean для очистки истории"
        )
        return
    
    elif session.get('step') == 'choice_group':
        groups = session['groups']
        try:
            number = int(text)
            if 1 <= number <= len(groups):
                chat_id, name = groups[number-1]
                session['chat_id'] = chat_id
                session['name_group'] = name
                session['step'] = 'choice_period'
                from .list_functions import show_menu_periods_in_ls
                show_menu_periods_in_ls(message, session, bot, collection_history)
            else:
                bot.reply_to(message, "❌ Неверный номер")
        except:
            bot.reply_to(message, "❌ Введите номер из списка")
    
    elif session.get('step') == 'choice_period':
        try:
            number = int(text)
            from .list_functions import handle_period_callback
            # Создаём временный callback для обработки
            class TempCall:
                def __init__(self, msg, num):
                    self.data = f"period_{num}"
                    self.message = msg
                    self.id = "temp"
            handle_period_callback(TempCall(message, number), bot, active_collections,
                                 test_collection, collection_history, known_groups, user_sessions)
        except:
            bot.reply_to(message, "❌ Введите номер периода")
    
    elif session.get('step') == 'choice_group_clean':
        groups = session['groups']
        try:
            number = int(text)
            if 1 <= number <= len(groups):
                chat_id, name, _ = groups[number-1]
                session['chat_id'] = chat_id
                session['name_group'] = name
                session['step'] = 'choice_action_clean'
                text_menu = f"""🧹 *Очистка истории: {name}*

*Выберите действие:*

1️⃣ Удалить всё
2️⃣ Удалить сегодня
3️⃣ Удалить вчера  
4️⃣ Удалить за 7 дней
5️⃣ Удалить за 30 дней
6️⃣ Удалить за дату
7️⃣ Удалить за период

👇 Отправьте номер (1-7)"""
                bot.reply_to(message, text_menu, parse_mode="Markdown")
            else:
                bot.reply_to(message, "❌ Неверный номер")
        except:
            bot.reply_to(message, "❌ Введите номер из списка")
    
    elif session.get('step') == 'choice_action_clean':
        try:
            number = int(text)
            if number == 6:
                session['step'] = 'input_date_clean'
                bot.reply_to(message, "📅 Введите дату для удаления (ДД-ММ-ГГГГ)")
            elif number == 7:
                session['step'] = 'input_period_clean'
                bot.reply_to(message, "📅 Введите период (ДД-ММ-ГГГГ - ДД-ММ-ГГГГ)")
            else:
                action_map = {1: 'всё', 2: 'сегодня', 3: 'вчера', 4: 'неделя', 5: 'месяц'}
                if number in action_map:
                    session['wait'] = {'type': action_map[number], 'parameter': None}
                    session['step'] = 'confirmation_clean'
                    bot.reply_to(message, f"⚠️ Удалить {action_map[number]}?\n"
                        f"✅ да\n"
                        f"❌ нет")
                else:
                    bot.reply_to(message, "❌ Введите число от 1 до 7")
        except:
            bot.reply_to(message, "❌ Введите номер действия")
    
    elif session.get('step') == 'input_date_clean':
        date = validate_date(text)
        if date:
            session['wait'] = {'type': 'дата', 'parameter': text}
            session['step'] = 'confirmation_clean'
            bot.reply_to(message, f"⚠️ Удалить записи за {text}?\n"
                            f"✅ да\n"
                            f"❌ нет")
        else:
            bot.reply_to(message, "❌ Неверный формат даты. Используйте ДД-ММ-ГГГГ")
    
    elif session.get('step') == 'input_period_clean':
        session['wait'] = {'type': 'период', 'parameter': text}
        session['step'] = 'confirmation_clean'
        bot.reply_to(message, 
            f"⚠️ Удалить записи за период {text}?\n"
            f"✅ да\n"
            f"❌ нет")
    
    elif session.get('step') == 'confirmation_clean':
        if text.lower() in ['да', 'yes', 'y', '✅']:
            from .clean_functions import do_clean
            data = session['wait']
            do_clean(message, session['chat_id'], data['type'], data['parameter'], bot, collection_history)
        else:
            bot.reply_to(message, "❌ Очистка отменена")
        del user_sessions[user_id]
    
    elif session.get('step') == 'input_period':
        try:
            parts = text.split('-')
            if len(parts) >= 6:
                date1_str = f"{parts[0].strip()}-{parts[1].strip()}-{parts[2].strip()}"
                date2_str = f"{parts[3].strip()}-{parts[4].strip()}-{parts[5].strip()}"
                
                date1 = validate_date(date1_str)
                date2 = validate_date(date2_str)
                
                if date1 and date2:
                    begin = date1.timestamp()
                    end = date2.timestamp() + 86400
                    chat_id = session['chat_id']
                    all_participants = []
                    
                    if chat_id in collection_history:
                        for record in collection_history[chat_id]:
                            if begin <= record['end_time'] <= end:
                                all_participants.extend(record['participants'])
                    
                    if not all_participants:
                        bot.reply_to(message, f"📭 Нет участников с {date1_str} по {date2_str}")
                    else:
                        from .list_functions import show_result_by_date
                        show_result_by_date(message, chat_id, all_participants, date1_str, date2_str, session, bot, collection_history)
                    
                    session['step'] = "choice_period"
                    from .list_functions import show_menu_periods_in_ls
                    show_menu_periods_in_ls(message, session, bot, collection_history)
                else:
                    bot.reply_to(message, "❌ Неверный формат дат")
            else:
                bot.reply_to(message, "❌ Неверный формат. Используйте ДД-ММ-ГГГГ - ДД-ММ-ГГГГ")
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: {e}")

def show_result_by_date(message, chat_id, participants, date1_str, date2_str, session, bot, collection_history):
    unique = {}
    for member in participants:
        uid = member['id']
        name = f"@{member['username']}" if member.get('username') else member.get('name', 'Неизвестно')
        if uid not in unique:
            unique[uid] = {'name': name, 'quantity': 1}
        else:
            unique[uid]['quantity'] += 1
    
    report = f"📊 *{session['name_group']}* с {date1_str} по {date2_str}:\n"
    report += f"👥 Участников: {len(unique)}\n"
    report += f"🔄 Участий: {len(participants)}\n\n"

    sorted_items = sorted(unique.items(), key=lambda x: x[1]['quantity'], reverse=True)
    for _, data in sorted_items[:30]:
        report += f"• {data['name']}"
        if data['quantity'] > 1:
            report += f" ({data['quantity']} раз)"
        report += '\n'
    if len(sorted_items) > 30:
        report += f"... и ещё {len(sorted_items) - 30}"
    
    bot.reply_to(message, report, parse_mode='Markdown')
    from .list_functions import show_menu_periods_in_ls
    show_menu_periods_in_ls(message, session, bot, collection_history)