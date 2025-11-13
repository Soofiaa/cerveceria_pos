# ui/charge_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QLineEdit, QMessageBox
)


class ChargeDialog(QDialog):
    """
    Diálogo de cobro.

    Al cerrarse con Aceptar, deja disponibles:
        self.selected_method : str              -> "Efectivo", "Débito", etc.
        self.cash_received   : int | None       -> monto recibido en entero (solo efectivo)
        self.change          : int | None       -> vuelto en entero (solo efectivo)
        self.reference       : str | None       -> número de referencia (otros medios)
    """
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cobrar")

        self.total = total
        self.selected_method = None
        self.cash_received = None
        self.change = None
        self.reference = None

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Total a cobrar: {self._fmt_money(total)}"))

        # --- Medio de pago ---
        lay.addWidget(QLabel("Medio de pago:"))
        self.cmb = QComboBox()
        # Mostrar con mayúscula inicial
        self.cmb.addItems(["Efectivo", "Débito", "Crédito", "Transferencia"])
        lay.addWidget(self.cmb)

        # --- Zona dinámica (efectivo / otros) ---
        # Efectivo: monto recibido
        self.lbl_paid = QLabel("Monto recibido:")
        self.le_paid = QLineEdit()
        self.le_paid.setPlaceholderText("Ej: 10.000")

        # Vuelto dentro de un cuadro (solo lectura)
        change_layout = QHBoxLayout()
        self.lbl_change = QLabel("Vuelto:")
        self.le_change = QLineEdit()
        self.le_change.setReadOnly(True)
        self.le_change.setText(self._fmt_money(0))
        change_layout.addWidget(self.lbl_change)
        change_layout.addWidget(self.le_change)

        # Otros medios: referencia opcional
        self.lbl_ref = QLabel("N° referencia (opcional):")
        self.le_ref = QLineEdit()

        lay.addWidget(self.lbl_paid)
        lay.addWidget(self.le_paid)
        lay.addLayout(change_layout)
        lay.addWidget(self.lbl_ref)
        lay.addWidget(self.le_ref)

        # Botones
        btns = QHBoxLayout()
        ok = QPushButton("Confirmar")
        cancel = QPushButton("Cancelar")
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

        # Señales
        ok.clicked.connect(self._on_accept)
        cancel.clicked.connect(self.reject)
        self.cmb.currentTextChanged.connect(self._update_fields)
        self.le_paid.textChanged.connect(self._recalc_change)

        # Estado inicial (Efectivo)
        self._update_fields(self.cmb.currentText())

    # ---------- Formato dinero ----------
    def _fmt_money(self, value: int) -> str:
        """
        Formatea un entero como $1.000, $12.500, etc.
        """
        return "$" + f"{value:,}".replace(",", ".")

    # ---------- Comportamiento dinámico ----------
    def _update_fields(self, method: str):
        """Muestra/oculta campos según el medio de pago."""
        if method == "Efectivo":
            # mostrar efectivo
            self.lbl_paid.show()
            self.le_paid.show()
            self.lbl_change.show()
            self.le_change.show()

            # ocultar referencia
            self.lbl_ref.hide()
            self.le_ref.hide()

            self._recalc_change()
        else:
            # ocultar efectivo
            self.lbl_paid.hide()
            self.le_paid.hide()
            self.lbl_change.hide()
            self.le_change.hide()

            # mostrar referencia
            self.lbl_ref.show()
            self.le_ref.show()

    def _recalc_change(self):
        """Recalcula el vuelto cuando es efectivo."""
        if self.cmb.currentText() != "Efectivo":
            return

        text = self.le_paid.text().strip()
        if not text:
            self.le_change.setText(self._fmt_money(0))
            return

        # Permitir que el usuario escriba 10.000 o 10000
        clean = text.replace(".", "")
        if not clean.isdigit():
            self.le_change.setText("Monto inválido")
            return

        paid = int(clean)
        if paid < self.total:
            self.le_change.setText("Monto insuficiente")
        else:
            self.le_change.setText(self._fmt_money(paid - self.total))

    # ---------- Validación y salida ----------
    def _on_accept(self):
        method = self.cmb.currentText()

        if method == "Efectivo":
            text = self.le_paid.text().strip()
            if not text:
                QMessageBox.warning(self, "Error", "Ingrese el monto recibido.")
                return

            clean = text.replace(".", "")
            if not clean.isdigit():
                QMessageBox.warning(self, "Error", "Monto recibido inválido.")
                return

            paid = int(clean)
            if paid < self.total:
                QMessageBox.warning(self, "Error", "El monto recibido es menor al total.")
                return

            self.cash_received = paid
            self.change = paid - self.total
            self.reference = None

        else:
            self.cash_received = None
            self.change = None
            ref_text = self.le_ref.text().strip()
            self.reference = ref_text if ref_text else None  # opcional

        self.selected_method = method
        self.accept()
