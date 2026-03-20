from database.groups import save_known_groups
from utils.validators import validate_date, validate_id
from utils.helpers import is_admin
import datetime
import time

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
                target_id = number
                found = False
                for chat_id, name in groups:
                    if chat_id == target_id:
                        found = True
                        session['chat_id'] = chat_id
                        session['name_group'] = name
                        session['step'] = 'choice_period'
                        from .list_functions import show_menu_periods_in_ls
                        show_menu_periods_in_ls(message, session, bot, collection_history)
                        break
                if not found:
                    bot.reply_to(message, "❌ Группа с таким ID не найдена")
        except:
            try:
                digits = ''.join(c for c in text if c.isdigit())
                if not digits:
                    bot.reply_to(message, "❌ Неверный формат ID")
                    return
                target_id = int(digits)
                found = False
                for chat_id, name in groups:
                    if abs(chat_id) == target_id:
                        found = True
                        session['chat_id'] = chat_id
                        session['name_group'] = name
                        session['step'] = 'choice_period'
                        from .list_functions import show_menu_periods_in_ls
                        show_menu_periods_in_ls(message, session, bot, collection_history)
                        break
                if not found:
                    bot.reply_to(message, "❌ Группа с таким ID не найдена")
            except:
                bot.reply_to(message, "❌ Введите номер из списка или ID группы")
    
    elif session.get('step') == 'choice_period':
        try:
            number = int(text)
            chat_id = session['chat_id']
            periods = {
                1: ('текущий', None),
                2: ('день', None),
                3: ('вчера', None),
                4: ('неделя', None),
                5: ('месяц', None),
                6: ('квартал', None),
                7: ('год', None),
                8: ('всё', None),
                9: ('ожидание_периода', None)
            }
            if number in periods:
                period, additional = periods[number]
                if period == "текущий":
                    if chat_id in active_collections:
                        collect = active_collections[chat_id]
                        from .list_functions import show_current_collection_in_group
                        show_current_collection_in_group(message, collect, bot)
                    else:
                        bot.reply_to(message, "📭 Нет активного сбора")
                elif period == 'вчера':
                    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
                    date_str = yesterday.strftime('%d-%m-%Y')
                    begin = yesterday.replace(hour=0, minute=0, second=0).timestamp()
                    end = begin + 86400
                    all_participants = []
                    if chat_id in collection_history:
                        for record in collection_history[chat_id]:
                            if begin <= record['end_time'] <= end:
                                all_participants.extend(record['participants'])
                    if not all_participants:
                        bot.reply_to(message, f"📭 Нет участников за {date_str}")
                    else:
                        from .list_functions import show_result_at_date
                        show_result_at_date(message, chat_id, all_participants, date_str, session, bot, collection_history)
                    from .list_functions import show_menu_periods_in_ls
                    show_menu_periods_in_ls(message, session, bot, collection_history)
                elif period == 'ожидание_периода':
                    session['step'] = 'input_period'
                    bot.reply_to(message, "📅 Введите период (ДД-ММ-ГГГГ - ДД-ММ-ГГГГ)")
                else:
                    from .list_functions import show_period_in_ls
                    show_period_in_ls(message, chat_id, period, session, bot, collection_history)
            else:
                bot.reply_to(message, "❌ Введите номер периода")
        except:
            bot.reply_to(message, "❌ Введите номер периода")
    
    elif session.get('step') == 'input_date':
        chat_id = session['chat_id']
        try:
            date = validate_date(text)
            if date:
                begin = date.timestamp()
                end = begin + 86400
                all_participants = []
                if chat_id in collection_history:
                    for record in collection_history[chat_id]:
                        if begin <= record['end_time'] <= end:
                            all_participants.extend(record['participants'])
                if not all_participants:
                    bot.reply_to(message, f"📭 Нет участников за {text}")
                else:
                    from .list_functions import show_result_at_date
                    show_result_at_date(message, chat_id, all_participants, text, session, bot, collection_history)
                session['step'] = "choice_period"
                from .list_functions import show_menu_periods_in_ls
                show_menu_periods_in_ls(message, session, bot, collection_history)
            else:
                bot.reply_to(message, "❌ Неверный формат. Используйте ДД-ММ-ГГГГ")
        except:
            bot.reply_to(message, "❌ Неверный формат. Используйте ДД-ММ-ГГГГ")
    
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
                # ИСПРАВЛЕНО: используем validate_id
                valid_id = validate_id(text)
                if valid_id:
                    target_id = int(valid_id)
                    found = False
                    for cid, n, _ in groups:
                        if cid == target_id or abs(cid) == target_id:
                            found = True
                            session['chat_id'] = cid
                            session['name_group'] = n
                            session['step'] = 'choice_action_clean'
                            text_menu = f"""🧹 *Очистка истории: {n}*

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
                            break
                    if not found:
                        bot.reply_to(message, "❌ Группа с таким ID не найдена")
                else:
                    bot.reply_to(message, "❌ Неверный формат ID")
        except:
            bot.reply_to(message, "❌ Введите номер из списка")
    
    elif session.get('step') == 'choice_action_clean':
        try:
            number = int(text)
            chat_id = session['chat_id']
            action = {
                1: ('всё', None),
                2: ('сегодня', None),
                3: ('вчера', None),
                4: ('неделя', None),
                5: ('месяц', None),
                6: ('ожидание_даты_очистки', None),
                7: ('ожидание_периода_очистки', None)
            }
            if number in action:
                action_type, additional = action[number]
                if action_type == 'ожидание_даты_очистки':
                    session['step'] = 'input_date_clean'
                    bot.reply_to(message, "📅 Введите дату для удаления (ДД-ММ-ГГГГ)")
                elif action_type == 'ожидание_периода_очистки':
                    session['step'] = 'input_period_clean'
                    bot.reply_to(message, "📅 Введите период (ДД-ММ-ГГГГ - ДД-ММ-ГГГГ)")
                else:
                    session['wait'] = {'type': action_type, 'parameter': None}
                    session['step'] = 'confirmation_clean'
                    bot.reply_to(message, f"⚠️ Удалить {action_type}?\n"
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
        chat_id = session['chat_id']
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
                bot.reply_to(message, f"❌ Неверный формат. Используйте ДД-ММ-ГГГГ - ДД-ММ-ГГГГ")
        except Exception as e:
            bot.reply_to(message, f"❌ Неверный формат. Используйте ДД-ММ-ГГГГ - ДД-ММ-ГГГГ")