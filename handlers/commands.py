import telebot
from utils.messages import get_welcome_text, get_help_text

def register_commands(bot):
    
    @bot.message_handler(commands=['start'])
    def handle_start_command(message):
        if message.chat.type != "private":
            return
        bot.reply_to(message, get_welcome_text(), parse_mode="HTML")
    
    @bot.message_handler(commands=['help'])
    def handle_help(message):
        if message.chat.type != "private":
            return
        bot.reply_to(message, get_help_text(), parse_mode="HTML")