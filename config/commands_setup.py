from telebot import types

def setup_bot_menu(bot):
    private_commands = [
        types.BotCommand("start", "🚀 Запустить бота"),
        types.BotCommand("help", "❓ Инструкция"),
        types.BotCommand("list", "📋 Мои группы и статистика"),
        types.BotCommand("clean", "🧹 Очистить историю"),
        types.BotCommand("settings", "⚙️ Настройки") # Заменили /add на /settings
    ]
    bot.set_my_commands(private_commands, scope=types.BotCommandScopeAllPrivateChats())

    admin_commands = [
        types.BotCommand("collect", "🚀 Начать сбор"),
        types.BotCommand("test", "🧪 Тестовый сбор"),
        types.BotCommand("stop", "🛑 Завершить сбор"),
        types.BotCommand("list", "📊 Статус текущего сбора"),
        types.BotCommand("settings", "⚙️ Настройки") # Добавляем и сюда для удобства админов
    ]
    bot.set_my_commands(admin_commands, scope=types.BotCommandScopeAllChatAdministrators())
    
    group_commands = [
        types.BotCommand("list", "📊 Статус текущего сбора")
    ]
    bot.set_my_commands(group_commands, scope=types.BotCommandScopeAllGroupChats())