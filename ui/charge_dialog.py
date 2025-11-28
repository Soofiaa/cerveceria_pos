from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from core.utils_format import fmt_money


class ChargeDialog(QDialog):
    """
    Diálogo de cobro con estética moderna y mensajes claros.

    Elementos destacados:
    - Encabezado con total destacado para reforzar la acción del cobro.
    - Campos alineados a la derecha para montos y referencia opcional.
    - Botones primario/ghost en línea con el tema del POS.
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
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)

        title = QLabel("Cobrar venta")
        title.setObjectName("DialogTitle")
        total_badge = QLabel(f"Total a cobrar: {fmt_money(self.total)}")
        total_badge.setObjectName("TotalsBadge")
        total_badge.setAlignment(Qt.AlignCenter)

        lay.addWidget(title)
        lay.addWidget(total_badge)

        # Medio de pago
        self.cmb = QComboBox()
        self.cmb.addItems(["Efectivo", "Débito", "Crédito", "Transferencia"])
        self.cmb.setMinimumHeight(32)

        payment_box = QGroupBox("Medio de pago")
        payment_form = QFormLayout()
        payment_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        payment_form.addRow("Selecciona", self.cmb)
        payment_box.setLayout(payment_form)
        lay.addWidget(payment_box)

        # Área dinámica según medio de pago
        self.panel = QWidget()
        self.form = QFormLayout(self.panel)
        self.form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.form.setFormAlignment(Qt.AlignTop)

        # ----- Campos para efectivo -----
        self.lbl_monto = QLabel("Monto recibido")
        self.in_monto = QLineEdit()
        self.in_monto.setPlaceholderText("Monto recibido")
        self.in_monto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.in_monto.setMinimumHeight(32)

        self.lbl_vuelto_title = QLabel("Vuelto")
        self.lbl_vuelto = QLabel("$0")
        self.lbl_vuelto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # ----- Campo para referencia (otros medios) -----
        self.lbl_ref_title = QLabel("Referencia")
        self.in_ref = QLineEdit()
        self.in_ref.setPlaceholderText("Número de referencia (opcional)")
        self.in_ref.setMinimumHeight(32)
        self.in_ref.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Agregamos TODAS las filas una sola vez
        self.form.addRow(self.lbl_monto, self.in_monto)
        self.form.addRow(self.lbl_vuelto_title, self.lbl_vuelto)
        self.form.addRow(self.lbl_ref_title, self.in_ref)

        lay.addWidget(self.panel)

        # Botones
        btns = QHBoxLayout()
        btns.addStretch()

        ok = QPushButton("Confirmar")
        cancel = QPushButton("Cancelar")
        ok.setProperty("buttonType", "primary")
        cancel.setProperty("buttonType", "ghost")
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
        method = (self.cmb.currentText() or "").lower()

        # Ocultamos todo por defecto
        for w in (
            self.lbl_monto, self.in_monto,
            self.lbl_vuelto_title, self.lbl_vuelto,
            self.lbl_ref_title, self.in_ref
        ):
            w.hide()

        if method == "efectivo":
            # Reset campos de efectivo
            self.in_monto.setText("")
            self.lbl_vuelto.setText("$0")

            # Mostramos solo efectivo + vuelto
            self.lbl_monto.show()
            self.in_monto.show()
            self.lbl_vuelto_title.show()
            self.lbl_vuelto.show()

            self.in_monto.setFocus()
        else:
            # Reset referencia
            self.in_ref.setText("")

            # Mostramos solo referencia
            self.lbl_ref_title.show()
            self.in_ref.show()

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
