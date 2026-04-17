from utils.messages import HELP_TEXT,WELCOME_TEXT

def register_commands(bot, active_collections, test_collection, known_groups, user_sessions):

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        if message.chat.type != 'private': return
        bot.reply_to(message, WELCOME_TEXT, parse_mode="HTML")

    @bot.message_handler(commands=['help'])
    def cmd_help(message):
        if message.chat.type != 'private': return
        bot.send_message(message.chat.id, HELP_TEXT, parse_mode="HTML")