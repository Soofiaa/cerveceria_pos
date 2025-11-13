# core/time_utils.py
from datetime import datetime, timezone

def now_local_str():
    """
    Fecha-hora local del sistema en formato 'YYYY-MM-DD HH:MM:SS'
    con zona horaria local (offset) resuelta por el SO.
    """
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
