# ui/charge_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFormLayout, QWidget, QMessageBox
)
from PySide6.QtCore import Qt

from core.utils_format import fmt_money


class ChargeDialog(QDialog):
    """
    Diálogo de cobro:
    - Efectivo: monto recibido + cálculo automático de vuelto.
    - Otros medios: campo de referencia opcional.
    """
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cobrar")
        self.selected_method = None
        self.cash_received = None
        self.change = None
        self.ref_number = None

        self.total = int(total or 0)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Total a cobrar: {fmt_money(self.total)}"))

        # Medio de pago
        self.cmb = QComboBox()
        self.cmb.addItems(["Efectivo", "Débito", "Crédito", "Transferencia"])

        lay.addWidget(QLabel("Medio de pago:"))
        lay.addWidget(self.cmb)

        # Área dinámica según medio de pago
        self.panel = QWidget()
        self.form = QFormLayout(self.panel)

        # Campos para efectivo
        self.in_monto = QLineEdit()
        self.in_monto.setPlaceholderText("Monto recibido")
        self.in_monto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.in_monto.setMinimumHeight(32)

        self.lbl_vuelto = QLabel("$0")
        self.lbl_vuelto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Campo para referencia (otros medios)
        self.in_ref = QLineEdit()
        self.in_ref.setPlaceholderText("Número de referencia (opcional)")
        self.in_ref.setMinimumHeight(32)

        lay.addWidget(self.panel)

        # Botones
        btns = QHBoxLayout()
        ok = QPushButton("Confirmar")
        cancel = QPushButton("Cancelar")
        ok.setMinimumHeight(34)
        cancel.setMinimumHeight(34)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

        # Conexiones
        self.cmb.currentTextChanged.connect(self._update_panel)
        self.in_monto.textChanged.connect(self._recalc_change)

        # Primera configuración
        self._update_panel()

    def _update_panel(self):
        """Cambia los campos mostrados según el medio de pago y pone foco correcto."""
        # Limpiar formulario dinámico
        while self.form.rowCount():
            self.form.removeRow(0)

        method = (self.cmb.currentText() or "").lower()

        if method == "efectivo":
            self.form.addRow("Monto recibido:", self.in_monto)
            self.form.addRow("Vuelto:", self.lbl_vuelto)
            # Dejar listo para escribir SIN clic
            self.in_monto.setText("")
            self.lbl_vuelto.setText("$0")
            self.in_monto.setFocus()
        else:
            self.form.addRow("Referencia:", self.in_ref)
            self.in_ref.setText("")
            self.in_ref.setFocus()

    def _recalc_change(self):
        """Recalcula el vuelto cuando cambia el monto recibido."""
        txt = (self.in_monto.text() or "").replace(".", "").replace(",", "")
        try:
            val = int(txt)
        except Exception:
            self.lbl_vuelto.setText("$0")
            return
        chg = max(0, val - self.total)
        self.lbl_vuelto.setText(fmt_money(chg))

    def accept(self):
        method = (self.cmb.currentText() or "").lower()

        if method == "efectivo":
            txt = (self.in_monto.text() or "").replace(".", "").replace(",", "")
            try:
                val = int(txt)
            except Exception:
                val = 0
            if val < self.total:
                QMessageBox.warning(self, "Cobrar", "El monto recibido es menor al total.")
                return
            self.cash_received = val
            self.change = val - self.total
            self.ref_number = None
        else:
            self.cash_received = None
            self.change = None
            self.ref_number = (self.in_ref.text() or "").strip() or None

        self.selected_method = method
        super().accept()
