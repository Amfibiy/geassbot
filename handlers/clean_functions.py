import time
import datetime
from telebot import types
from database.mongo import delete_history_records
from utils.helpers import get_admin_groups

def handle_clean(message, bot, active_collections, test_collection, known_groups, user_sessions):
    admin_groups = get_admin_groups(message.from_user.id, bot)
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}

    if not admin_groups:
        bot.send_message(message.chat.id, "📭 <b>Список групп пуст.</b>\nДобавьте бота в группу и выдайте права администратора.", parse_mode="HTML")
        return

    # Устанавливаем состояние ожидания ID именно для очистки
    user_sessions[user_id]['step'] = 'clean_wait_group_id'

    text = "🧹 <b>Выберите группу для очистки:</b>\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for i, g in enumerate(admin_groups, 1):
        title = g.get('title', 'Группа').replace('<', '&lt;').replace('>', '&gt;')
        c_id = g.get('chat_id')
        text += f"{i}. <b>{title}</b> (<code>{c_id}</code>)\n"
        markup.add(types.InlineKeyboardButton(text=f"{i}. {title}", callback_data=f"clean_group_{c_id}"))

    text += "\n👇 <b>Нажмите на кнопку выше</b>\nили отправьте ID группы (включая минус)."
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_clean_actions(message_or_call, session, bot):
    chat_id = session.get('clean_chat_id')
    name_group = session.get('name_group', f"Группа {chat_id}")
    
    text = f"🧹 <b>Очистка истории:</b> {name_group}\nID: <code>{chat_id}</code>\n\nВыберите период, за который нужно УДАЛИТЬ записи:"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🕒 1 час", callback_data="clean_period_1h"),
        types.InlineKeyboardButton("🌅 Сегодня", callback_data="clean_period_today")
    )
    markup.row(
        types.InlineKeyboardButton("📅Месяц", callback_data="clean_period_month"),
        types.InlineKeyboardButton("📅 7 дней", callback_data="clean_period_week"),
        types.InlineKeyboardButton("♾️ Всё время", callback_data="clean_period_all")
    )
    markup.row(types.InlineKeyboardButton("⌨️ Ввести дату вручную", callback_data="clean_period_manual"))
    markup.row(types.InlineKeyboardButton("🔙 Назад к списку", callback_data="clean_back_to_list"))

    chat_id_to_send = message_or_call.message.chat.id if hasattr(message_or_call, 'message') else message_or_call.chat.id
    
    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, chat_id_to_send, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(chat_id_to_send, text, reply_markup=markup, parse_mode="HTML")

def ask_confirm_clean(message_or_call, chat_id, begin_ts, end_ts, period_name, session, bot):
    session.update({
        'clean_begin': begin_ts,
        'clean_end': end_ts,
        'clean_period_name': period_name
    })
    
    text = f"⚠️ <b>ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ</b>\n\nВы уверены, что хотите навсегда удалить записи за <b>{period_name}</b> для группы <code>{chat_id}</code>?"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ДА, УДАЛИТЬ", callback_data="clean_confirm_yes"),
        types.InlineKeyboardButton("❌ ОТМЕНА", callback_data="clean_confirm_no")
    )
    
    if hasattr(message_or_call, 'message'):
        bot.edit_message_text(text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=markup, parse_mode="HTML")
    else:
        bot.send_message(message_or_call.chat.id, text, reply_markup=markup, parse_mode="HTML")

def execute_delete(call, bot, user_sessions):
    user_id = call.from_user.id
    session = user_sessions.get(user_id, {})
    
    chat_id = session.get('clean_chat_id')
    begin_ts = session.get('clean_begin')
    end_ts = session.get('clean_end')
    period_name = session.get('clean_period_name')
    
    if not chat_id:
        bot.answer_callback_query(call.id, "❌ Сессия истекла.", show_alert=True)
        return

    try:
        delete_history_records(chat_id, begin_ts, end_ts)
        bot.answer_callback_query(call.id, "✅ История успешно очищена!", show_alert=True)
        show_clean_actions(call, session, bot)
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {e}", show_alert=True)