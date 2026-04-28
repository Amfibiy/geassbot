import time
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.mongo import (
    get_all_members_ids, 
    get_combined_settings, 
    save_known_group, 
    save_history_record
)
from utils.messages import (
    START_MESSAGES_MANDATORY, TEST_MESSAGES, COLLECT_BODY_ACTIVE, 
    COLLECT_ALREADY_RUNNING, TEST_BODY_ACTIVE
)
from config.settings import EMOJI_LIST, TAGS_CHUNK_SIZE

def _start_generic_collection(message, bot, active_collections, test_collection, is_test=False):
    chat_id = message.chat.id
    admin_id = message.from_user.id

    existing_col = active_collections.get(chat_id) or test_collection.get(chat_id)
    if existing_col:
        elapsed = int(time.time() - existing_col['start_time'])
        total = existing_col['duration']
        rem = max(0, total - elapsed)
        
        bot.send_message(chat_id, COLLECT_ALREADY_RUNNING.format(
            count=len(existing_col['participants']),
            elapsed=elapsed // 60,
            remaining=f"{rem // 60:02d}:{rem % 60:02d}"
        ), parse_mode="HTML")
        return

    target_dict = test_collection if is_test else active_collections
    precursor_templates = TEST_MESSAGES if is_test else START_MESSAGES_MANDATORY
    main_template = TEST_BODY_ACTIVE if is_test else COLLECT_BODY_ACTIVE

    member_ids = list(set(get_all_members_ids(chat_id)))
    bot_me = bot.get_me()
    if bot_me.id in member_ids: member_ids.remove(bot_me.id)

    save_known_group(chat_id, message.chat.title, member_count=len(member_ids))
    configs = get_combined_settings(chat_id, admin_id)
    duration_sec = configs['duration'] 

    tag_chunks = []
    current_chunk = []
    for i, uid in enumerate(member_ids):
        emoji = EMOJI_LIST[i % len(EMOJI_LIST)]
        current_chunk.append(f'<a href="tg://user?id={uid}">{emoji}</a>')
        if len(current_chunk) == TAGS_CHUNK_SIZE:
            tag_chunks.append(" ".join(current_chunk))
            current_chunk = []
    if current_chunk:
        tag_chunks.append(" ".join(current_chunk))

    msg_ids_to_delete = [] 
    for i, template in enumerate(precursor_templates):
        tags_string = f"\n\n{tag_chunks[i]}\n" if i < len(tag_chunks) else ""
        try:
            msg = bot.send_message(chat_id, template.format(
                duration=duration_sec // 60,
                tags=tags_string
            ), parse_mode="HTML")
            msg_ids_to_delete.append(msg.message_id) 
            time.sleep(0.3) 
        except Exception: pass

    remaining_tags = ""
    if len(tag_chunks) > len(precursor_templates):
        remaining_tags = "\n\n" + "\n".join(tag_chunks[len(precursor_templates):]) + "\n"

    try:
        rem_mins = duration_sec // 60
        rem_secs = duration_sec % 60
        remaining_str = f"{rem_mins:02d}:{rem_secs:02d}"

        main_text = main_template.format(
            duration=rem_mins,
            remaining=remaining_str,
            tags=remaining_tags,
            count=0
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Присоединиться (0)", callback_data="join_collection"))
        
        main_msg = bot.send_message(chat_id, main_text, reply_markup=markup, parse_mode="HTML")
        msg_ids_to_delete.append(main_msg.message_id) 
        
        target_dict[chat_id] = {
            'chat_id': chat_id,
            'title': message.chat.title, 
            'main_message_id': main_msg.message_id,
            'messages_to_delete': msg_ids_to_delete, 
            'start_time': time.time(),
            'duration': duration_sec,
            'participants': [],
            'is_test': is_test,
            'remaining_tags': remaining_tags,
            'main_template': main_template
        }
    except Exception as e:
        print(f"Ошибка старта: {e}")

def stop_collection(message, bot, active_collections, test_collection, *args):
    chat_id = message.chat.id
    col = active_collections.pop(chat_id, None) or test_collection.pop(chat_id, None)
        
    if not col:
        bot.reply_to(message, "❌ Нет активного сбора для завершения.")
        return

    for msg_id in col.get('messages_to_delete', []):
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception: pass 

    _finish_summary(chat_id, bot, col, "Завершено досрочно")

def start_collection(message, bot, active_collections, test_collection, *args):
    _start_generic_collection(message, bot, active_collections, test_collection, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, *args):
    _start_generic_collection(message, bot, active_collections, test_collection, is_test=True)

def handle_join(call, bot, active_collections, test_collection):
    chat_id = call.message.chat.id
    user = call.from_user
    
    col = active_collections.get(chat_id) or test_collection.get(chat_id)
    
    if not col:
        return bot.answer_callback_query(call.id, "❌ Сбор уже завершен или не найден.", show_alert=True)

    if any(p.get('id') == user.id for p in col['participants']):
        return bot.answer_callback_query(call.id, "✅ Ты уже в списке!", show_alert=False)

    col['participants'].append({
        'id': user.id, 
        'username': user.username, 
        'name': user.first_name
    })
    
    count = len(col['participants'])
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"✅ Присоединиться ({count})", callback_data="join_collection"))

    elapsed = int(time.time() - col['start_time'])
    rem = max(0, col['duration'] - elapsed)
    remaining_str = f"{rem // 60:02d}:{rem % 60:02d}"

    try:
        new_text = col['main_template'].format(
            duration=col['duration'] // 60,
            remaining=remaining_str,
            tags=col['remaining_tags'],
            count=count
        )
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=col['main_message_id'],
            text=new_text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            try:
                bot.edit_message_reply_markup(chat_id, col['main_message_id'], reply_markup=markup)
            except: pass

    bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, ты в деле!")

def stop_collection_automatically(chat_id, bot, coll_dict, is_test):
    col = coll_dict.pop(int(chat_id), None)
    if not col: return

    for msg_id in col.get('messages_to_delete', []):
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception: pass 

    _finish_summary(chat_id, bot, col, "Время вышло")

def _finish_summary(chat_id, bot, col, status_text):
    quantity = len(col['participants'])
    is_test = col.get('is_test', False)
    status_icon = "🎉" if quantity > 0 else "😔"
    
    final_text = (
        f"✅ <b>Сбор завершён!</b>\n\n"
        f"👥 Участников: {quantity}\n"
        f"⏰ Статус: {status_text}\n"
        f"{status_icon} {'Удачи всем!' if quantity > 0 else 'Никто не пришел'}"
    )

    bot.send_message(chat_id, final_text, parse_mode="HTML")
    
    if not is_test and quantity > 0:
        save_history_record(col)