import datetime
from database.mongo import get_group_by_id, delete_history_record_by_id
from utils.validators import validate_date
from .clean_functions import (
    handle_clean, show_clean_periods_menu, show_clean_all_time_menu,
    show_clean_weeks_menu, show_clean_days_menu, show_clean_hours_menu,
    show_records_for_cleaning, ask_confirm_clean, execute_delete
)

def register_clean_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def clean_command(message):
        if message.chat.type == 'private':
            handle_clean(message, bot, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_group_'))
    def handle_clean_group_choice(call):
        chat_id = int(call.data.split('_')[2])
        user_id = call.from_user.id
        if user_id not in user_sessions: user_sessions[user_id] = {}
        user_sessions[user_id]['clean_chat_id'] = chat_id
        show_clean_periods_menu(call, user_sessions[user_id], bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_period_'))
    def handle_clean_period_choice(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if not session: return
        
        choice = call.data.replace('clean_period_', '')
        chat_id = session.get('clean_chat_id')
        now = datetime.datetime.now()

        if choice == 'today':
            b = int(now.replace(hour=0, minute=0, second=0).timestamp())
            show_records_for_cleaning(call, bot, chat_id, b, int(now.timestamp()), "Сегодня", user_sessions)
        elif choice == 'yesterday':
            y = now - datetime.timedelta(days=1)
            b = int(y.replace(hour=0, minute=0, second=0).timestamp())
            e = int(y.replace(hour=23, minute=59, second=59).timestamp())
            show_records_for_cleaning(call, bot, chat_id, b, e, "Вчера", user_sessions)
        elif choice == 'week':
            b = int((now - datetime.timedelta(days=7)).timestamp())
            show_records_for_cleaning(call, bot, chat_id, b, int(now.timestamp()), "Неделя", user_sessions)
        elif choice == 'month':
            b = int((now - datetime.timedelta(days=30)).timestamp())
            show_records_for_cleaning(call, bot, chat_id, b, int(now.timestamp()), "Месяц", user_sessions)
        elif choice == 'all':
            show_clean_all_time_menu(call, session, bot)
        elif choice == 'manual':
            session['step'] = 'clean_input_date'
            bot.edit_message_text("✍️ Введите период (ДД.ММ.ГГ - ДД.ММ.ГГ):", call.message.chat.id, call.message.message_id)
        
        elif '_' in choice:
            parts = choice.split('_', 2) 
            b, e, label = int(parts[0]), int(parts[1]), parts[2]
            show_records_for_cleaning(call, bot, chat_id, b, e, label, user_sessions)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'clean_input_date')
    def handle_clean_manual_date(message):
        u_id = message.from_user.id
        if u_id not in user_sessions:
            bot.reply_to(message, "❌ Сессия истекла. Начните заново с команды /clean")
            return
        
        session = user_sessions[u_id]
        chat_id = session.get('clean_chat_id')
        raw = message.text.strip().replace(" ", "").replace("-", ".").replace("/", ".")
        parts = raw.split(".")
        
        if len(parts) >= 6:
            try:
                date_str1 = f"{parts[0]}.{parts[1]}.{parts[2]}"
                date_str2 = f"{parts[3]}.{parts[4]}.{parts[5]}"
                d1 = validate_date(date_str1)
                d2 = validate_date(date_str2)
            
                if d1 and d2:
                    begin = int(d1.timestamp())
                    end = int(d2.replace(hour=23, minute=59, second=59).timestamp())
                    p_name = f"{date_str1} — {date_str2}"
                    
                    show_records_for_cleaning(message, bot, chat_id, begin, end, p_name, user_sessions)
                    session['step'] = "clean_choice_period"
                    return
                else:
                    bot.reply_to(message, "❌ Не удалось распознать даты. Убедитесь, что они реальны.")
                    return
            except Exception as e:
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith(('clean_mview_', 'clean_wview_', 'clean_dview_')))
    def handle_clean_drilldown(call):
        data = call.data.split('_', 3)
        v_type, b, e, label = data[1], int(data[2]), int(data[3]), data[4]
        if v_type == 'mview': show_clean_weeks_menu(call, bot, b, e, label)
        elif v_type == 'wview': show_clean_days_menu(call, bot, b, e, label)
        elif v_type == 'dview': show_clean_hours_menu(call, bot, b, e, label)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_rec_'))
    def handle_single_delete(call):
        parts = call.data.split('_')
        rec_id = parts[2] 
        
        user_id = call.from_user.id
        session = user_sessions.get(user_id, {})
        chat_id = session.get('clean_chat_id')
        begin = session.get('clean_view_begin')
        end = session.get('clean_view_end')
        label = session.get('clean_view_label')

        if delete_history_record_by_id(rec_id):
            bot.answer_callback_query(call.id, "✅ Запись удалена")

            if all([chat_id, begin, end, label]):
                show_records_for_cleaning(call, bot, chat_id, begin, end, label, user_sessions)
            else:
                handle_clean(call.message, bot, user_sessions, edit=True)
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка при удалении", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_bulk_'))
    def handle_bulk_confirm_request(call):
        parts = call.data.split('_')
        chat_id = user_sessions[call.from_user.id].get('clean_chat_id')
        ask_confirm_clean(call, chat_id, int(parts[2]), int(parts[3]), "выбранный период", user_sessions[call.from_user.id], bot)

    @bot.callback_query_handler(func=lambda call: call.data == 'clean_confirm_yes')
    def handle_final_yes(call):
        execute_delete(call, bot, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data == 'clean_back_to_groups')
    def handle_back_groups(call):
        handle_clean(call.message, bot, user_sessions, edit=True)

    @bot.callback_query_handler(func=lambda call: call.data == 'clean_back_to_periods')
    def handle_back_periods(call):
        show_clean_periods_menu(call, user_sessions.get(call.from_user.id, {}), bot)