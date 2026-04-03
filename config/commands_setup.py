from telebot import types

def setup_bot_menu(bot):
    # 1. Команды для ЛС (Личные сообщения)
    private_commands = [
        types.BotCommand("start", "🚀 Запустить бота"),
        types.BotCommand("help", "❓ Инструкция"),
        types.BotCommand("list", "📋 Мои группы и статистика"),
        types.BotCommand("clean", "🧹 Очистить историю"),
        types.BotCommand("add", "👤 Добавить участника")
    ]
    bot.set_my_commands(private_commands, scope=types.BotCommandScopeAllPrivateChats())

    # 2. Команды для администраторов в группах
    admin_commands = [
        types.BotCommand("collect", "🚀 Начать сбор"),
        types.BotCommand("test", "🧪 Тестовый сбор"),
        types.BotCommand("stop", "🛑 Завершить сбор"),
        types.BotCommand("list", "📊 Статус текущего сбора")
    ]
    bot.set_my_commands(admin_commands, scope=types.BotCommandScopeAllChatAdministrators())
    
    # 3. Команды для всех участников в группах
    group_commands = [
        types.BotCommand("list", "📊 Статус текущего сбора")
    ]
    bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())