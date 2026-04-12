import time
import datetime
from .clean_functions import handle_clean, show_clean_actions, ask_confirm_clean, execute_delete
from database.mongo import get_group_by_id
from utils.validators import validate_date

def register_clean_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def clean_command(message):
        if message.chat.type == 'private':
            handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions)
        else:
            bot.reply_to(message, "⚠️ Очистка доступна только в ЛС.")

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and 
                         user_sessions.get(m.from_user.id, {}).get('step') == 'clean_wait_group_id' and 
                         (m.text.strip().startswith('-') or m.text.strip().isdigit()))
    def handle_clean_id_input(message):
        chat_id = message.text.strip()
        group = get_group_by_id(chat_id)
        
        if group:
            u_id = message.from_user.id
            if u_id not in user_sessions: user_sessions[u_id] = {}
            user_sessions[u_id].update({
                'clean_chat_id': group['chat_id'], 
                'name_group': group['title'], 
                'step': 'clean_choice_period'
            })
            show_clean_actions(message, user_sessions[u_id], bot)
        else:
            bot.send_message(message.chat.id, "❌ Группа для очистки с таким ID не найдена.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_group_'))
    def clean_group_cb(call):
        user_id = call.from_user.id
        chat_id = call.data.replace('clean_group_', '')
        
        group = get_group_by_id(chat_id)
        name_group = group['title'] if group else f"Группа {chat_id}"
        
        if user_id not in user_sessions: user_sessions[user_id] = {}
        user_sessions[user_id].update({'clean_chat_id': chat_id, 'name_group': name_group, 'step': 'clean_choice_period'})
        
        show_clean_actions(call, user_sessions[user_id], bot)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "clean_back_to_list")
    def clean_back_cb(call):
        handle_clean(call.message, bot, None, None, None, user_sessions)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "clean_period_manual")
    def clean_manual_cb(call):
        u_id = call.from_user.id
        user_sessions[u_id]['step'] = 'clean_input_date'
        bot.edit_message_text("✍️ <b>Введите диапазон дат для УДАЛЕНИЯ</b>:\n<code>ДД-ММ-ГГГГ - ДД-ММ-ГГГГ</code>", 
                              call.message.chat.id, call.message.message_id, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_period_'))
    def clean_period_cb(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if not session: return
        
        period = call.data.replace('clean_period_', '')
        chat_id = session.get('clean_chat_id')
        
        now = datetime.datetime.now()
        now_ts = now.timestamp()
        
        if period == "1h":
            begin = now_ts - 3600
            p_name = "Последний час"
        elif period == "today":
            begin = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            p_name = "Сегодня"
        elif period == "yesterday":
            begin = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            end_yesterday = begin + 86399
            ask_confirm_clean(call, chat_id, begin, end_yesterday, "Вчера", session, bot)
            bot.answer_callback_query(call.id)
            return
        elif period == "week":
            begin = now_ts - (7 * 86400)
            p_name = "Неделя"
        elif period == "month":
            begin = now_ts - (30 * 86400)
            p_name = "Месяц (30 дней)"
        elif period == "all":
            begin = None
            p_name = "Всё время"

        ask_confirm_clean(call, chat_id, begin, now_ts if begin else None, p_name, session, bot)
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'clean_input_date')
    def handle_clean_manual_date(message):
        u_id = message.from_user.id
        session = user_sessions[u_id]
        chat_id = session.get('clean_chat_id')
        text = message.text.strip()

        if " - " in text:
            parts = text.split(" - ")
            d1 = validate_date(parts[0].strip())
            d2 = validate_date(parts[1].strip())
            if d1 and d2:
                begin = d1.timestamp()
                end = d2.replace(hour=23, minute=59, second=59).timestamp()
                ask_confirm_clean(message, chat_id, begin, end, f"{parts[0]} — {parts[1]}", session, bot)
                session['step'] = "clean_choice_period"
            else:
                bot.reply_to(message, "❌ Неверный формат.")
        else:
            bot.reply_to(message, "✍️ Используйте разделитель ' - '.")

    @bot.callback_query_handler(func=lambda call: call.data == "clean_confirm_yes")
    def clean_confirm_yes(call):
        execute_delete(call, bot, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data == "clean_confirm_no")
    def clean_confirm_no(call):
        session = user_sessions.get(call.from_user.id, {})
        show_clean_actions(call, session, bot)
        bot.answer_callback_query(call.id, "Отменено")