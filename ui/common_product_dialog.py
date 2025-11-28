from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator


class CommonProductDialog(QDialog):
    """
    Diálogo para ingresar un producto común de forma rápida.

    Las entradas siguen el estilo moderno del POS:
    - Encabezado claro y descriptivo.
    - Botones primario/ghost que reflejan el estilo global.
    - Validaciones numéricas y alineación a la derecha para precios y cantidad.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar producto común")
        self.price_value = None
        self.qty_value = 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Producto común")
        title.setObjectName("DialogTitle")
        subtitle = QLabel(
            "Define cantidad y precio rápido para ventas puntuales sin catálogo."
        )
        subtitle.setObjectName("HintLabel")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)

        # Cantidad
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 10**6)
        self.spin_qty.setValue(1)
        self.spin_qty.setAccelerated(True)
        self.spin_qty.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin_qty.setMinimumHeight(34)
        form.addRow("Cantidad", self.spin_qty)

        # Precio
        self.in_price = QLineEdit()
        self.in_price.setValidator(QIntValidator(1, 10**9, self))  # <= SOLO NÚMEROS
        self.in_price.setPlaceholderText("Ej: 1.500")
        self.in_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.in_price.setMinimumHeight(34)
        form.addRow("Precio (CLP)", self.in_price)

        layout.addLayout(form)

        # Botones
        btns = QHBoxLayout()
        btns.addStretch()

        btn_ok = QPushButton("Aceptar")
        btn_ok.setProperty("buttonType", "primary")
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("buttonType", "ghost")
        btn_ok.setMinimumHeight(34)
        btn_cancel.setMinimumHeight(34)

        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        btn_ok.clicked.connect(self._on_accept)
        btn_cancel.clicked.connect(self.reject)

    def _parse_price(self, txt: str) -> int:
        t = (txt or "").strip()
        if not t:
            return 0
        t = t.replace(".", "").replace(",", "")
        return int(t)

    def _on_accept(self):
        # Validar precio
        try:
            price = self._parse_price(self.in_price.text())
            if price <= 0:
                raise ValueError
        except Exception:
            QMessageBox.warning(self, "Precio inválido", "Ingresa un precio válido mayor que 0.")
            return

        self.price_value = price
        self.qty_value = self.spin_qty.value()
        self.accept()
