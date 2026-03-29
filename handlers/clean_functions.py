import datetime
import time
from database.mongo import delete_history_records, clear_all_history
from utils.validators import validate_date

def do_clean(message, chat_id, clean_type, parameter, bot):
    """Главная функция для выполнения очистки базы данных"""
    now = time.time()
    
    if clean_type == 'всё':
        deleted = clear_all_history(chat_id)
        bot.reply_to(message, f"✅ Вся история этой группы успешно удалена из базы.\nУдалено записей: {deleted}")
        return
    
    begin = 0
    end = now
    
    if clean_type == "сегодня":
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0)
        begin = today.timestamp()
        end = begin + 86400
        
    elif clean_type == "вчера":
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        begin = yesterday.replace(hour=0, minute=0, second=0).timestamp()
        end = begin + 86400
        
    elif clean_type == "неделя":
        begin = now - 604800
        
    elif clean_type == "месяц":
        begin = now - 2592000
        
    elif clean_type == "дата" and parameter:
        date_obj = validate_date(parameter)
        if date_obj:
            begin = date_obj.timestamp()
            end = begin + 86400
        else:
            bot.reply_to(message, "❌ Ошибка: неверный формат даты.")
            return
            
    elif clean_type == "период" and parameter:
        try:
            parts = parameter.split('-')
            if len(parts) >= 6:
                date1_str = f"{parts[0].strip()}-{parts[1].strip()}-{parts[2].strip()}"
                date2_str = f"{parts[3].strip()}-{parts[4].strip()}-{parts[5].strip()}"
                date1 = validate_date(date1_str)
                date2 = validate_date(date2_str)
                if date1 and date2:
                    begin = date1.timestamp()
                    end = date2.timestamp() + 86400
                else:
                    bot.reply_to(message, "❌ Ошибка: неверный формат дат.")
                    return
            else:
                bot.reply_to(message, "❌ Ошибка: неверный формат периода.")
                return
        except Exception as e:
            bot.reply_to(message, "❌ Произошла ошибка при разборе периода.")
            return
            
    else:
        bot.reply_to(message, "❌ Неизвестный тип очистки.")
        return
    deleted = delete_history_records(chat_id, begin, end)
    bot.reply_to(message, f"✅ Очистка завершена. Удалено записей: {deleted}")