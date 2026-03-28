import time
import sys
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import is_admin, get_thread_id
from config.settings import COLLECTION_DURATION
from database.history import save_history

sys.stderr = sys.stdout 
def log_to_stderr(msg):
    """Логирование в stderr для Render"""
    print(msg, file=sys.stderr)
    sys.stderr.flush()

def send_start_messages(bot, chat_id, thread_id, active_collections):
    start_message = "🚨 *ВНИМАНИЕ!* 🚨\n\n🎯 *Начинается сбор участников!*\n⏰ Длительность: 30 минут\n👇 Присоединяйтесь по кнопке ниже"
    smile_messages = [
        "🎮 *Готовы к сбору?* 🎮\n\n🏃‍♂️ Не откладывайте на потом!\n🔥 Присоединяйтесь сейчас!",
        "🌟 *Не пропустите!* 🌟\n\n⏱️ Время ограничено!\n👥 Соберитесь вместе!",
        "💥 *Последний звонок!* 💥\n\n✅ Успейте присоединиться!\n🎁 Возможность для всех!"
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
    elif count == 1:
        members_text = f"👥 Участников: {count} человек"
        button_text = f"✅ Присоединиться ({count})"
    else:
        members_text = f"👥 Участников: {count} человек"
        button_text = f"✅ Присоединиться ({count})"
    
    text = f"""
📊 *Счётчики:*
{members_text}
⏰ Осталось времени: {minutes_left:02d}:{seconds_left:02d}

👇 Нажмите кнопку чтобы присоединиться
    """
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(button_text, callback_data="join"))
    return text, keyboard

def notify_all_members(bot, chat_id, collection, admin_name, is_test=False):
    """Уведомляет всех участников группы о начале сбора"""
    log_to_stderr(f"🔔 NOTIFY_ALL_MEMBERS ВЫЗВАНА: chat_id={chat_id}, test={is_test}")
    
    try:
        log_to_stderr("📡 Запрос get_chat_members...")
        members = bot.get_chat_members(chat_id, limit=200)
        log_to_stderr(f"📡 Получено {len(members)} участников")
        
        if not members:
            log_to_stderr("⚠️ Нет участников в ответе API")
            return
        
        mentions = []
        for member in members:
            user = member.user
            if not user.is_bot:
                if user.username:
                    mentions.append(f"@{user.username}")
                else:
                    mentions.append(user.first_name)
        
        log_to_stderr(f"📝 Сформировано {len(mentions)} упоминаний")
        
        if not mentions:
            log_to_stderr("⚠️ Нет упоминаний для отправки")
            return
        
        if is_test:
            header = f"🧪 *ТЕСТОВЫЙ СБОР!* Администратор {admin_name} запускает тестовый сбор участников!\n\n"
        else:
            header = f"🔔 *ВНИМАНИЕ!* Администратор {admin_name} запускает сбор участников!\n\n"
        
        chunk_size = 50
        thread_id = collection.get('thread_id')
        log_to_stderr(f"📨 Отправка уведомлений, thread_id={thread_id}, chunks={len(mentions)//chunk_size + 1}")
        
        for i in range(0, len(mentions), chunk_size):
            chunk = mentions[i:i + chunk_size]
            mention_text = header + "Присоединяйтесь: " + ", ".join(chunk)
            
            try:
                sent = bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    text=mention_text,
                    parse_mode="Markdown"
                )
                log_to_stderr(f"📨 Отправлена часть {i//chunk_size + 1}, message_id={sent.message_id}")
                time.sleep(0.5)
            except Exception as e:
                log_to_stderr(f"❌ Ошибка при отправке уведомления: {e}")
        
        log_to_stderr(f"✅ Уведомления отправлены {len(mentions)} участникам")
        
    except Exception as e:
        log_to_stderr(f"❌ КРИТИЧЕСКАЯ ОШИБКА в notify_all_members: {e}")
        import traceback
        log_to_stderr(traceback.format_exc())

def start_collection(message, bot, active_collections, test_collection,
                     collection_history, known_groups, user_sessions):
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
        
        status_text = f"""
⚠️ *Активный сбор уже идёт!*

📊 *Текущий статус:*
👥 Участников: {quantity}
⏱️ Прошло времени: {minutes_pass} мин
⏰ Осталось: {minutes_left:02d}:{seconds_left:02d}

💡 *Команды для управления:*
/list - Статистика сбора
/stop - Завершить сбор досрочно

❌ *Новый сбор можно запустить только после завершения текущего.*"""
        bot.reply_to(message, status_text, parse_mode="Markdown")
        return

    admin_name = message.from_user.first_name
    if message.from_user.username:
        admin_name = f"@{message.from_user.username}"
    
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
        'thread_id': get_thread_id(message)
    }
    
    thread_id = get_thread_id(message)
    send_start_messages(bot, chat_id, thread_id, active_collections)

    text, keyboard = create_counter_message(0, COLLECTION_DURATION)
    counter_message = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    active_collections[chat_id]["counter_message_id"] = counter_message.message_id
    
    notify_all_members(bot, chat_id, active_collections[chat_id], admin_name, is_test=False)
    
    bot.reply_to(message, "✅ Сбор начат!")

def finish_collection(chat_id, bot, active_collections, test_collection, 
                      collection_history, silent=False, is_test=False):
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

        if chat_id not in collection_history:
            collection_history[chat_id] = []
        collection_history[chat_id].append(completed)
        save_history(collection_history)
    
    for msg_id in collect.get('smile_message_ids', []):
        try:
            bot.delete_message(chat_id, msg_id)
        except:
            pass
    
    if is_test:
        final_text = f"""🧪 *Тест завершён!*
        
👥 Участников: {quantity}
⏰ Время вышло"""
    else:
        final_text = f"""✅ *Сбор завершён!*
        
👥 Участников: {quantity}
⏰ Время вышло
{'🎉 Спасибо!' if quantity > 0 else '😔 Никто не присоединился'}"""
    
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

    if not silent and not is_test and quantity > 0:
        for member in collect['participants']:
            try:
                bot.send_message(
                    member['id'],
                    f"🎉 Сбор завершён! Участников: {quantity}",
                    parse_mode="Markdown"
                )
            except:
                continue
    
    del storage[chat_id]

def start_test_collection(message, bot, active_collections, test_collection,
                          collection_history, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id):
        return
    chat_id = message.chat.id
    
    if chat_id in test_collection:
        finish_collection(chat_id, bot, active_collections, test_collection, 
                         collection_history, silent=True, is_test=True)
    
    admin_name = message.from_user.first_name
    if message.from_user.username:
        admin_name = f"@{message.from_user.username}"
    
    test_collection[chat_id] = {
        'participants': [],
        'start_time': time.time(),
        'counter_message_id': None,
        'start_message_id': None,
        'smile_message_ids': [],
        'admin_id': message.from_user.id,
        'is_test': True,
        'thread_id': get_thread_id(message)
    }
    
    thread_id = get_thread_id(message)
    text, keyboard = create_counter_message(0, COLLECTION_DURATION)
    
    start_msg = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text="🧪 *ТЕСТОВЫЙ СБОР*\n\n⏰ 30 минут\n👇 Нажмите для теста",
        parse_mode="Markdown"
    )
    test_collection[chat_id]['start_message_id'] = start_msg.message_id
    
    counter_msg = bot.send_message(
        chat_id=chat_id,
        message_thread_id=thread_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    test_collection[chat_id]['counter_message_id'] = counter_msg.message_id
    
    notify_all_members(bot, chat_id, test_collection[chat_id], admin_name, is_test=True)
    
    bot.reply_to(message, "🧪 Тестовый сбор запущен!")

def stop_collection(message, bot, active_collections, test_collection,
                    collection_history, known_groups, user_sessions):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Только для админов")
        return
    
    chat_id = message.chat.id
    
    if chat_id in active_collections:
        finish_collection(chat_id, bot, active_collections, test_collection, 
                         collection_history, silent=False, is_test=False)
        bot.reply_to(message, "✅ Обычный сбор досрочно завершен")
    elif chat_id in test_collection:
        finish_collection(chat_id, bot, active_collections, test_collection, 
                         collection_history, silent=False, is_test=True)
        bot.reply_to(message, "🧪 Тестовый сбор досрочно завершен")
    else:
        bot.reply_to(message, "⚠️ Нет активного сбора")

def handle_join(call, bot, active_collections, test_collection,
                collection_history, known_groups, user_sessions):
    log_to_stderr(f"🔘 ПОЛУЧЕН CALLBACK: {call.data}")
    log_to_stderr(f"👤 От пользователя: {call.from_user.id}")
    log_to_stderr(f"💬 В чате: {call.message.chat.id}")
    
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
            log_to_stderr(f"✅ Сообщение обновлено, участников: {quantity}")
    except Exception as e:
        log_to_stderr(f"❌ Ошибка обновления: {e}")

def update_collection_counter(chat_id, collect, bot, current_time):
    """Обновляет счётчик обычного сбора"""
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
    """Обновляет счётчик тестового сбора"""
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