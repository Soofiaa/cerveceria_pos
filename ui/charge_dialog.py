from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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
)
from core.utils_format import fmt_money
from ui.pos.pos_utils import parse_price


class ChargeDialog(QDialog):
    """
    Diálogo de cobro con:
    - Total a cobrar destacado.
    - Medios de pago como botones tipo tarjeta con icono.
    - Detalle dinámico según el método (efectivo = monto/vuelto, otros = referencia).
    """

    def __init__(self, total: int, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cobrar")
        self.selected_method: str | None = None
        self.cash_received: int | None = None
        self.change: int | None = None
        self.ref_number: str | None = None

        self.total = int(total or 0)

        # === Layout general ===
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # --- Título y subtítulo ---
        title = QLabel("Cobrar venta")
        title.setObjectName("DialogTitle")

        subtitle = QLabel("Revisa el total, selecciona el medio de pago y confirma el cobro.")
        subtitle.setObjectName("HintLabel")
        subtitle.setWordWrap(True)

        lay.addWidget(title)
        lay.addWidget(subtitle)

        # --- Total a cobrar: dos líneas dentro de la misma “tarjeta” ---
        total_badge = QLabel()
        total_badge.setObjectName("TotalsBadge")
        total_badge.setAlignment(Qt.AlignCenter)
        total_badge.setTextFormat(Qt.RichText)
        total_badge.setText(
            f"<div style='font-size: 11pt; margin-bottom: 4px;'>Total a cobrar</div>"
            f"<div style='font-size: 22pt; font-weight: 900;'>{fmt_money(self.total)}</div>"
        )
        lay.addWidget(total_badge)

        # === Medios de pago como tarjetas ===
        methods_label = QLabel("Medio de pago")
        methods_label.setObjectName("HintLabel")
        lay.addWidget(methods_label)

        methods_row = QHBoxLayout()
        methods_row.setSpacing(8)

        self.method_group = QButtonGroup(self)
        self.method_group.setExclusive(True)

        self.btn_cash = QPushButton("💵 Efectivo")
        self.btn_debit = QPushButton("💳 Débito")
        self.btn_credit = QPushButton("💳 Crédito")
        self.btn_transfer = QPushButton("🏦 Transferencia")

        for btn in (self.btn_cash, self.btn_debit, self.btn_credit, self.btn_transfer):
            btn.setCheckable(True)
            btn.setMinimumHeight(34)
            btn.setProperty("buttonType", "ghost")  # se verá como placas suaves
            btn.setObjectName("PayMethodButton")    # por si quieres estilizar en QSS
            methods_row.addWidget(btn)

        lay.addLayout(methods_row)

        # Mapa botón -> método interno
        self._buttons_to_method = {
            self.btn_cash: "efectivo",
            self.btn_debit: "debito",
            self.btn_credit: "credito",
            self.btn_transfer: "transferencia",
        }
        for btn in self._buttons_to_method:
            self.method_group.addButton(btn)

        self.method_group.buttonClicked.connect(self._on_method_clicked)

        # === Detalle del pago ===
        details_box = QGroupBox("Detalle del pago")
        details_layout = QFormLayout()
        details_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        details_layout.setContentsMargins(14, 10, 14, 12)
        details_layout.setHorizontalSpacing(10)
        details_layout.setVerticalSpacing(6)

        # Campos efectivo
        self.lbl_monto = QLabel("Monto recibido")
        self.in_monto = QLineEdit()
        self.in_monto.setPlaceholderText("Monto recibido")
        self.in_monto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.in_monto.setMinimumHeight(32)

        self.lbl_vuelto_title = QLabel("Vuelto")
        self.lbl_vuelto = QLabel("$0")
        self.lbl_vuelto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Campo referencia
        self.lbl_ref_title = QLabel("Referencia")
        self.in_ref = QLineEdit()
        self.in_ref.setPlaceholderText("Número de referencia (opcional)")
        self.in_ref.setMinimumHeight(32)
        self.in_ref.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Agregamos todas las filas (luego las mostraremos/ocultaremos)
        details_layout.addRow(self.lbl_monto, self.in_monto)
        details_layout.addRow(self.lbl_vuelto_title, self.lbl_vuelto)
        details_layout.addRow(self.lbl_ref_title, self.in_ref)

        details_box.setLayout(details_layout)
        lay.addWidget(details_box)

        # === Botones inferiores ===
        btns = QHBoxLayout()
        btns.addStretch()

        ok = QPushButton("Confirmar")
        cancel = QPushButton("Cancelar")
        ok.setProperty("buttonType", "primary")
        cancel.setProperty("buttonType", "ghost")
        ok.setMinimumHeight(36)
        cancel.setMinimumHeight(36)

        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)

        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

        # Conexiones de campos
        self.in_monto.textChanged.connect(self._format_monto)
        self.in_monto.textChanged.connect(self._recalc_change)

        # Estado inicial: efectivo seleccionado
        self.btn_cash.setChecked(True)
        self._update_panel("efectivo")

    # ================== LÓGICA ==================

    def _on_method_clicked(self, btn: QPushButton):
        method = self._buttons_to_method.get(btn, "efectivo")
        self._update_panel(method)

    def _update_panel(self, method: str):
        """
        Muestra/oculta campos según el método de pago.
        efectivo -> monto + vuelto
        otros    -> referencia
        """
        method = (method or "").lower()

        # Ocultar todo
        for w in (
            self.lbl_monto, self.in_monto,
            self.lbl_vuelto_title, self.lbl_vuelto,
            self.lbl_ref_title, self.in_ref,
        ):
            w.hide()

        if method == "efectivo":
            # Limpiar efectivo
            self.in_monto.setText("")
            self.lbl_vuelto.setText("$0")

            self.lbl_monto.show()
            self.in_monto.show()
            self.lbl_vuelto_title.show()
            self.lbl_vuelto.show()
            self.in_monto.setFocus()
        else:
            # Limpiar referencia
            self.in_ref.setText("")

            self.lbl_ref_title.show()
            self.in_ref.show()
            self.in_ref.setFocus()

        self.selected_method = method


    def _recalc_change(self):
        val = parse_price(self.in_monto.text())
        chg = max(0, val - self.total)
        self.lbl_vuelto.setText(fmt_money(chg))


    def accept(self):
        """Valida datos y deja las propiedades listas para el caller."""
        # Determinar método seleccionado
        checked_btn = self.method_group.checkedButton()
        method = self._buttons_to_method.get(checked_btn, "efectivo")
        self.selected_method = method

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

        super().accept()

    
    def _format_monto(self):
        txt = self.in_monto.text()

        # quitar $ visual antes de parsear
        clean = txt.replace("$", "").strip()

        num = parse_price(clean)

        if clean == "":
            formatted = ""
        else:
            formatted = f"${num:,}".replace(",", ".")

        if formatted != txt:
            self.in_monto.blockSignals(True)
            self.in_monto.setText(formatted)
            self.in_monto.blockSignals(False)
            self.in_monto.setCursorPosition(len(formatted))

