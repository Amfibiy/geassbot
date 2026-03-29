from telebot import types

def setup_bot_menu(bot):
    private_commands = [
        types.BotCommand("start", "🚀 Запустить бота"),
        types.BotCommand("help", "❓ Инструкция"),
        types.BotCommand("list", "📋 Мои сборы и статистика"),
        types.BotCommand("clean", "🧹 Очистить историю")
    ]
    bot.set_my_commands(private_commands, scope=types.BotCommandScopeAllPrivateChats())

    group_commands = [
        types.BotCommand("list", "📋 Текущий статус сбора")
    ]
    bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())
    admin_commands = [
        types.BotCommand("start_collect", "🚀 Начать сбор"),
        types.BotCommand("test", "🧪 Тестовый сбор"),
        types.BotCommand("stop", "🛑 Завершить сбор"),
        types.BotCommand("list", "📋 Управление и статистика"),
        types.BotCommand("clean", "🧹 Удалить историю этой группы")
    ]
    bot.set_my_commands(admin_commands, scope=types.BotCommandScopeAllChatAdministrators())