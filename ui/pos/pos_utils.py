from PySide6.QtWidgets import QPushButton


def parse_price(txt: str) -> int:
    """Convierte texto tipo '1.500' o '1,500' en entero."""
    t = (txt or "").strip()
    if not t:
        return 0
    return int(t.replace(".", "").replace(",", ""))


def make_remove_button(item_id: int, on_click):
    """Crea un botón rojo de eliminar para tablas."""
    btn = QPushButton("✕")
    btn.setStyleSheet(
        """
        QPushButton {
            background-color: #ffdddd;
            border: 1px solid #ffaaaa;
            border-radius: 8px;
            color: #aa0000;
            font-weight: bold;
            min-width: 24px;
            min-height: 24px;
        }
        QPushButton:hover { background-color: #ffcccc; }
        """
    )
    btn.clicked.connect(lambda *_: on_click(item_id))
    return btn
