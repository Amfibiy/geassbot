from telebot import types

def setup_bot_menu(bot):
    # Команды только для личных сообщений (ЛС) с ботом
    private_commands = [
        types.BotCommand("start", "🚀 Запустить бота"),
        types.BotCommand("help", "❓ Инструкция"),
        types.BotCommand("list", "📋 Мои сборы и статистика"),
        types.BotCommand("clean", "🧹 Очистить историю")
    ]
    bot.set_my_commands(private_commands, scope=types.BotCommandScopeAllPrivateChats())

    # Команды для обычных участников в группах
    group_commands = [
        types.BotCommand("list", "📋 Текущий статус сбора")
    ]
    bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())
    
    # Команды для администраторов в группах
    admin_commands = [
        types.BotCommand("collect", "🚀 Начать сбор"),
        types.BotCommand("test", "🧪 Тестовый сбор"),
        types.BotCommand("stop", "🛑 Завершить сбор"),
        types.BotCommand("list", "📋 Текущий статус сбора")
    ]
    bot.set_my_commands(admin_commands, scope=types.BotCommandScopeAllChatAdministrators())