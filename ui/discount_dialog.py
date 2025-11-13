# ui/discount_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox
)
from PySide6.QtGui import QIntValidator


class DiscountDialog(QDialog):
    def __init__(self, total_actual: int, modo="global", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aplicar descuento")
        self.valor = 0
        self.modo = modo

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Total actual: ${total_actual}"))

        self.in_desc = QLineEdit()
        self.in_desc.setValidator(QIntValidator(0, 10**9))
        self.in_desc.setPlaceholderText("Monto o porcentaje")
        layout.addWidget(QLabel("Descuento:"))
        layout.addWidget(self.in_desc)

        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItems(["Monto fijo", "Porcentaje"])
        layout.addWidget(self.cmb_tipo)

        btns = QHBoxLayout()
        ok = QPushButton("Aplicar")
        cancel = QPushButton("Cancelar")
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def accept(self):
        try:
            val = int(self.in_desc.text() or "0")
            if val < 0:
                raise ValueError
            self.valor = val
            self.tipo = self.cmb_tipo.currentText()
            super().accept()
        except Exception:
            QMessageBox.warning(self, "Valor inválido", "Ingrese un número válido.")
