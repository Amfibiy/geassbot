import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def update_counters(bot, active_collections, test_collection):
    while True:
        try:
            now = time.time()
            for coll_dict, is_test in [(active_collections, False), (test_collection, True)]:
                for chat_id, col in list(coll_dict.items()):
                    elapsed = int(now - col['start_time'])
                    duration_total = col.get('duration', 1800) 
                    
                    if elapsed >= duration_total:
                        from handlers.collection_functions import stop_collection_automatically
                        stop_collection_automatically(chat_id, bot, coll_dict, is_test)
                    else:
                        rem = max(0, duration_total - elapsed)
                        time_str = f"{rem // 60:02d}:{rem % 60:02d}"
                        
                        template = col.get('main_template')
                        tags = col.get('remaining_tags', "")
                        count = len(col['participants'])
                        
                        try:
                            new_text = template.format(
                                duration=time_str,   
                                remaining=time_str,  
                                tags=tags,
                                count=count
                            )
                            
                            markup = InlineKeyboardMarkup()
                            markup.add(InlineKeyboardButton(
                                f"✅ Присоединиться ({count})", 
                                callback_data="join_collection"
                            ))

                            bot.edit_message_text(
                                chat_id=chat_id,
                                message_id=col['main_message_id'],
                                text=new_text,
                                reply_markup=markup,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            if "message is not modified" not in str(e).lower():
                                print(f"⚠️ Ошибка обновления ({chat_id}): {e}")

        except Exception as e:
            print(f"❌ Критическая ошибка в цикле счетчика: {e}")
        
        time.sleep(10) 