import time
import datetime
from .list_functions import show_participants_list, show_menu_periods_in_ls, show_result_by_date
from database.mongo import get_group_by_id
from utils.validators import validate_date

# Функция проверки: похоже ли сообщение на ID группы
def is_potential_group_id(text):
    if not text:
        return False
    t = text.strip()
    return (t.startswith('-') and t[1:].isdigit()) or t.isdigit()

def register_list_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['list'])
    def handle_list(message):
        if message.chat.type in ['group', 'supergroup']:
            chat_id = message.chat.id
            col = active_collections.get(chat_id) or test_collection.get(chat_id)
            if col:
                count = len(col['participants'])
                if count == 0:
                    bot.reply_to(message, "📋 <b>Статус сбора:</b>\nПока никто не присоединился.", parse_mode="HTML")
                else:
                    title = col.get('title', 'Сбор').replace('<', '&lt;').replace('>', '&gt;')
                    lines = [f"📋 <b>Статус сбора: {title}</b>\nУчастников: {count}\n"]
                    for i, p in enumerate(col['participants'], 1):
                        name = p['name'].replace('<', '&lt;').replace('>', '&gt;')
                        username = f" (@{p['username']})" if p.get('username') else ""
                        lines.append(f"{i}. {name}{username}")
                    bot.reply_to(message, "\n".join(lines), parse_mode="HTML")
            else:
                bot.reply_to(message, "ℹ️ В данный момент нет активных сборов.")
        else:
            show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_group_'))
    def list_group_cb(call):
        user_id = call.from_user.id
        chat_id = call.data.replace('list_group_', '')
        
        group = get_group_by_id(chat_id)
        name_group = group['title'] if group else f"Группа {chat_id}"
        
        if user_id not in user_sessions: user_sessions[user_id] = {}
        user_sessions[user_id].update({'list_chat_id': chat_id, 'name_group': name_group, 'step': 'list_choice_period'})
        
        show_menu_periods_in_ls(call, user_sessions[user_id], bot)
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and is_potential_group_id(m.text))
    def handle_direct_id_input(message):
        u_id = message.from_user.id
        session = user_sessions.get(u_id, {})
        current_step = session.get('step', '')

        # Игнорируем, если пользователь в режиме ввода даты или в процессе очистки
        if current_step == 'list_input_date' or current_step.startswith('clean_'):
            return

        chat_id = message.text.strip()
        group = get_group_by_id(chat_id)
        
        if group:
            if u_id not in user_sessions: user_sessions[u_id] = {}
            user_sessions[u_id].update({'list_chat_id': group['chat_id'], 'name_group': group['title'], 'step': 'list_choice_period'})
            show_menu_periods_in_ls(message, user_sessions[u_id], bot)
        else:
            bot.send_message(message.chat.id, "❌ Группа с таким ID не найдена в базе.", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == 'list_back_to_groups')
    def list_back_to_groups_cb(call):
        show_participants_list(call, bot, active_collections, test_collection, known_groups, user_sessions)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == 'list_back_to_periods')
    def list_back_to_periods_cb(call):
        user_id = call.from_user.id
        session = user_sessions.get(user_id, {})
        if session.get('list_chat_id'):
            session['step'] = 'list_choice_period'
            show_menu_periods_in_ls(call, session, bot)
        else:
            bot.answer_callback_query(call.id, "❌ Сессия устарела.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_period_'))
    def list_period_cb(call):
        user_id = call.from_user.id
        session = user_sessions.get(user_id, {})
        chat_id = session.get('list_chat_id')
        if not chat_id:
            bot.answer_callback_query(call.id, "❌ Сессия истекла.", show_alert=True)
            return

        period = call.data.replace('list_period_', '')
        
        if period == "manual":
            session['step'] = "list_input_date"
            bot.edit_message_text("✍️ Введите диапазон дат: <code>ДД-ММ-ГГГГ - ДД-ММ-ГГГГ</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            bot.answer_callback_query(call.id)
            return

        now_ts = time.time()
        now_dt = datetime.datetime.fromtimestamp(now_ts)
        
        if period == "1h":
            begin = now_ts - 3600
            end = now_ts
            p_name = "Последний час"
        elif period == "today":
            begin = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            end = now_ts
            p_name = "Сегодня"
        elif period == "yesterday":
            begin = (now_dt - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            end = begin + 86399
            p_name = "Вчера"
        elif period == "week":
            begin = now_ts - (7 * 86400)
            end = now_ts
            p_name = "Неделя"
        elif period == "month":
            begin = now_ts - (30 * 86400)
            end = now_ts
            p_name = "Месяц (30 дней)"
        elif period == "all":
            begin = None
            end = None
            p_name = "Всё время"

        show_result_by_date(call, chat_id, begin, end, p_name, session, bot)
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'list_input_date')
    def handle_list_manual_date(message):
        u_id = message.from_user.id
        session = user_sessions[u_id]
        chat_id = session.get('list_chat_id')
        text = message.text.strip()

        if " - " in text:
            parts = text.split(" - ")
            d1 = validate_date(parts[0].strip())
            d2 = validate_date(parts[1].strip())
            if d1 and d2:
                begin = d1.timestamp()
                end = d2.replace(hour=23, minute=59, second=59).timestamp()
                show_result_by_date(message, chat_id, begin, end, f"{parts[0]} — {parts[1]}", session, bot)
                session['step'] = "list_choice_period"
            else:
                bot.reply_to(message, "❌ Неверный формат дат.")
        else:
            bot.reply_to(message, "✍️ Используйте разделитель ' - '.")