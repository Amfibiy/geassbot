from .mongo import (
    get_known_groups, 
    save_known_group, 
    save_history_record, 
    load_history_for_chat,
    save_user_id,
    get_all_members_ids,
    delete_history_records,  # Новая
    clear_all_history        # Новая
)