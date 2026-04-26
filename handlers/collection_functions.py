import time
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.mongo import (
    get_all_members_ids, get_combined_settings, save_known_group, 
    save_user_id, save_history_record, get_group_member_count
)
from utils.messages import (
    START_MESSAGES_MANDATORY, TEST_MESSAGES, COLLECT_BODY_ACTIVE, 
    COLLECT_ALREADY_RUNNING, TEST_BODY_ACTIVE
)

from config.settings import EMOJI_LIST, TAGS_CHUNK_SIZE

def _start_generic_collection(message, bot, collection_dict, is_test=False):
    chat_id = message.chat.id
    admin_id = message.from_user.id

    if chat_id in collection_dict:
        col = collection_dict[chat_id]
        elapsed_min = int((time.time() - col['start_time']) // 60)
        total_min = col['duration'] // 60
        rem_min = max(0, total_min - elapsed_min)
        
        try:
            bot.send_message(chat_id, COLLECT_ALREADY_RUNNING.format(
                count=len(col['participants']),
                elapsed=elapsed_min,
                remaining=f"{rem_min} мин"
            ), parse_mode="HTML")
        except:
            bot.send_message(chat_id, "⚠️ Сбор уже запущен!")
        return

    member_ids = list(set(get_all_members_ids(chat_id)))
    bot_me = bot.get_me()
    if bot_me.id in member_ids:
        member_ids.remove(bot_me.id)

    save_known_group(chat_id, message.chat.title, member_count=len(member_ids))
    if not message.from_user.is_bot:
        save_user_id(chat_id, admin_id, message.from_user.username)

    configs = get_combined_settings(chat_id, admin_id)
    duration_min = configs['duration'] // 60
    
    precursor_templates = TEST_MESSAGES if is_test else START_MESSAGES_MANDATORY
    main_template = TEST_BODY_ACTIVE if is_test else COLLECT_BODY_ACTIVE

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

    sent_msg = None
    
    for i, template in enumerate(precursor_templates):
        tags_string = f"\n\n{tag_chunks[i]}\n" if i < len(tag_chunks) else ""
        
        try:
            full_text = template.format(
                duration=duration_min,
                tags=tags_string
            )
            bot.send_message(chat_id, full_text, parse_mode="HTML")
            time.sleep(0.4) 
        except Exception as e:
            print(f"❌ Ошибка отправки прекурсора {i}: {e}")
    remaining_tags = ""
    if len(tag_chunks) > len(precursor_templates):
        remaining_tags = "\n\n" + "\n".join(tag_chunks[len(precursor_templates):]) + "\n"

    try:
        main_text = main_template.format(
            duration=duration_min,
            tags=remaining_tags
        )
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Присоединиться (0)", callback_data="join_collection"))

        sent_msg = bot.send_message(chat_id, main_text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"❌ Ошибка отправки главного сообщения: {e}")

    if sent_msg:
        collection_dict[chat_id] = {
            'main_message_id': sent_msg.message_id,
            'chat_id': chat_id,
            'title': message.chat.title,
            'start_time': time.time(),
            'duration': configs['duration'],
            'participants': [],
            'admin_id': admin_id,
            'is_test': is_test
        }

def stop_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    chat_id = message.chat.id
    col = active_collections.pop(chat_id, None) or test_collection.pop(chat_id, None)
    is_test = col.get('is_test', False) if col else False
        
    if not col:
        bot.reply_to(message, "❌ Нет активного сбора.")
        return

    quantity = len(col['participants'])
    status_icon = "🎉" if quantity > 0 else "😔"
    
    final_text = (
        f"✅ <b>Сбор завершён!</b>\n\n"
        f"👥 Участников: {quantity}\n"
        f"⏰ Статус: Завершено досрочно\n"
        f"{status_icon} {'Спасибо всем!' if quantity > 0 else 'Никто не пришел'}"
    )

    bot.send_message(chat_id, final_text, parse_mode="HTML")
    if not is_test and quantity > 0:
        save_history_record(col)

def start_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if message.chat.type == 'private':
        bot.reply_to(message, "🏰 Команда только для групп.")
        return
    _start_generic_collection(message, bot, active_collections, is_test=False)

def start_test_collection(message, bot, active_collections, test_collection, known_groups, user_sessions):
    if message.chat.type == 'private':
        bot.reply_to(message, "🧪 Команда только для групп.")
        return
    _start_generic_collection(message, bot, test_collection, is_test=True)

def handle_join(call, bot, active_collections, test_collection):
    chat_id = call.message.chat.id
    col = active_collections.get(int(chat_id)) or test_collection.get(int(chat_id))
    
    if not col:
        bot.answer_callback_query(call.id, "❌ Сбор уже завершен или не найден.", show_alert=True)
        return

    user = call.from_user
    if any(p.get('id') == user.id for p in col['participants']):
        bot.answer_callback_query(call.id, "✅ Вы уже в деле!")
        return

    col['participants'].append({
        'id': user.id, 
        'username': user.username, 
        'name': user.first_name
    })
    
    count = len(col['participants'])
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"✅ Присоединиться ({count})", callback_data="join_collection"))
    
    try:
        bot.edit_message_reply_markup(chat_id, col['main_message_id'], reply_markup=markup)
        bot.answer_callback_query(call.id, f"⚔️ {user.first_name}, вы в списке!")
    except Exception:
        bot.answer_callback_query(call.id, "✅ Готово!")

def stop_collection_automatically(chat_id, bot, coll_dict, is_test):
    col = coll_dict.pop(int(chat_id), None)
    if not col: return

    quantity = len(col['participants'])
    final_text = (
        f"✅ <b>Сбор завершён!</b>\n\n"
        f"👥 Участников: {quantity}\n"
        f"⏰ Статус: Время вышло\n"
        f"{'🎉 Удачи!' if quantity > 0 else '😔 Сбор не удался'}"
    )

    bot.send_message(chat_id, final_text, parse_mode="HTML")
    if not is_test and quantity > 0:
        save_history_record(col)