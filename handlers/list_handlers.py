import datetime
from telebot import types
from database.mongo import get_group_by_id
from utils.validators import validate_date
from .list_functions import (
    show_participants_list, 
    show_menu_periods_in_ls, 
    show_result_by_date,
    show_all_time_menu,
    show_weeks_of_month_menu, 
    show_days_of_week_menu,    
    show_hours_of_day_menu     
)

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

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and 
                         is_potential_group_id(m.text) and 
                         user_sessions.get(m.from_user.id, {}).get('step') == 'list_wait_group_id')
    def handle_direct_id_input(message):
        chat_id = message.text.strip()
        group = get_group_by_id(chat_id)
        
        if group:
            u_id = message.from_user.id
            if u_id not in user_sessions: user_sessions[u_id] = {}
            user_sessions[u_id].update({
                'list_chat_id': group['chat_id'], 
                'name_group': group['title'], 
                'step': 'list_choice_period'
            })
            show_menu_periods_in_ls(message, user_sessions[u_id], bot)
        else:
            bot.send_message(message.chat.id, "❌ Группа с таким ID не найдена в базе.", parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data == 'list_back_to_groups')
    def list_back_to_groups_cb(call):
        show_participants_list(call, bot, active_collections, test_collection, known_groups, user_sessions)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "list_back_to_periods")
    def handle_back_to_main(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if session:
            session['step'] = 'list_choice_period'  
            show_menu_periods_in_ls(call, session, bot)
        else:
            bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_period_'))
    def handle_specific_period(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if not session: return
        data = call.data.split('_', 4)
        chat_id = session.get('list_chat_id')
        back_cb = session.get('list_last_menu_cb', 'list_back_to_periods')
        show_result_by_date(call, chat_id, float(data[2]), float(data[3]), data[4], session, bot, back_cb=back_cb)
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and not m.text.startswith('/') and user_sessions.get(m.from_user.id, {}).get('step') == 'list_input_date')
    def handle_list_manual_date(message):
        u_id = message.from_user.id
        if u_id not in user_sessions:
            bot.reply_to(message, "❌ Сессия истекла. Начните заново с команды /list")
            return
        session = user_sessions[u_id]
        chat_id = session.get('list_chat_id')
        raw = message.text.strip().replace(" ", "").replace("-", ".").replace("/", ".")
        parts = raw.split(".")
        if len(parts) >= 6:
            try:
                date_str1 = f"{parts[0]}.{parts[1]}.{parts[2]}"
                date_str2 = f"{parts[3]}.{parts[4]}.{parts[5]}"
                d1 = validate_date(date_str1)
                d2 = validate_date(date_str2)
            
                if d1 and d2:
                    begin = d1.timestamp()
                    end = d2.replace(hour=23, minute=59, second=59).timestamp()
                    p_name = f"{date_str1} — {date_str2}"
                    show_result_by_date(message, chat_id, begin, end, p_name, session, bot, back_cb="list_back_to_periods")
                    session['step'] = "list_choice_period"
                    return
                else:
                    bot.reply_to(message, "❌ Не удалось распознать даты. Убедитесь, что они реальны (например, 13.04.26).")
                    return
            except Exception as e:
                print(f"Ошибка парсинга даты: {e}")
                bot.reply_to(message, "❌ Произошла ошибка при обработке даты.")
                return

        error_text = (
            "❌ <b>Неверный формат.</b>\n\n"
            "Введите две даты слитно через точки:\n"
            "<code>13.04.26.14.04.26</code>\n\n"
            "Или через дефис:\n"
            "<code>13.04.2026 - 14.04.2026</code>"
        )
        bot.reply_to(message, error_text, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_view_'))
    def handle_view_choice(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if not session: 
            bot.answer_callback_query(call.id, "Сессия истекла")
            return

        choice = call.data.replace('list_view_', '')
        chat_id = session.get('list_chat_id')
        now_dt = datetime.datetime.now()

        session['list_parent_mview'] = 'list_back_to_periods'
        session['list_parent_wview'] = 'list_back_to_periods'

        if choice == 'today':
            session['list_last_menu_cb'] = call.data
            b = int(now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
            e = int(now_dt.timestamp())
            show_hours_of_day_menu(call, bot, b, e, "Сегодня", back_cb="list_back_to_periods")
            
        elif choice == 'week':
            session['list_parent_wview'] = call.data
            session['list_last_menu_cb'] = call.data
            b = int((now_dt - datetime.timedelta(days=6)).replace(hour=0, minute=0, second=0).timestamp())
            e = int(now_dt.timestamp())
            show_days_of_week_menu(call, bot, b, e, "7 дней", back_cb="list_back_to_periods")
            
        elif choice == 'month':
            session['list_parent_mview'] = call.data
            session['list_last_menu_cb'] = call.data
            f_day = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if f_day.month == 12: n_m = f_day.replace(year=f_day.year+1, month=1)
            else: n_m = f_day.replace(month=f_day.month+1)
            l_day = n_m - datetime.timedelta(seconds=1)
            show_weeks_of_month_menu(call, bot, int(f_day.timestamp()), int(l_day.timestamp()), f_day.strftime("%m.%Y"), back_cb="list_back_to_periods")
            
        elif choice == 'yesterday':
            session['list_last_menu_cb'] = call.data
            yest = now_dt - datetime.timedelta(days=1)
            b = int(yest.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
            e = int(yest.replace(hour=23, minute=59, second=59, microsecond=0).timestamp())
            show_hours_of_day_menu(call, bot, b, e, "Вчера", back_cb="list_back_to_periods")
            
        elif choice == 'all':
            session['list_last_menu_cb'] = call.data
            show_all_time_menu(call, session, bot)    
            
        elif choice == 'manual':
            session['step'] = 'list_input_date'
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="list_back_to_periods"))
            bot.edit_message_text("✍️ Введите период (ДД.ММ.ГГ - ДД.ММ.ГГ):", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('list_mview_', 'list_wview_', 'list_dview_')))
    def handle_drilldown(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id, {})
        data = call.data.split('_', 4) 
        v_type, b_ts, e_ts, label = data[1], data[2], data[3], data[4]
        
        session['list_last_menu_cb'] = call.data
        
        if v_type == 'mview':
            session['list_parent_mview'] = call.data
            show_weeks_of_month_menu(call, bot, b_ts, e_ts, label, back_cb="list_view_all")
        elif v_type == 'wview':
            session['list_parent_wview'] = call.data
            back_cb = session.get('list_parent_mview', "list_view_all")
            show_days_of_week_menu(call, bot, b_ts, e_ts, label, back_cb=back_cb)
        elif v_type == 'dview':
            back_cb = session.get('list_parent_wview', "list_view_all")
            chat_id = session.get('list_chat_id')
            show_hours_of_day_menu(call, bot, b_ts, e_ts, label, chat_id, u_id, back_cb=back_cb)