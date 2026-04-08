from .list_functions import (
    show_participants_list,
    handle_list_group_callback,
    handle_period_callback,
    show_menu_periods_in_ls
)
from database.mongo import get_group_by_id

def register_list_handlers(bot, active_collections, test_collection, known_groups, user_sessions):
    
    @bot.message_handler(commands=['list'])
    def handle_list(message):
        if message.chat.type in ['group', 'supergroup']:
            # Логика для группы: показываем участников с никами
            chat_id = message.chat.id
            col = active_collections.get(chat_id) or test_collection.get(chat_id)
            if col:
                count = len(col['participants'])
                if count == 0:
                    bot.reply_to(message, "📋 **Статус сбора:**\nПока никто не присоединился.", parse_mode="Markdown")
                else:
                    # Экранируем символы, чтобы Markdown не выдавал ошибку API
                    title = col.get('title', 'Сбор').replace('_', '\\_').replace('*', '\\*')
                    lines = [f"📋 **Статус сбора: {title}**\nУчастников: {count}\n"]
                    for i, p in enumerate(col['participants'], 1):
                        name = p['name'].replace('_', '\\_').replace('*', '\\*')
                        username = f" (@{p['username']})" if p.get('username') else ""
                        lines.append(f"{i}. {name}{username}")
                    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")
            else:
                bot.reply_to(message, "📭 В данный момент активных сборов нет.")
        else:
            # Логика для ЛС (показ кнопок групп)
            show_participants_list(message, bot, active_collections, test_collection, known_groups, user_sessions)

    @bot.message_handler(func=lambda m: m.chat.type == 'private' and (m.text.strip().startswith('-') or m.text.strip().isdigit()))
    def handle_manual_id(message):
        """Обработка, если пользователь прислал ID группы текстом в ЛС"""
        chat_id_raw = message.text.strip()
        group = get_group_by_id(chat_id_raw)
        
        if group:
            u_id = message.from_user.id
            # Инициализируем сессию при ручном вводе
            user_sessions[u_id] = {
                'chat_id': group['chat_id'],
                'name_group': group['title'],
                'step': 'choice_period'
            }
            show_menu_periods_in_ls(message, user_sessions[u_id], bot)
        else:
            bot.send_message(message.chat.id, "❌ Группа с таким ID не найдена в базе.")

    # Регистрация колбэков для меню списка
    @bot.callback_query_handler(func=lambda call: call.data.startswith('list_group_'))
    def list_group_cb(call):
        handle_list_group_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith('period_'))
    def period_cb(call):
        handle_period_callback(call, bot, active_collections, test_collection, known_groups, user_sessions)