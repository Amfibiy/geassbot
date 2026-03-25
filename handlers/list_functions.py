import time
import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin

def escape_markdown(text):
    """Экранирует спецсимволы для Markdown"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

def show_current_collection_in_group(message, collect, bot):
    quantity = len(collect['participants'])
    passed = time.time() - collect['start_time']
    left = max(0, 1800 - passed)
    minutes_pass = int(passed // 60)
    minutes_left = int(left // 60)
    seconds_left = int(left % 60)
    
    if collect.get('is_test'):
        header = "🧪 *Текущий тестовый сбор*"
    else:
        header = "📊 *Текущий сбор*"

    text = f"""{header}

👥 Участников: {quantity}
⏱️ Прошло: {minutes_pass} мин
⏰ Осталось: {minutes_left:02d}:{seconds_left:02d}

*Список участников:*\n"""
    
    for p in collect['participants'][:20]:
        if p.get('username'):
            # Экранируем username (может содержать _, *, и т.д.)
            name = escape_markdown(f"@{p['username']}")
        else:
            # обычное имя экранируем
            name = escape_markdown(p.get('name', 'Неизвестно'))
        text += f"• {name}\n"
    
    if len(collect['participants']) > 20:
        text += f"... и ещё {len(collect['participants']) - 20}"
    
    bot.reply_to(message, text, parse_mode="Markdown")

def show_period_in_ls(message, chat_id, period, session, bot, collection_history):
    now = time.time()
    
    if period == "день":
        begin = now - 86400
        name = "последние 24 часа"
    elif period == "вчера":
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        begin = yesterday.replace(hour=0, minute=0, second=0).timestamp()
        end = begin + 86400
        date_str = yesterday.strftime('%d-%m-%Y')
        name = f"за {date_str} (вчера)"
    elif period == "неделя":
        begin = now - 604800
        name = "последние 7 дней"
    elif period == "месяц":
        begin = now - 2592000
        name = "последние 30 дней"
    elif period == "квартал":
        begin = now - 7776000
        name = "последние 90 дней"
    elif period == "год":
        begin = now - 31536000
        name = "последние 365 дней"
    elif period == "всё":
        begin = 0
        name = "всё время"
    else:
        bot.reply_to(message, "❌ Неизвестный период")
        return
    
    all_participants = []
    if chat_id in collection_history:
        for record in collection_history[chat_id]:
            if period == "вчера":
                if begin <= record['end_time'] <= end:
                    all_participants.extend(record['participants'])
            else:
                if record['end_time'] >= begin:
                    all_participants.extend(record['participants'])
    
    if not all_participants:
        if period == "вчера":
            bot.reply_to(message, f"📭 За {date_str} (вчера) не было сборов")
        else:
            bot.reply_to(message, f"📭 Нет участников за {name}")
        show_menu_periods_in_ls(message, session, bot, collection_history)
        return
    
    unique = {}
    for member in all_participants:
        uid = member['id']
        if member.get('username'):
            name_display = escape_markdown(f"@{member['username']}")
        else:
            name_display = escape_markdown(member.get('name', 'Неизвестно'))
        if uid not in unique:
            unique[uid] = {'name': name_display, 'quantity': 1}
        else:
            unique[uid]['quantity'] += 1
    
    report = f"📊 *{escape_markdown(session['name_group'])}* за {name}:\n"
    report += f"👥 Участников: {len(unique)}\n"
    report += f"🔄 Участий: {len(all_participants)}\n\n"
    
    sorted_items = sorted(unique.items(), key=lambda x: x[1]['quantity'], reverse=True)
    for _, data in sorted_items[:30]:
        report += f"• {data['name']}"
        if data['quantity'] > 1:
            report += f" ({data['quantity']} раз)"
        report += "\n"
    if len(sorted_items) > 30:
        report += f"... и ещё {len(sorted_items) - 30}"
    
    bot.reply_to(message, report, parse_mode='Markdown')
    show_menu_periods_in_ls(message, session, bot, collection_history)

def show_menu_of_choice_group_in_ls(message, user_id, bot, known_groups, active_collections, test_collection, collection_history, user_sessions):
    available_groups = []
    
    for chat_id in known_groups:
        try:
            if is_admin(chat_id, user_id):
                chat = bot.get_chat(chat_id)
                name = chat.title if chat.title else f"Группа {chat_id}"
                available_groups.append((chat_id, name))
        except:
            if chat_id in known_groups:
                known_groups.remove(chat_id)
                from database.groups import save_known_groups
                save_known_groups(known_groups)
            continue
    
    all_chats = set(collection_history.keys()) | set(active_collections.keys()) | set(test_collection.keys())
    for chat_id in all_chats:
        if chat_id not in known_groups:
            try:
                if is_admin(chat_id, user_id):
                    chat = bot.get_chat(chat_id)
                    name = chat.title if chat.title else f"Группа {chat_id}"
                    available_groups.append((chat_id, name))
            except:
                continue
    
    if not available_groups:
        bot.reply_to(message,
            "👋 *Добро пожаловать!*\n\n"
            "📭 Пока нет групп.\n\n"
            "📌 *Чтобы добавить группу:*\n"
            "1️⃣ Добавьте бота в группу как администратора\n"
            "2️⃣ Бот автоматически обнаружит группу\n"
            "3️⃣ Через несколько секунд группа появится здесь\n\n"
            "💡 *Статус:* Бот проверяет новые группы автоматически"
        )
        return
    
    available_groups.sort(key=lambda x: x[1])
    text = "📋 <b>Выберите группу для просмотра:</b>\n\n"

    for index, (chat_id, name) in enumerate(available_groups, 1):
        status = "🟢" if chat_id in active_collections else "⚪"
        # Экранируем имя группы для HTML
        safe_name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        text += f"{index}. {status} {safe_name}\n"
        text += f"   🆔 <code>{chat_id}</code>\n\n"
    
    text += "👇 <b>Отправьте номер группы</b> (1, 2, 3...)\n"
    text += "или введите ID группы вручную"

    user_sessions[user_id] = {
        'groups': available_groups,
        'step': 'choice_group'
    }
    
    bot.reply_to(message, text, parse_mode="HTML")

def show_menu_periods_in_ls(message, session, bot, collection_history):
    chat_id = session['chat_id']
    name = session['name_group']
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("1️⃣ Текущий", "period_1"),
        ("2️⃣ Сегодня", "period_2"),
        ("3️⃣ Вчера", "period_3"),
        ("4️⃣ Неделя", "period_4"),
        ("5️⃣ Месяц", "period_5"),
        ("6️⃣ Квартал", "period_6"),
        ("7️⃣ Год", "period_7"),
        ("8️⃣ Всё время", "period_8"),
        ("9️⃣ Свой период", "period_9")
    ]

    for text, data in buttons:
        keyboard.add(InlineKeyboardButton(text, callback_data=data))
    
    total_collections = len(collection_history.get(chat_id, []))
    total_participants = 0
    for record in collection_history.get(chat_id, []):
        total_participants += record.get('total_participants', len(record.get('participants', [])))
    
    # Экранируем имя для HTML
    safe_name = name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = f"""📋 <b>Группа: {safe_name}</b>

📊 <b>Статистика:</b>
• Всего сборов: {total_collections}
• Всего участников: {total_participants}

👇 <b>Нажмите на период для просмотра</b>"""
    
    session['step'] = 'choice_period'
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

def show_participants_list(message, bot, active_collections, test_collection,
                           collection_history, known_groups, user_sessions):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if message.chat.type != "private":
        if not is_admin(chat_id, user_id):
            bot.reply_to(message, "❌ Только для админов")
            return
        if chat_id in active_collections:
            collect = active_collections[chat_id]
            show_current_collection_in_group(message, collect, bot)
        elif chat_id in test_collection:
            collect = test_collection[chat_id]
            show_current_collection_in_group(message, collect, bot)
        else:
            bot.reply_to(message, "📭 Нет активного сбора. Используйте /start_collect")
        return
    
    show_menu_of_choice_group_in_ls(message, user_id, bot, known_groups, active_collections, test_collection, collection_history, user_sessions)

def handle_period_callback(call, bot, active_collections, test_collection,
                           collection_history, known_groups, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id)
    if not session or session.get('step') != 'choice_period':
        bot.answer_callback_query(call.id, "❌ Сессия устарела. Начните заново с /list")
        return
    
    period_num = int(call.data.replace('period_', ''))
    chat_id = session['chat_id']
    periods = {
        1: 'текущий',
        2: 'день',
        3: 'вчера',
        4: 'неделя',
        5: 'месяц',
        6: 'квартал',
        7: 'год',
        8: 'всё',
        9: 'ожидание_периода'
    }
    period = periods.get(period_num)
    
    if period == "текущий":
        if chat_id in active_collections:
            collect = active_collections[chat_id]
            show_current_collection_in_group(call.message, collect, bot)
        else:
            bot.answer_callback_query(call.id, "📭 Нет активного сбора", show_alert=True)
    elif period == 'ожидание_периода':
        session['step'] = 'input_period'
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📅 Введите период (ДД-ММ-ГГГГ - ДД-ММ-ГГГГ)")
    else:
        show_period_in_ls(call.message, chat_id, period, session, bot, collection_history)
        bot.answer_callback_query(call.id)