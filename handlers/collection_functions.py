import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids
from utils.messages import START_MESSAGES, TEST_START_MSG, COLLECT_ALREADY_RUNNING

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    
    if chat_id in collection_dict:
        col = collection_dict[chat_id]
        elapsed = int(time.time() - col['start_time'])
        minutes_pass = elapsed // 60
        rem = max(0, COLLECTION_DURATION - elapsed)
        
        status_text = f"""⚠️ *Активный сбор уже идёт!*

📊 *Текущий статус:*
👥 Участников: {len(col['participants'])}
⏱️ Прошло времени: {minutes_pass} мин
⏰ Осталось: {rem // 60:02d}:{rem % 60:02d}

💡 *Команды для управления:*
/list - Статистика сбора
/stop - Завершить сбор досрочно

❌ *Новый сбор можно запустить только после завершения текущего.*"""
        
        bot.reply_to(message, status_text, parse_mode="Markdown")
        return

    member_ids = get_all_members_ids(chat_id)
    # Твои невидимые теги для упоминания всех
    tags = [f'<a href="tg://user?id={m_id}">\u200b</a>' for m_id in member_ids]
    mention_text = "".join(tags)

    if is_test:
        msgs = [
            f"{mention_text}🧪 *ТЕСТОВЫЙ СБОР*\n\n⏰ 30 минут\n👇 Нажмите для теста"
        ]
    else:
        # Твои 4 сообщения при старте
        msgs = [
            f"{mention_text}🚨 *ВНИМАНИЕ!* 🚨\n\n🎯 *Начинается сбор участников!*\n⏰ Длительность: 30 минут\n👇 Присоединяйтесь по кнопке ниже",
            f"{mention_text}🎮 *Готовы к сбору?* 🎮\n\n🏃‍♂️ Не откладывайте на потом!\n🔥 Присоединяйтесь сейчас!",
            f"{mention_text}🌟 *Не пропустите!* 🌟\n\n⏱️ Время ограничено!\n👥 Соберитесь вместе!",
            f"{mention_text}💥 *Последний звонок!* 💥\n\n✅ Успейте присоединиться!\n🎁 Возможность для всех!"
        ]

    for m_text in msgs:
        bot.send_message(chat_id, m_text, parse_mode="HTML")
        time.sleep(0.5)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Присоединиться (0)", callback_data="join_collection"))
    
    main_text = f"""📊 *Счётчики:*
Пока никто не присоединился...
⏰ Осталось времени: 30:00

👇 Нажмите кнопку чтобы присоединиться"""

    main_msg = bot.send_message(chat_id, main_text, reply_markup=markup, parse_mode="Markdown")
    
    # Сюда добавили chat_id и is_test для связи с БД
    collection_dict[chat_id] = {
        'chat_id': chat_id,
        'is_test': is_test,
        'start_time': time.time(),
        'main_message_id': main_msg.message_id,
        'participants': [],
        'title': message.chat.title,
        'mention_text': mention_text
    }

def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = message.chat.id
    is_test = False
    col = active_collections.pop(chat_id, None)
    if not col:
        col = test_collection.pop(chat_id, None)
        is_test = True
    if not col:
        bot.reply_to(message, "❌ Нет активного сбора для остановки.")
        return

    quantity = len(col['participants'])
    final_text = f"""✅ *Сбор завершён!*
        
👥 Участников: {quantity}
⏰ Завершено досрочно
{'🎉 Спасибо!' if quantity > 0 else '😔 Никто не присоединился'}"""

    bot.send_message(chat_id, final_text, parse_mode="Markdown")
    
    if not is_test and len(col['participants']) > 0:
        save_history_record(col)

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if message.chat.type == 'private':
        bot.reply_to(message, "🏰 **В ЛС нельзя запустить сбор.**")
        return
    _start_generic_collection(message, bot, active_collections, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if message.chat.type == 'private':
        bot.reply_to(message, "🧪 **В ЛС нельзя запустить тест.**")
        return
    _start_generic_collection(message, bot, test_collection, is_test=True)

def handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions):
    # Принудительно делаем chat_id числом
    chat_id = int(call.message.chat.id)
    col = active_collections.get(chat_id) or test_collection.get(chat_id)

    if not col:
        bot.answer_callback_query(call.id, "❌ Сбор уже завершен.", show_alert=True)
        return

    user = call.from_user
    # Проверка на наличие участника
    if any(p.get('id') == user.id for p in col['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в списке!")
        return

    # Добавляем данные, которые нужны для /list в mongo.py
    col['participants'].append({
        'id': user.id, 
        'username': user.username, 
        'name': user.first_name
    })
    
    count = len(col['participants'])
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ Присоединиться ({count})", callback_data="join_collection"))
    
    try:
        # Обновляем именно то сообщение, где кнопка
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=col['main_message_id'],
            reply_markup=markup
        )
    except Exception as e:
        print(f"Ошибка обновления кнопки: {e}")

    bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, вы в деле!")

def stop_collection_automatically(chat_id, bot, coll_dict, is_test):
    col = coll_dict.pop(int(chat_id), None)
    if not col: return

    quantity = len(col['participants'])
    final_text = f"""✅ *Сбор завершён!*
        
👥 Участников: {quantity}
⏰ Время вышло
{'🎉 Спасибо!' if quantity > 0 else '😔 Никто не присоединился'}"""

    bot.send_message(chat_id, final_text, parse_mode="Markdown")
    
    if not is_test and quantity > 0:
        save_history_record(col)