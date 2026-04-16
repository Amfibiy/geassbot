import datetime
from telebot import types
from database.mongo import delete_history_records, delete_history_record_by_id, load_history_for_chat,get_combined_settings
from utils.helpers import get_admin_groups,get_localized_timestamps

def escape_html(text):
    if not text: return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def handle_clean(message, bot, user_sessions, edit=False):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    if not admin_groups:
        text = "📭 <b>Список групп пуст.</b>\nДобавьте бота в группу и выдайте права администратора."
        if edit:
            bot.edit_message_text(text, message.chat.id, message.message_id, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, text, parse_mode="HTML")
        return

    user_sessions[user_id]['step'] = 'clean_wait_group_id'
    text = "🧹 <b>Выберите группу для очистки:</b>\n<i>Нажмите на кнопку или отправьте ID группы текстом.</i>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = escape_html(g.get('title', 'Группа'))
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(f"{i}. {title}", callback_data=f"clean_group_{c_id}"))
    
    if edit:
        bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_clean_periods_menu(message_or_call, session, bot):
    chat_id = session.get('clean_chat_id')
    admin_id = message_or_call.from_user.id
    configs = get_combined_settings(chat_id, admin_id)
    
    t_b, t_e = get_localized_timestamps(configs['timezone'], "today")
    y_b, y_e = get_localized_timestamps(configs['timezone'], "yesterday")

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📅 Сегодня", callback_data=f"clean_period_{t_b}_{t_e}_Сегодня"),
        types.InlineKeyboardButton("🗓 Вчера", callback_data=f"clean_period_{y_b}_{y_e}_Вчера")
    )
    markup.add(
        types.InlineKeyboardButton("📊 За все время", callback_data="clean_view_all_time"),
        types.InlineKeyboardButton("🔍 Выбрать период", callback_data="clean_custom_period")
    )
    markup.add(types.InlineKeyboardButton("🔙 К списку групп", callback_data="clean_back_to_groups"))
    
    text = f"🧹 <b>Очистка истории</b>\nВыберите период для группы: <code>{chat_id}</code>"
    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="HTML")
        
def show_clean_all_time_menu(call, session, bot):
    markup = types.InlineKeyboardMarkup(row_width=2)
    now = datetime.datetime.now(datetime.timezone.utc)
    markup.add(types.InlineKeyboardButton("🔥 Вся история (УДАЛИТЬ)", callback_data=f"clean_period_0_{int(now.timestamp())}_Вся история"))
    
    buttons = []
    for i in range(12):
        f_day = (now.replace(day=1) - datetime.timedelta(days=i*31)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if f_day.month == 12:
            next_m = f_day.replace(year=f_day.year + 1, month=1)
        else:
            next_m = f_day.replace(month=f_day.month + 1)
        l_day = next_m - datetime.timedelta(seconds=1)
        
        label = f_day.strftime("%m.%Y")
        buttons.append(types.InlineKeyboardButton(text=f"📅 {label}", callback_data=f"clean_mview_{int(f_day.timestamp())}_{int(l_day.timestamp())}_{label}"))
    
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="clean_back_to_periods"))
    bot.edit_message_text("📂 <b>Архив по месяцам (очистка):</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_clean_weeks_menu(call, bot, begin_ts, end_ts, month_label, back_cb="clean_back_to_periods"):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(f"🗑 Весь месяц ({month_label})", callback_data=f"clean_period_{begin_ts}_{end_ts}_Месяц {month_label}"))
    
    curr = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    end_dt = datetime.datetime.fromtimestamp(int(float(end_ts)))
    
    w_idx = 1
    while curr <= end_dt:
        w_end = (curr + datetime.timedelta(days=6)).replace(hour=23, minute=59, second=59)
        if w_end > end_dt: w_end = end_dt
        
        lbl = f"{curr.strftime('%d.%m')}-{w_end.strftime('%d.%m')}"
        markup.add(types.InlineKeyboardButton(f"🗓 Неделя {w_idx} ({lbl})", callback_data=f"clean_wview_{int(curr.timestamp())}_{int(w_end.timestamp())}_{lbl}"))
        curr = w_end + datetime.timedelta(seconds=1)
        w_idx += 1

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    bot.edit_message_text(f"📍 Очистка за месяц: <b>{month_label}</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_clean_days_menu(call, bot, begin_ts, end_ts, week_label, back_cb="clean_back_to_periods"):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(f"🗑 Вся неделя ({week_label})", callback_data=f"clean_period_{begin_ts}_{end_ts}_Неделя {week_label}"))
    
    curr = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    end_dt = datetime.datetime.fromtimestamp(int(float(end_ts)))
    
    btns = []
    while curr <= end_dt:
        d_end = curr.replace(hour=23, minute=59, second=59)
        lbl = curr.strftime('%d.%m')
        btns.append(types.InlineKeyboardButton(lbl, callback_data=f"clean_dview_{int(curr.timestamp())}_{int(d_end.timestamp())}_{lbl}"))
        curr += datetime.timedelta(days=1)
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    bot.edit_message_text(f"📅 Дни недели (<b>{week_label}</b>):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_clean_hours_menu(call, bot, begin_ts, end_ts, day_label, chat_id, admin_id, back_cb="clean_back_to_periods"):
    configs = get_combined_settings(chat_id, admin_id)
    start_dt_utc = datetime.datetime.fromtimestamp(int(float(begin_ts)))
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton(f"🧹 Весь день ({day_label})", callback_data=f"clean_period_{begin_ts}_{end_ts}_{day_label}"))
    
    btns = []
    for h in range(0, 24, 3):
        h_start_utc = start_dt_utc + datetime.timedelta(hours=h)
        h_end_utc = h_start_utc + datetime.timedelta(hours=2, minutes=59, seconds=59)
        label = f"{h:02d}:00 - {h+2:02d}:59"
        btns.append(types.InlineKeyboardButton(
            label, 
            callback_data=f"clean_period_{int(h_start_utc.timestamp())}_{int(h_end_utc.timestamp())}_{day_label} {h:02d}h"
        ))
    
    markup.add(*btns)
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    bot.edit_message_text(f"⏳ Выберите время для очистки (<b>{day_label}</b>):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def show_records_for_cleaning(call_or_msg, bot, chat_id, begin, end, label, user_sessions, back_cb="clean_back_to_periods"):
    user_id = call_or_msg.from_user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id].update({
        'clean_view_begin': begin,
        'clean_view_end': end,
        'clean_view_label': label,
        'clean_chat_id': chat_id
    })

    records = load_history_for_chat(chat_id, float(begin), float(end))
    records = sorted(records, key=lambda x: x.get('timestamp', 0), reverse=True)[:15]

    markup = types.InlineKeyboardMarkup()
    
    if not records:
        text = f"📭 В периоде <b>{label}</b> записей не найдено."
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    else:
        text = f"🗑 <b>Удаление записей ({label}):</b>\n\nВыберите запись или удалите всё разом."
        
        for r in records:
            r_id = str(r['_id'])
            dt = datetime.datetime.fromtimestamp(r.get('timestamp', 0)).strftime('%d.%m %H:%M')
            count = len(r.get('participants', []))
            markup.add(types.InlineKeyboardButton(f"🕒 {dt} — {count} чел. [УДАЛИТЬ ❌]", callback_data=f"clean_rec_{r_id}"))

        markup.add(types.InlineKeyboardButton(f"🔥 УДАЛИТЬ ВСЕ ЗА {label}", callback_data=f"clean_bulk_{begin}_{end}"))
        markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data=back_cb))

    cid = call_or_msg.message.chat.id if hasattr(call_or_msg, 'message') else call_or_msg.chat.id
    mid = call_or_msg.message.message_id if hasattr(call_or_msg, 'message') else None

    if mid:
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="HTML")

def ask_confirm_clean(call, chat_id, begin, end, period_name, session, bot, back_cb="clean_back_to_periods"):
    session.update({'clean_begin': begin, 'clean_end': end, 'clean_period_name': period_name})
    text = f"⚠️ <b>ПОДТВЕРЖДЕНИЕ</b>\n\nВы уверены, что хотите навсегда удалить ВСЕ записи за <b>{period_name}</b> для группы <code>{chat_id}</code>?"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ДА, УДАЛИТЬ", callback_data="clean_confirm_yes"),
        types.InlineKeyboardButton("❌ ОТМЕНА", callback_data=back_cb)
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

def execute_delete(call, bot, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id, {})
    chat_id = session.get('clean_chat_id')
    begin = session.get('clean_begin')
    end = session.get('clean_end')
    
    count = delete_history_records(chat_id, begin, end)
    bot.answer_callback_query(call.id, f"✅ Удалено записей: {count}", show_alert=True)
    show_clean_periods_menu(call, session, bot)