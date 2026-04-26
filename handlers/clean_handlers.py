import datetime
from telebot import types
from database.mongo import get_group_by_id, delete_history_record_by_id
from utils.validators import validate_date
from .clean_functions import (
    handle_clean, show_clean_periods_menu, show_clean_all_time_menu,
    show_clean_weeks_menu, show_clean_days_menu, show_clean_hours_menu,
    show_records_for_cleaning, ask_confirm_clean, execute_delete
)

def get_cancel_kbd():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("❌ Отмена")
    return markup

def register_clean_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def clean_command(message):
        if message.chat.type == 'private':
            handle_clean(message, bot, user_sessions)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'clean_wait_group_id')
    def handle_text_group_id(message):
        u_id = message.from_user.id
        group_id = message.text.strip()
        
        if u_id not in user_sessions: 
            user_sessions[u_id] = {}
            
        group = get_group_by_id(group_id)
        name_group = group['title'] if group else f"Группа {group_id}"
        
        user_sessions[u_id].update({
            'clean_chat_id': group_id, 
            'name_group': name_group, 
            'step': 'clean_choice_period'
        })
        
        show_clean_periods_menu(message, user_sessions[u_id], bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_group_'))
    def handle_clean_group_choice(call):
        chat_id = call.data.replace('clean_group_', '')
        user_id = call.from_user.id
        
        group = get_group_by_id(chat_id)
        name_group = group['title'] if group else f"Группа {chat_id}"
        
        if user_id not in user_sessions: 
            user_sessions[user_id] = {}
            
        user_sessions[user_id].update({
            'clean_chat_id': chat_id, 
            'name_group': name_group, 
            'step': 'clean_choice_period'
        })
        
        show_clean_periods_menu(call, user_sessions[user_id], bot)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_view_'))
    def handle_clean_view_choice(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if not session: 
            bot.answer_callback_query(call.id, "Сессия истекла")
            return

        choice = call.data.replace('clean_view_', '')
        chat_id = session.get('clean_chat_id')
        
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)

        # Сбрасываем историю родителей
        session['clean_parent_mview'] = 'clean_back_to_periods'
        session['clean_parent_wview'] = 'clean_back_to_periods'

        if choice == 'today':
            session['clean_last_menu_cb'] = call.data
            b = int(today_start.timestamp())
            e = int(now_dt.timestamp())
            show_clean_hours_menu(call, bot, b, e, "Сегодня", back_cb="clean_back_to_periods")
            
        elif choice == 'week':
            session['clean_parent_wview'] = call.data
            session['clean_last_menu_cb'] = call.data
            b = int((now_dt - datetime.timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
            e = int(now_dt.timestamp())
            show_clean_days_menu(call, bot, b, e, "7 дней", back_cb="clean_back_to_periods")
            
        elif choice == 'month':
            session['clean_parent_mview'] = call.data
            session['clean_last_menu_cb'] = call.data
            f_day = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if f_day.month == 12: 
                n_m = f_day.replace(year=f_day.year+1, month=1)
            else: 
                n_m = f_day.replace(month=f_day.month+1)
            l_day = n_m - datetime.timedelta(seconds=1)
            show_clean_weeks_menu(call, bot, int(f_day.timestamp()), int(l_day.timestamp()), f_day.strftime("%m.%Y"), back_cb="clean_back_to_periods")
            
        elif choice == 'yesterday':
            session['clean_last_menu_cb'] = call.data
            yesterday = today_start - datetime.timedelta(days=1)
            b = int(yesterday.timestamp())
            e = int(today_start.timestamp()) - 1
            show_clean_hours_menu(call, bot, b, e, "Вчера", back_cb="clean_back_to_periods")
            
        elif choice == 'all':
            session['clean_last_menu_cb'] = call.data
            show_clean_all_time_menu(call, session, bot)    
            
        elif choice == 'manual':
            session['step'] = 'clean_input_date'
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
            bot.edit_message_text("✍️ Введите период (ДД.ММ.ГГ - ДД.ММ.ГГ):", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
        bot.answer_callback_query(call.id)
        
    @bot.callback_query_handler(func=lambda call: call.data == "clean_back_to_periods")
    def handle_back_to_periods_clean(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if session:
            session['step'] = 'clean_choice_period' 
            show_clean_periods_menu(call, session, bot)
        else:
            bot.answer_callback_query(call.id, "Сессия истекла", show_alert=True)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_period_'))
    def handle_clean_specific_period(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if not session: return
        data = call.data.split('_', 4)
        chat_id = session.get('clean_chat_id')
        
        back_cb = session.get('clean_last_menu_cb', 'clean_back_to_periods')
        show_records_for_cleaning(call, bot, chat_id, float(data[2]), float(data[3]), data[4], user_sessions, back_cb=back_cb)
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'clean_input_date')
    def handle_clean_manual_date(message):
        u_id = message.from_user.id
        session = user_sessions.get(u_id)
        if not session:
            bot.reply_to(message, "❌ Сессия истекла. Введите /clean снова.")
            return
    
        chat_id = session.get('clean_chat_id')
        raw = message.text.strip().replace(" ", "").replace("-", ".").replace("/", ".")
        parts = raw.split(".")
    
        if len(parts) >= 6:
            try:
                d1 = validate_date(f"{parts[0]}.{parts[1]}.{parts[2]}")
                d2 = validate_date(f"{parts[3]}.{parts[4]}.{parts[5]}")
            
                if d1 and d2:
                    begin = int(d1.timestamp())
                    end = int(d2.replace(hour=23, minute=59, second=59).timestamp())
                
                    label = f"{parts[0]}.{parts[1]} - {parts[3]}.{parts[4]}"
                    show_records_for_cleaning(message, bot, chat_id, begin, end, label, user_sessions, back_cb="clean_back_to_periods")
                    session['step'] = "clean_choice_period"
                    return
            except Exception:
                pass

        bot.reply_to(
            message, 
            "❌ <b>Неверный формат!</b>\nИспользуйте: <code>ДД.ММ.ГГ - ДД.ММ.ГГ</code>\nПример: <code>10.04.26 - 12.04.26</code>", 
            parse_mode="HTML"
        )
        
    @bot.callback_query_handler(func=lambda call: call.data.startswith(('clean_mview_', 'clean_wview_', 'clean_dview_')))
    def handle_drilldown(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id, {})
        data = call.data.split('_', 4)
        v_type, b_ts, e_ts, label = data[1], data[2], data[3], data[4]
        
        session['clean_last_menu_cb'] = call.data
        if v_type == 'custom_interval':
            session['step'] = 'clean_input_date'
            
            bot.send_message(
                call.message.chat.id, 
                "Режим ввода активирован. Нажмите кнопку ниже для выхода:", 
                reply_markup=get_cancel_kbd()
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
            bot.edit_message_text(
                "✍️ <b>Введите период для ОЧИСТКИ</b> (ДД.ММ.ГГ - ДД.ММ.ГГ):", 
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=markup, 
                parse_mode="HTML"
            )

        if v_type == 'mview':
            session['clean_parent_mview'] = call.data
            show_clean_weeks_menu(call, bot, b_ts, e_ts, label, back_cb="clean_view_all_time")
        elif v_type == 'wview':
            session['clean_parent_wview'] = call.data
            back_cb = session.get('clean_parent_mview', "clean_view_all_time")
            show_clean_days_menu(call, bot, b_ts, e_ts, label, back_cb=back_cb)
        elif v_type == 'dview':
            back_cb = session.get('clean_parent_wview', "clean_view_all_time")
            chat_id = session.get('clean_chat_id')
            show_clean_hours_menu(call, bot, b_ts, e_ts, label, chat_id, u_id, back_cb=back_cb)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_rec_'))
    def handle_single_delete(call):
        rec_id = call.data.split('_')[2]
        session = user_sessions.get(call.from_user.id, {})
        if delete_history_record_by_id(rec_id):
            bot.answer_callback_query(call.id, "✅ Удалено")
            back_cb = session.get('clean_last_menu_cb', 'clean_back_to_periods')
            show_records_for_cleaning(call, bot, session.get('clean_chat_id'), session.get('clean_view_begin'), session.get('clean_view_end'), session.get('clean_view_label'), user_sessions, back_cb=back_cb)
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_bulk_'))
    def handle_bulk_confirm(call):
        parts = call.data.split('_')
        session = user_sessions.get(call.from_user.id, {})
        # При отмене массового удаления мы тоже возвращаемся туда, откуда пришли
        back_cb = session.get('clean_last_menu_cb', 'clean_back_to_periods')
        ask_confirm_clean(call, session.get('clean_chat_id'), int(parts[2]), int(parts[3]), "выбранный период", session, bot, back_cb=back_cb)

    @bot.callback_query_handler(func=lambda call: call.data == 'clean_confirm_yes')
    def handle_final_yes(call):
        execute_delete(call, bot, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data == 'clean_back_to_groups')
    def handle_back_groups(call):
        handle_clean(call.message, bot, user_sessions, edit=True)