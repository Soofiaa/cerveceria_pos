from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

def parse_price(txt: str) -> int:
    """Convierte texto tipo '1.500' o '1,500' en entero."""
    t = (txt or "").strip()
    if not t:
        return 0
    return int(t.replace(".", "").replace(",", ""))