import datetime
from database.mongo import get_group_by_id, delete_history_record_by_id
from utils.validators import validate_date
from .clean_functions import (
    handle_clean, show_clean_periods_menu, show_clean_hours_menu, 
    show_records_for_cleaning, ask_confirm_clean, execute_delete
)

def register_clean_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['clean'])
    def clean_command(message):
        if message.chat.type == 'private':
            handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and 
                         user_sessions.get(m.from_user.id, {}).get('step') == 'clean_wait_group_id')
    def handle_manual_id_for_clean(message):
        chat_id_raw = message.text.strip()
        try:
            chat_id = int(chat_id_raw)
        except ValueError:
            bot.reply_to(message, "❌ ID группы должен быть числом.")
            return

        group = get_group_by_id(chat_id)
        if group:
            u_id = message.from_user.id
            if u_id not in user_sessions: user_sessions[u_id] = {}
            
            user_sessions[u_id].update({
                'clean_chat_id': chat_id,
                'step': 'clean_choice_period'
            })
            show_clean_periods_menu(message, user_sessions[u_id], bot, edit=False)
        else:
            bot.reply_to(message, "❌ Группа не найдена. Убедитесь, что бот там есть.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_group_'))
    def handle_clean_group_choice(call):
        chat_id = int(call.data.replace('clean_group_', ''))
        u_id = call.from_user.id
        if u_id not in user_sessions: user_sessions[u_id] = {}
        user_sessions[u_id]['clean_chat_id'] = chat_id
        show_clean_periods_menu(call, user_sessions[u_id], bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_view_'))
    def handle_clean_view(call):
        u_id = call.from_user.id
        session = user_sessions.get(u_id)
        if not session: return
        
        choice = call.data.replace('clean_view_', '')
        now = datetime.datetime.now()
        chat_id = session.get('clean_chat_id')

        if choice == 'today':
            b = int(now.replace(hour=0, minute=0, second=0).timestamp())
            show_clean_hours_menu(call, bot, b, int(now.timestamp()), "Сегодня")
        elif choice == 'yesterday':
            yest = now - datetime.timedelta(days=1)
            b = int(yest.replace(hour=0, minute=0, second=0).timestamp())
            e = int(yest.replace(hour=23, minute=59, second=59).timestamp())
            show_clean_hours_menu(call, bot, b, e, "Вчера")
        elif choice == 'week':
            b = int((now - datetime.timedelta(days=7)).timestamp())
            # ИСПРАВЛЕНО: Правильный порядок аргументов
            show_records_for_cleaning(call, bot, chat_id, b, int(now.timestamp()), "Неделя", user_sessions)
        elif choice == 'month':
            b = int((now - datetime.timedelta(days=30)).timestamp())
            show_records_for_cleaning(call, bot, chat_id, b, int(now.timestamp()), "Месяц", user_sessions)
        elif choice == 'all':
            show_records_for_cleaning(call, bot, chat_id, 0, int(now.timestamp()), "Всё время", user_sessions)
        elif choice == 'manual':
            session['step'] = 'clean_input_date'
            bot.edit_message_text("✍️ Введите период (ДД.ММ.ГГ - ДД.ММ.ГГ):", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_drill_'))
    def handle_clean_drill(call):
        parts = call.data.split('_')
        b, e, label = int(parts[2]), int(parts[3]), parts[4]
        chat_id = user_sessions[call.from_user.id].get('clean_chat_id')
        # ИСПРАВЛЕНО: Правильный порядок аргументов
        show_records_for_cleaning(call, bot, chat_id, b, e, label, user_sessions)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('clean_rec_'))
    def handle_delete_specific_record(call):
        rec_id = call.data.replace('clean_rec_', '')
        if delete_history_record_by_id(rec_id):
            bot.answer_callback_query(call.id, "✅ Запись удалена")
            
            # ИСПРАВЛЕНО: Обновляем список, а не выкидываем в меню периодов
            u_id = call.from_user.id
            session = user_sessions.get(u_id, {})
            chat_id = session.get('clean_chat_id')
            begin = session.get('clean_begin')
            end = session.get('clean_end')
            label = session.get('clean_period_name', 'Период')
            
            if chat_id and begin and end:
                show_records_for_cleaning(call, bot, chat_id, begin, end, label, user_sessions)
            else:
                show_clean_periods_menu(call, session, bot)
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

    @bot.callback_query_handler(func=lambda call: call.data == 'clean_back_to_periods')
    def handle_back_periods(call):
        show_clean_periods_menu(call, user_sessions.get(call.from_user.id, {}), bot)
    
    @bot.callback_query_handler(func=lambda call: call.data == "clean_back_to_groups")
    def handle_clean_back_to_groups(call):
        u_id = call.from_user.id
        if u_id in user_sessions:
            user_sessions[u_id]['step'] = 'clean_wait_group_id'
        
        handle_clean(call.message, bot, active_collections, test_collection, known_groups, user_sessions, edit=True)
        bot.answer_callback_query(call.id)
    @bot.message_handler(func=lambda m: m.chat.type == 'private' and user_sessions.get(m.from_user.id, {}).get('step') == 'clean_input_date')
    def handle_clean_manual_date(message):
        u_id = message.from_user.id
        session = user_sessions.get(u_id)
        if not session:
            bot.reply_to(message, "❌ Сессия истекла. Начните заново с /clean")
            return
            
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
                    
                    # Показываем список записей за выбранный ручной период
                    show_records_for_cleaning(message, bot, chat_id, begin, end, p_name, user_sessions)
                    session['step'] = "clean_choice_period"
                    return
                else:
                    bot.reply_to(message, "❌ Не удалось распознать даты. (Например: 13.04.26 - 14.04.26)")
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