from PySide6.QtWidgets import QPushButton


def parse_price(txt: str) -> int:
    """
    Convierte texto tipo '$10.500', '10.500', '10,500' en entero 10500.
    Ignora cualquier caracter que no sea dígito.
    """
    if not txt:
        return 0

    # Nos quedamos solo con los dígitos (0–9)
    digits = "".join(ch for ch in txt if ch.isdigit())

    if not digits:
        return 0

    return int(digits)


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
