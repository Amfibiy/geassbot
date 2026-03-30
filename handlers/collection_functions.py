import time
import sys
import logging
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin, get_thread_id
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/opt/render/project/src/bot.log', mode='a')
    ]
)

def log_info(msg):
    logging.info(msg)

def get_mention_string(chunk):
    """Создает строку из невидимых упоминаний для пачки пользователей"""
    invisible_char = "​"  # Нулевой символ
    return "".join([f"[{invisible_char}](tg://user?id={uid})" for uid in chunk])

def send_silent_mentions(bot, chat_id, thread_id, overflow_chunks):
    """Отправляет и удаляет сообщения только для тех, кто не поместился в основные"""
    invisible_char = "​"
    for chunk in overflow_chunks:
        try:
            mentions = get_mention_string(chunk)
            msg = bot.send_message(
                chat_id=chat_id,
                message_thread_id=thread_id,
                text=f"{invisible_char}{mentions}",
                parse_mode="Markdown",
                disable_notification=False
            )
            # Удаляем через 5 секунд, чтобы не мусорить
            threading.Timer(5.0, lambda m_id=msg.message_id: bot.delete_message(chat_id, m_id)).start()
            time.sleep(2)
        except Exception as e:
            log_info(f"❌ Ошибка в дополнительных тегах: {e}")

def send_start_messages(bot, chat_id, thread_id, active_collections, user_ids):
    """Отправляет основные сообщения, вшивая в них теги"""
    # Разбиваем всех юзеров на группы по 50 человек
    chunks = [user_ids[i:i + 50] for i in range(0, len(user_ids), 50)]
    
    # Тексты сообщений
    messages_templates = [
        "🚨 *ВНИМАНИЕ!* 🚨\n\n🎯 *Начинается сбор участников!*\n⏰ Длительность: 30 минут\n👇 Присоединяйтесь по кнопке ниже",
        "🎮 *Готовы к сбору?* 🎮\n\n🏃‍♂️ Не откладывайте на потом!\n🔥 Присоединяйтесь сейчас!",
        "🌟 *Не пропустите!* 🌟\n\n⏱️ Время ограничено!\n👥 Соберитесь вместе!",
        "💥 *Последний звонок!* 💥\n\n✅ Успейте присоединиться!\n🎁 Возможность для всех!"
    ]

    smile_ids = []
    
    # 1. Отправляем первое (главное) сообщение
    chunk0 = chunks[0] if len(chunks) > 0 else []
    mentions0 = get_mention_string(chunk0)
    
    sent_start = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=f"{messages_templates[0]}{mentions0}",
        parse_mode="Markdown"
    )
    active_collections[chat_id]['start_message_id'] = sent_start.message_id

    # 2. Отправляем дополнительные "красивые" сообщения с тегами (пачки 2, 3, 4)
    for i in range(1, 4):
        chunk = chunks[i] if len(chunks) > i else []
        mentions = get_mention_string(chunk)
        
        sent = bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=f"{messages_templates[i]}{mentions}",
            parse_mode="Markdown"
        )
        smile_ids.append(sent.message_id)
        time.sleep(1)

    active_collections[chat_id]['smile_message_ids'] = smile_ids

    # 3. Если людей > 200, запускаем "невидимые" удаляемые сообщения в фоне
    if len(chunks) > 4:
        overflow = chunks[4:]
        threading.Thread(
            target=send_silent_mentions, 
            args=(bot, chat_id, thread_id, overflow), 
            daemon=True
        ).start()

def create_counter_message(count, time_left):
    minutes_left = int(time_left // 60)
    seconds_left = int(time_left % 60)
    
    if count == 0:
        members_text = "👤 Пока никто не присоединился"
        button_text = "✅ Стать первым участником"
    else:
        members_text = f"👥 Участников: {count} человек"
        button_text = f"✅ Присоединиться ({count})"
    
    text = f"📊 *Счётчики:*\n{members_text}\n⏰ Осталось времени: {minutes_left:02d}:{seconds_left:02d}\n\n👇 Нажмите кнопку чтобы присоединиться"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(button_text, callback_data="join"))
    return text, keyboard

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Только для админов")
        return
    
    chat_id = message.chat.id
    if chat_id in active_collections:
        bot.reply_to(message, "⚠️ Сбор уже запущен!")
        return

    admin_name = message.from_user.first_name
    if message.from_user.username:
        admin_name = f"@{message.from_user.username}"
        
    thread_id = get_thread_id(message)
    user_ids = get_all_members_ids(chat_id)
    
    active_collections[chat_id] = {
        'participants': [],
        'start_time': time.time(),
        'counter_message_id': None,
        'start_message_id': None,
        'smile_message_ids': [],
        'admin_id': message.from_user.id,
        'admin_name': admin_name,
        'admin_username': message.from_user.username or "",
        'is_test': False,
        'thread_id': thread_id
    }
    
    # Запускаем отправку цепочки сообщений с тегами
    send_start_messages(bot, chat_id, thread_id, active_collections, user_ids)

    # Сообщение со счетчиком
    text, keyboard = create_counter_message(0, COLLECTION_DURATION)
    counter_message = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    active_collections[chat_id]["counter_message_id"] = counter_message.message_id
    bot.reply_to(message, "✅ Сбор начат!")

def finish_collection(chat_id, bot, active_collections, test_collection, silent=False, is_test=False):
    storage = test_collection if is_test else active_collections
    if chat_id not in storage: return

    collect = storage[chat_id]
    quantity = len(collect['participants'])
    
    if not is_test:
        completed = {
            'id': f"{chat_id}_{int(collect['start_time'])}",
            'chat_id': chat_id,
            'start_time': collect['start_time'],
            'end_time': time.time(),
            'participants': collect['participants'].copy(),
            'total_participants': quantity,
            'admin_id': collect.get('admin_id', 0),
            'admin_name': collect.get('admin_name', 'Неизвестно'),
            'is_test': False
        }
        save_history_record(completed)
    
    # Удаляем лишние "улыбки"
    for msg_id in collect.get('smile_message_ids', []):
        try: bot.delete_message(chat_id, msg_id)
        except: pass
    
    final_text = f"✅ *Сбор завершён!*\n\n👥 Участников: {quantity}\n⏰ Время вышло"
    
    try:
        if collect['counter_message_id']:
            bot.edit_message_text(chat_id=chat_id, message_id=collect['counter_message_id'], text=final_text, parse_mode="Markdown")
    except: pass

    try:
        if collect['start_message_id']:
            bot.delete_message(chat_id, collect['start_message_id'])
    except: pass

    del storage[chat_id]

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id): return
    chat_id = message.chat.id
    
    if chat_id in test_collection:
        finish_collection(chat_id, bot, active_collections, test_collection, silent=True, is_test=True)
    
    thread_id = get_thread_id(message)
    user_ids = get_all_members_ids(chat_id)
    
    test_collection[chat_id] = {
        'participants': [],
        'start_time': time.time(),
        'counter_message_id': None,
        'start_message_id': None,
        'smile_message_ids': [],
        'admin_id': message.from_user.id,
        'is_test': True,
        'thread_id': thread_id
    }
    
    # Для теста делаем упрощенную отправку без кучи "улыбок"
    chunk = user_ids[:50] if user_ids else []
    mentions = get_mention_string(chunk)
    
    start_msg = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=f"🧪 *ТЕСТОВЫЙ СБОР*{mentions}\n\n⏰ 30 минут\n👇 Нажмите для теста",
        parse_mode="Markdown"
    )
    test_collection[chat_id]['start_message_id'] = start_msg.message_id
    
    # Если в тесте тоже много людей (>50), отправляем невидимые
    if len(user_ids) > 50:
        overflow = [user_ids[i:i + 50] for i in range(50, len(user_ids), 50)]
        threading.Thread(target=send_silent_mentions, args=(bot, chat_id, thread_id, overflow), daemon=True).start()

    text, keyboard = create_counter_message(0, COLLECTION_DURATION)
    counter_msg = bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=text, reply_markup=keyboard, parse_mode="Markdown")
    test_collection[chat_id]['counter_message_id'] = counter_msg.message_id
    bot.reply_to(message, "🧪 Тестовый сбор запущен!")

def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id): return
    chat_id = message.chat.id
    if chat_id in active_collections:
        finish_collection(chat_id, bot, active_collections, test_collection, is_test=False)
        bot.reply_to(message, "✅ Завершено")
    elif chat_id in test_collection:
        finish_collection(chat_id, bot, active_collections, test_collection, is_test=True)
        bot.reply_to(message, "🧪 Тест завершен")

def handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = call.message.chat.id
    storage = active_collections if chat_id in active_collections else test_collection if chat_id in test_collection else None
    
    if not storage:
        bot.answer_callback_query(call.id, "❌ Сбор завершен", show_alert=True)
        return

    collection = storage[chat_id]
    user = call.from_user

    if any(p['id'] == user.id for p in collection['participants']):
        bot.answer_callback_query(call.id, "✅ Уже в списке")
        return
    
    collection['participants'].append({
        'id': user.id,
        'name': user.first_name,
        'username': user.username,
        'join_time': time.time()
    })

    bot.answer_callback_query(call.id, "🎉 Присоединились!")
    update_collection_counter(chat_id, collection, bot, time.time())

def update_collection_counter(chat_id, collect, bot, current_time):
    passed = current_time - collect['start_time']
    left = max(0, COLLECTION_DURATION - passed)
    quantity = len(collect['participants'])
    new_text, new_keyboard = create_counter_message(quantity, left)
    try:
        if collect['counter_message_id']:
            bot.edit_message_text(chat_id=chat_id, message_id=collect['counter_message_id'], text=new_text, reply_markup=new_keyboard, parse_mode="Markdown")
    except: pass

def update_test_counter(chat_id, collect, bot, current_time):
    update_collection_counter(chat_id, collect, bot, current_time)