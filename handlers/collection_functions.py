import time
import sys
import logging
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin, get_thread_id
from config.settings import COLLECTION_DURATION
from database.mongo import save_history_record, get_all_members_ids

# Настройка логирования в файл и stdout
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

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

def send_silent_mentions(bot, chat_id, thread_id, is_test=False):

    user_ids = get_all_members_ids(chat_id)
    if not user_ids:
        log_info(f"В базе чата {chat_id} нет пользователей для тега.")
        return

    num_waves = 2 if is_test else 5
    
    avg = len(user_ids) / num_waves
    waves = []
    last = 0.0
    while last < len(user_ids):
        waves.append(user_ids[int(last):int(last + avg)])
        last += avg

    invisible_char = "​" 
    
    log_info(f"Начинаю рассылку тегов для {chat_id}: {len(user_ids)} чел., {num_waves} волн.")

    for i, wave in enumerate(waves):
        if not wave: continue
        sub_chunks = [wave[x:x+40] for x in range(0, len(wave), 40)]
        
        for chunk in sub_chunks:
            mentions = "".join([f"[{invisible_char}](tg://user?id={uid})" for uid in chunk])
            try:
                bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    text=f"📢 Сбор! Волна {i+1}/{num_waves}{mentions}",
                    parse_mode="Markdown",
                    disable_notification=False
                )
                time.sleep(3) 
            except Exception as e:
                log_info(f"❌ Ошибка в волне {i+1}: {e}")
                continue

def send_start_messages(bot, chat_id, thread_id, active_collections, admin_name):
    start_message = f"🚨 *ВНИМАНИЕ!* 🚨\n\n🎯 *Начинается сбор участников!*\n⏰ Длительность: 30 минут\n👇 Присоединяйтесь по кнопке ниже"
    smile_messages = [
        f"🎮 *Готовы к сбору?* 🎮\n\n🏃‍♂️ Не откладывайте на потом!\n🔥 Присоединяйтесь сейчас!",
        f"🌟 *Не пропустите!* 🌟\n\n⏱️ Время ограничено!\n👥 Соберитесь вместе!",
        f"💥 *Последний звонок!* 💥\n\n✅ Успейте присоединиться!\n🎁 Возможность для всех!"
    ]
    
    sent_start = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=start_message,
        parse_mode="Markdown"
    )
    active_collections[chat_id]['start_message_id'] = sent_start.message_id
    
    smile_ids = []
    for msg in smile_messages:
        sent = bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=msg,
            parse_mode="Markdown"
        )
        smile_ids.append(sent.message_id)
    active_collections[chat_id]['smile_message_ids'] = smile_ids

def create_counter_message(count, time_left):
    minutes_left = int(time_left // 60)
    seconds_left = int(time_left % 60)
    
    if count == 0:
        members_text = "👤 Пока никто не присоединился"
        button_text = "✅ Стать первым участником"
    else:
        members_text = f"👥 Участников: {count} человек"
        button_text = f"✅ Присоединиться ({count})"
    
    text = f"""📊 *Счётчики:*
{members_text}
⏰ Осталось времени: {minutes_left:02d}:{seconds_left:02d}

👇 Нажмите кнопку чтобы присоединиться"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(button_text, callback_data="join"))
    return text, keyboard

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Только для админов")
        return
    
    chat_id = message.chat.id
    
    if chat_id in active_collections:
        collect = active_collections[chat_id]
        passed = time.time() - collect['start_time']
        left = max(0, COLLECTION_DURATION - passed)
        quantity = len(collect['participants'])
        minutes_pass = int(passed // 60)
        minutes_left = int(left // 60)
        seconds_left = int(left % 60)
        
        status_text = f"""⚠️ *Активный сбор уже идёт!*

📊 *Текущий статус:*
👥 Участников: {quantity}
⏱️ Прошло времени: {minutes_pass} мин
⏰ Осталось: {minutes_left:02d}:{seconds_left:02d}

💡 *Команды для управления:*
/list - Статистика сбора
/stop - Завершить сбор досрочно"""
        bot.reply_to(message, status_text, parse_mode="Markdown")
        return

    admin_name = message.from_user.first_name
    if message.from_user.username:
        admin_name = f"@{message.from_user.username}"
        
    thread_id = get_thread_id(message)
    
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
    
    send_start_messages(bot, chat_id, thread_id, active_collections, admin_name)

    threading.Thread(
        target=send_silent_mentions, 
        args=(bot, chat_id, thread_id, False), 
        daemon=True
    ).start()

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
    if is_test:
        if chat_id not in test_collection:
            return
        collect = test_collection[chat_id]
        storage = test_collection
    else:
        if chat_id not in active_collections:
            return
        collect = active_collections[chat_id]
        storage = active_collections

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
    
    for msg_id in collect.get('smile_message_ids', []):
        try:
            bot.delete_message(chat_id, msg_id)
        except:
            pass
    
    if is_test:
        final_text = f"🧪 *Тест завершён!*\n\n👥 Участников: {quantity}\n⏰ Время вышло"
    else:
        final_text = f"✅ *Сбор завершён!*\n\n👥 Участников: {quantity}\n⏰ Время вышло\n{'🎉 Спасибо!' if quantity > 0 else '😔 Никто не присоединился'}"
    
    try:
        if collect['counter_message_id']:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=collect['counter_message_id'],
                text=final_text,
                parse_mode="Markdown"
            )
    except:
        pass

    try:
        if collect['start_message_id']:
            bot.delete_message(chat_id, collect['start_message_id'])
    except:
        pass

    del storage[chat_id]

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id):
        return
    chat_id = message.chat.id
    
    if chat_id in test_collection:
        finish_collection(chat_id, bot, active_collections, test_collection, silent=True, is_test=True)
    
    thread_id = get_thread_id(message)
    
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
    
    start_msg = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=f"🧪 *ТЕСТОВЫЙ СБОР*\n\n⏰ 30 минут\n👇 Нажмите для теста",
        parse_mode="Markdown"
    )
    test_collection[chat_id]['start_message_id'] = start_msg.message_id

    threading.Thread(
        target=send_silent_mentions, 
        args=(bot, chat_id, thread_id, True), 
        daemon=True
    ).start()
    
    text, keyboard = create_counter_message(0, COLLECTION_DURATION)
    counter_msg = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    test_collection[chat_id]['counter_message_id'] = counter_msg.message_id
    bot.reply_to(message, "🧪 Тестовый сбор запущен!")

def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Только для админов")
        return
    
    chat_id = message.chat.id
    
    if chat_id in active_collections:
        finish_collection(chat_id, bot, active_collections, test_collection, silent=False, is_test=False)
        bot.reply_to(message, "✅ Обычный сбор досрочно завершен")
    elif chat_id in test_collection:
        finish_collection(chat_id, bot, active_collections, test_collection, silent=False, is_test=True)
        bot.reply_to(message, "🧪 Тестовый сбор досрочно завершен")
    else:
        bot.reply_to(message, "⚠️ Нет активного сбора")

def handle_join(call, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = call.message.chat.id
    if chat_id in active_collections:
        collection = active_collections[chat_id]
        collection_type = "normal"
    elif chat_id in test_collection:
        collection = test_collection[chat_id]
        collection_type = "test"
    else:
        bot.answer_callback_query(call.id, "❌ Сбор завершен", show_alert=True)
        return

    user = call.from_user

    for participant in collection['participants']:
        if participant['id'] == user.id:
            bot.answer_callback_query(call.id, "✅ Уже в списке")
            return
    
    collection['participants'].append({
        'id': user.id,
        'name': user.first_name,
        'username': user.username,
        'join_time': time.time()
    })

    bot.answer_callback_query(call.id, "🎉 Вы в списке!" if collection_type == 'normal' else "🧪 Добавлен в тест!")
    
    passed = time.time() - collection['start_time']
    left = COLLECTION_DURATION - passed
    quantity = len(collection['participants'])

    new_text, new_keyboard = create_counter_message(quantity, left)

    try:
        if collection['counter_message_id']:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=collection['counter_message_id'],
                text=new_text,
                reply_markup=new_keyboard,
                parse_mode="Markdown"
            )
    except Exception as e:
        log_info(f"❌ Ошибка обновления: {e}")

def update_collection_counter(chat_id, collect, bot, current_time):
    passed = current_time - collect['start_time']
    left = COLLECTION_DURATION - passed
    quantity = len(collect['participants'])
    new_text, new_keyboard = create_counter_message(quantity, left)
    try:
        if collect['counter_message_id']:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=collect['counter_message_id'],
                text=new_text,
                reply_markup=new_keyboard,
                parse_mode="Markdown"
            )
    except:
        pass

def update_test_counter(chat_id, collect, bot, current_time):
    update_collection_counter(chat_id, collect, bot, current_time)