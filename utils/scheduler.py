import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def update_counters(bot, active_collections, test_collection, COLLECTION_DURATION):
    while True:
        try:
            now = time.time()
            for coll_dict, is_test in [(active_collections, False), (test_collection, True)]:
                for chat_id, col in list(coll_dict.items()):
                    elapsed = int(now - col['start_time'])
                    
                    if elapsed >= COLLECTION_DURATION:
                        from handlers.collection_functions import stop_collection_automatically
                        stop_collection_automatically(chat_id, bot, coll_dict, is_test)
                    else:
                        rem = COLLECTION_DURATION - elapsed
                        minutes_rem = rem // 60
                        seconds_rem = rem % 60
                        
                        # Текст БЕЗ тегов, чтобы не вызывать повторные пуши
                        if is_test:
                            new_text = (
                                f"🧪 <b>ТЕСТОВЫЙ СБОР</b>\n\n"
                                f"⏱ Осталось времени: {minutes_rem:02d}:{seconds_rem:02d}\n\n"
                                f"👇 Нажмите кнопку (статистика не сохранится)"
                            )
                        else:
                            new_text = (
                                f"🚨 <b>ВНИМАНИЕ!</b> 🚨\n\n"
                                f"🎯 <b>Начинается сбор участников!</b>\n"
                                f"⏱ Осталось времени: <b>{minutes_rem:02d}:{seconds_rem:02d}</b>\n\n"
                                f"👇 Присоединяйтесь по кнопке ниже"
                            )
                        
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton(f"✅ Присоединиться ({len(col['participants'])})", callback_data="join_collection"))

                        try:
                            bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=col['main_message_id'],
                                text=new_text,
                                reply_markup=markup,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            if "message is not modified" not in str(e):
                                print(f"⚠️ Ошибка обновления счетчика: {e}")

        except Exception as e:
            print(f"❌ Ошибка в цикле счетчика: {e}")
        time.sleep(30)