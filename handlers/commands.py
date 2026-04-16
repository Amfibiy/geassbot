from telebot import types
from utils.messages import get_welcome_text, get_help_text

def register_commands(bot, active_collections, test_collection, known_groups, user_sessions):

    @bot.message_handler(commands=['start'])
    def cmd_start(message):
        if message.chat.type != 'private': return
        bot.reply_to(message, get_welcome_text(), parse_mode="HTML")

    @bot.message_handler(commands=['help'])
    def cmd_help(message):
        if message.chat.type != 'private': return
        bot.send_message(message.chat.id, get_help_text(), parse_mode="HTML")