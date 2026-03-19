import datetime
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin
from database.history import save_history

def do_clean(message, chat_id, clean_type, parameter, bot, collection_history):
    if chat_id not in collection_history:
        bot.reply_to(message, "📭 Нет истории")
        return
    
    now = time.time()
    new_records = []
    deleted = 0
    
    if clean_type == 'всё':
        deleted = len(collection_history[chat_id])
        collection_history[chat_id] = []
        bot.reply_to(message, f"✅ Удалено {deleted} записей")
        save_history(collection_history)
        return
    
    if clean_type == "сегодня":
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0)
        begin = today.timestamp()
        end = begin + 86400
        name = "сегодня"
    elif clean_type == "вчера":
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        begin = yesterday.replace(hour=0, minute=0, second=0).timestamp()
        end = begin + 86400
        name = "вчера"
    elif clean_type == "неделя":
        begin = now - 604800
        end = now
        name = "последние 7 дней"
    elif clean_type == "месяц":
        begin = now - 2592000
        end = now
        name = "последние 30 дней"
    elif clean_type == "дата":
        try:
            date = datetime.datetime.strptime(parameter, "%d-%m-%Y")
            begin = date.replace(hour=0, minute=0, second=0).timestamp()
            end = begin + 86400
            name = f"за {parameter}"
        except:
            bot.reply_to(message, "❌ Неверный формат даты. Используйте ДД-ММ-ГГГГ")
            return
    elif clean_type == "период":
        try:
            dates = parameter.split('-')
            date1 = datetime.datetime.strptime(dates[0].strip(), "%d-%m-%Y")
            date2 = datetime.datetime.strptime(dates[1].strip(), "%d-%m-%Y")
            begin = date1.timestamp()
            end = date2.timestamp() + 86400
            name = f"с {dates[0].strip()} по {dates[1].strip()}"
        except:
            bot.reply_to(message, "❌ Неверный формат. Используйте ДД-ММ-ГГГГ - ДД-ММ-ГГГГ")
            return
    
    for record in collection_history[chat_id]:
        if begin <= record['end_time'] <= end:
            deleted += 1
        else:
            new_records.append(record)
    
    collection_history[chat_id] = new_records
    save_history(collection_history)
    bot.reply_to(message, f"✅ Удалено {deleted} записей {name}")

def handle_clean(message, bot, active_collections, test_collection,
                 collection_history, known_groups, user_sessions):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if message.chat.type != "private":
        if not is_admin(chat_id, user_id, bot, known_groups):
            bot.reply_to(message, "❌ Только для админов")
            return
        show_the_cleaning_group_menu(message, chat_id, bot, collection_history, user_sessions)
        return
    
    show_group_to_clean_in_ls(message, user_id, bot, known_groups, collection_history, user_sessions)

def show_the_cleaning_group_menu(message, chat_id, bot, collection_history, user_sessions):
    quantity = len(collection_history.get(chat_id, []))
    if quantity == 0:
        bot.reply_to(message, "📭 В этой группе нет истории для очистки")
        return
    
    text = f"""🧹 *Очистка истории группы*

📊 Всего записей: {quantity}

*Выберите действие:*

1️⃣ Удалить всё
2️⃣ Удалить за сегодня
3️⃣ Удалить за вчера
4️⃣ Удалить за последние 7 дней
5️⃣ Удалить за последние 30 дней
6️⃣ Удалить за конкретную дату
7️⃣ Удалить за период (дата1 - дата2)

👇 Отправьте номер действия (1-7)"""
    
    user_sessions[message.from_user.id] = {
        'chat_id': chat_id,
        'step': 'choice_action_clean'
    }
    bot.reply_to(message, text, parse_mode="Markdown")

def show_group_to_clean_in_ls(message, user_id, bot, known_groups, collection_history, user_sessions):
    available = []
    
    for chat_id in known_groups:
        try:
            if is_admin(chat_id, user_id, bot, known_groups) and collection_history.get(chat_id):
                try:
                    chat = bot.get_chat(chat_id)
                    name = chat.title if chat.title else f"Группа {chat_id}"
                    records = len(collection_history[chat_id])
                    available.append((chat_id, name, records))
                except:
                    available.append((chat_id, f"Группа {chat_id}", len(collection_history[chat_id])))
        except:
            continue

    for chat_id in collection_history.keys():
        if chat_id not in known_groups:
            try:
                if is_admin(chat_id, user_id, bot, known_groups):
                    chat = bot.get_chat(chat_id)
                    name = chat.title if chat.title else f"Группа {chat_id}"
                    records = len(collection_history[chat_id])
                    available.append((chat_id, name, records))
            except:
                available.append((chat_id, f"Группа {chat_id}", len(collection_history[chat_id])))
    
    if not available:
        bot.reply_to(message, "📭 Нет групп с историей для очистки")
        return
    
    available.sort(key=lambda x: x[1])
    text = "🧹 <b>Выберите группу для очистки:</b>\n\n"
    keyboard = InlineKeyboardMarkup(row_width=1)

    for index, (chat_id, name, quantity) in enumerate(available, 1):
        text += f"{index}. {name} ({quantity} записей)\n"
        text += f"🆔 <code>{chat_id}</code>\n\n"
        keyboard.add(InlineKeyboardButton(f"{index}. {name}",
            callback_data=f"clean_group_{chat_id}"))
    
    text += "👇 Отправьте номер группы (1, 2, 3...)\n"
    text += "или ID группы вручную"
    
    user_sessions[user_id] = {
        'groups': available,
        'step': 'choice_group_clean'
    }
    
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

def handle_clean_group_callback(call, bot, active_collections, test_collection,
                                 collection_history, known_groups, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id)
    if not session or session.get('step') != 'choice_group_clean':
        bot.answer_callback_query(call.id, "❌ Сессия устарела. Начните заново с /clean")
        return
    
    chat_id = int(call.data.replace('clean_group_', ''))
    name = None

    for cid, n, _ in session['groups']:
        if cid == chat_id:
            name = n
            break
    
    if not name:
        bot.answer_callback_query(call.id, "❌ Группа не найдена")
        return
    
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

👇 *Отправьте номер* (1-7) или нажмите кнопку"""
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    actions = [
        ("1️⃣ Всё", "clean_action_1"),
        ("2️⃣ Сегодня", "clean_action_2"),
        ("3️⃣ Вчера", "clean_action_3"),
        ("4️⃣ 7 дней", "clean_action_4"),
        ("5️⃣ 30 дней", "clean_action_5"),
        ("6️⃣ Дата", "clean_action_6"),
        ("7️⃣ Период", "clean_action_7")
    ]

    for text, data in actions:
        keyboard.add(InlineKeyboardButton(text, callback_data=data))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text_menu,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id)

def handle_clean_action_callback(call, bot, active_collections, test_collection,
                                  collection_history, known_groups, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id)
    if not session or session.get('step') != 'choice_action_clean':
        bot.answer_callback_query(call.id, "❌ Сессия устарела")
        return
    
    action_num = int(call.data.replace('clean_action_', ''))
    action_map = {
        1: ('всё', None),
        2: ('сегодня', None),
        3: ('вчера', None),
        4: ('неделя', None),
        5: ('месяц', None),
        6: ('ожидание_даты_очистки', None),
        7: ('ожидание_периода_очистки', None)
    }
    
    action_type, _ = action_map[action_num]
    
    if action_type == 'ожидание_даты_очистки':
        session['step'] = 'input_date_clean'
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📅 Введите дату для удаления (ДД-ММ-ГГГГ)")
    elif action_type == 'ожидание_периода_очистки':
        session['step'] = 'input_period_clean'
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📅 Введите период (ДД-ММ-ГГГГ - ДД-ММ-ГГГГ)")
    else:
        session['wait'] = {'type': action_type, 'parameter': None}
        session['step'] = 'confirmation_clean'
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Нет", callback_data="confirm_no")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚠️ Удалить {action_type}?\n\nВы уверены?",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)

def handle_confirm_callback(call, bot, active_collections, test_collection,
                             collection_history, known_groups, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id)
    if not session or session.get('step') != 'confirmation_clean':
        bot.answer_callback_query(call.id, "❌ Сессия устарела")
        return
    
    if call.data == "confirm_yes":
        data = session['wait']
        do_clean(call.message, session['chat_id'], data['type'], data['parameter'], bot, collection_history)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ Очистка выполнена!",
            parse_mode='Markdown'
        )
    else:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Очистка отменена",
            parse_mode='Markdown'
        )

    del user_sessions[user_id]
    bot.answer_callback_query(call.id)