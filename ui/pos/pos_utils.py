from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton

def parse_price(txt: str) -> int:
    """Convierte texto tipo '1.500' o '1,500' en entero."""
    t = (txt or "").strip()
    if not t:
        return 0
    return int(t.replace(".", "").replace(",", ""))

def make_remove_button(line_id: int, callback):
    """Botón rojo ✕ centrado."""
    btn = QPushButton("✕")
    btn.setFixedSize(32, 32)
    btn.setStyleSheet("""
        QPushButton {
            background-color: #d9534f; color: white;
            border: none; border-radius: 6px; font-weight: bold;
        }
        QPushButton:hover { background-color: #c9302c; }
    """)
    btn.clicked.connect(lambda: callback(line_id))
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.addStretch()
    layout.addWidget(btn)
    layout.addStretch()
    layout.setContentsMargins(0, 0, 0, 0)
    return container
