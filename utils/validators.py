import datetime

def validate_date(date_str):
    try:
        return datetime.datetime.strptime(date_str, "%d-%m-%Y")
    except ValueError:
        return None

def validate_id(id_str):
    try:
        clean_id = id_str.strip()
        if clean_id.startswith('-'):
            digits = ''.join(c for c in clean_id[1:] if c.isdigit())
            return '-' + digits if digits else None
        else:
            digits = ''.join(c for c in clean_id if c.isdigit())
            return digits if digits else None
    except Exception:
        return None