# ui/common_product_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator

class CommonProductDialog(QDialog):
    """
    Diálogo para ingresar Precio y Cantidad del 'Producto común'.
    Acepta precios como '1500', '1.500' o '1,500'.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar producto común")
        self.price_value = None
        self.qty_value = 1

        layout = QVBoxLayout(self)

        # Cantidad
        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Cantidad:"))
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 10**6)
        self.spin_qty.setValue(1)
        self.spin_qty.setAccelerated(True)
        self.spin_qty.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        qty_row.addWidget(self.spin_qty)
        layout.addLayout(qty_row)

        # Precio
        price_row = QHBoxLayout()
        price_row.addWidget(QLabel("Precio (CLP):"))
        self.in_price = QLineEdit()
        self.in_price.setValidator(QIntValidator(1, 10**9, self))  # <= SOLO NÚMEROS
        self.in_price.setPlaceholderText("Ej: 1.500")
        self.in_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        price_row.addWidget(self.in_price)
        layout.addLayout(price_row)

        # Botones
        btns = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btns.addStretch()
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
