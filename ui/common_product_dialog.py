from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QSpinBox,
    QComboBox,
)

from ui.pos.pos_utils import parse_price


class CommonProductDialog(QDialog):
    """
    Diálogo para producto común:
    - nombre (opcional)
    - cantidad (primero, por defecto 1)
    - precio unitario (obligatorio, formateado como $X.XXX)
    - ganancia opcional en % o $ (por defecto 100%)

    Compatibilidad hacia atrás:
    - dlg.qty_value
    - dlg.price_value
    - dlg.name_value

    API nueva:
    - dlg.get_data() -> dict con name, qty, unit_price, gain_type, gain_value
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Producto común")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # === Nombre opcional ===
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Nombre (opcional):"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Ej: Cerveza sin registro, promo, etc.")
        row_name.addWidget(self.edit_name)
        layout.addLayout(row_name)

        # === Cantidad (primero, por defecto 1) ===
        row_qty = QHBoxLayout()
        row_qty.addWidget(QLabel("Cantidad:"))
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 10**6)
        self.spin_qty.setValue(1)
        row_qty.addWidget(self.spin_qty)
        layout.addLayout(row_qty)

        # === Precio unitario ===
        row_price = QHBoxLayout()
        row_price.addWidget(QLabel("Precio unitario:"))
        self.edit_price = QLineEdit()
        self.edit_price.setPlaceholderText("Ej: 2500")
        self.edit_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_price.addWidget(self.edit_price)
        layout.addLayout(row_price)

        # === Ganancia opcional ===
        row_gain = QHBoxLayout()
        row_gain.addWidget(QLabel("Ganancia (opcional):"))

        self.edit_gain = QLineEdit()
        self.edit_gain.setPlaceholderText("Ej: 100")
        self.edit_gain.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.edit_gain.setText("100")  # por defecto 100

        self.cmb_gain_type = QComboBox()
        self.cmb_gain_type.addItems(["%", "$"])  # tipo de ganancia

        row_gain.addWidget(self.edit_gain)
        row_gain.addWidget(self.cmb_gain_type)
        layout.addLayout(row_gain)

        # === Botones ===
        btns = QHBoxLayout()
        btns.addStretch()
        btn_ok = QPushButton("Agregar")
        btn_cancel = QPushButton("Cancelar")
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

        btn_ok.clicked.connect(self.on_accept)
        btn_cancel.clicked.connect(self.reject)

        # Foco inicial en cantidad
        self.spin_qty.setFocus()
        self.spin_qty.selectAll()

        # Formateo en vivo del precio
        self.edit_price.textChanged.connect(self._format_price)

    # ======== Propiedades compatibles con el código antiguo ========

    @property
    def qty_value(self) -> int:
        """Cantidad seleccionada."""
        return self.spin_qty.value()

    @property
    def price_value(self) -> int:
        """Precio unitario parseado como entero."""
        return parse_price(self.edit_price.text())

    @property
    def name_value(self) -> str | None:
        """Nombre opcional del producto común."""
        name = (self.edit_name.text() or "").strip()
        return name or None

    # Ganancia (nueva API, pero no rompe nada si no se usa)
    @property
    def gain_type(self) -> str:
        """'%' o '$' según lo elegido."""
        return self.cmb_gain_type.currentText()

    @property
    def gain_value(self) -> int | None:
        """
        Valor numérico de ganancia.
        Si el campo está vacío o es inválido, devuelve None.
        """
        txt = (self.edit_gain.text() or "").strip()
        if not txt:
            return None
        txt = txt.replace(".", "").replace(",", "")
        if not txt.isdigit():
            return None
        return int(txt)

    # ======== Lógica interna ========

    def _format_price(self):
        """Formatea el precio como $X.XXX mientras se escribe."""
        txt = self.edit_price.text()
        clean = txt.replace("$", "").strip()

        num = parse_price(clean)

        if clean == "":
            formatted = ""
        else:
            formatted = f"${num:,}".replace(",", ".")

        if formatted != txt:
            self.edit_price.blockSignals(True)
            self.edit_price.setText(formatted)
            self.edit_price.blockSignals(False)
            self.edit_price.setCursorPosition(len(formatted))

    def on_accept(self):
        price = self.price_value
        if price <= 0:
            QMessageBox.warning(self, "Producto común", "Ingresa un precio mayor que 0.")
            return
        self.accept()

    def get_data(self) -> dict:
        """
        Devuelve los datos listos para guardar en el ticket.
        (Por ahora, el ticket usa solo name, qty y unit_price;
         gain_type y gain_value quedan disponibles por si se ocupan más adelante.)
        """
        return {
            "name": self.name_value,
            "qty": self.qty_value,
            "unit_price": self.price_value,
            "gain_type": self.gain_type,
            "gain_value": self.gain_value,
        }
