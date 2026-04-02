import datetime

def validate_date(date_str):
    """Проверяет корректность даты в формате ДД-ММ-ГГГГ"""
    try:
        return datetime.datetime.strptime(date_str, "%d-%m-%Y")
    except:
        return None

def validate_id(id_str):
    """Проверяет корректность ID группы"""
    try:
        clean_id = id_str.strip()
        if clean_id.startswith('-'):
            digits = ''.join(c for c in clean_id[1:] if c.isdigit())
            if digits:
                return '-' + digits
        else:
            digits = ''.join(c for c in clean_id if c.isdigit())
            return digits if digits else None
    except:
        return None
    return None