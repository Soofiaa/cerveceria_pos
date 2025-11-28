from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout
)


class ProductDialog(QDialog):
    """
    Diálogo modal para crear o editar un producto.
    Si se entrega 'data', se usa modo edición.

    Al aceptar (Guardar), deja un diccionario en self.result:
        {
            "name": str,
            "sale_price": int,
            "purchase_price": int,
            "barcode": str | None
        }
    """

    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setModal(True)
        self.result = None

        is_edit = data is not None
        self.setWindowTitle("Editar producto" if is_edit else "Nuevo producto")

        # Tamaño y márgenes generales del diálogo
        self.resize(420, 260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Título grande del diálogo
        title_label = QLabel("Editar producto" if is_edit else "Nuevo producto")
        title_label.setObjectName("DialogTitle")
        layout.addWidget(title_label)

        # Subtítulo / ayuda breve
        subtitle = QLabel("Completa los datos para agregar el producto al catálogo.")
        subtitle.setObjectName("HintLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # === Grupo principal ===
        group = QGroupBox("Datos del producto")
        group_layout = QFormLayout()
        group_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        group_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        group_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        group_layout.setHorizontalSpacing(10)
        group_layout.setVerticalSpacing(6)
        group_layout.setContentsMargins(14, 10, 14, 12)

        # Campos
        self.in_name = QLineEdit()
        self.in_name.setPlaceholderText("Ej: CORONAS 330")

        self.in_sale = QLineEdit()
        self.in_sale.setValidator(QIntValidator(0, 10**9, self))
        self.in_sale.setPlaceholderText("Ej: 2200")
        self.in_sale.setAlignment(Qt.AlignRight)

        self.in_purchase = QLineEdit()
        self.in_purchase.setValidator(QIntValidator(0, 10**9, self))
        self.in_purchase.setPlaceholderText("Opcional. Ej: 1000")
        self.in_purchase.setAlignment(Qt.AlignRight)

        self.in_barcode = QLineEdit()
        self.in_barcode.setPlaceholderText("Opcional")

        # Altura homogénea en los campos
        for le in [self.in_name, self.in_sale, self.in_purchase, self.in_barcode]:
            le.setMinimumHeight(32)

        # Etiquetas del formulario
        group_layout.addRow("Nombre*", self.in_name)
        group_layout.addRow("Precio venta*", self.in_sale)
        group_layout.addRow("Precio compra", self.in_purchase)
        group_layout.addRow("Código de barras", self.in_barcode)

        group.setLayout(group_layout)
        layout.addWidget(group)

        # === Botones Guardar / Cancelar ===
        btns = QHBoxLayout()
        btns.addStretch()

        self.btn_save = QPushButton("Guardar")
        self.btn_save.setProperty("buttonType", "primary")

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setProperty("buttonType", "ghost")

        self.btn_save.setMinimumHeight(36)
        self.btn_cancel.setMinimumHeight(36)

        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

        # Conexiones
        self.btn_save.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self.reject)

        # Modo edición: precargar datos
        if is_edit:
            self.in_name.setText(data.get("name") or "")
            self.in_sale.setText(str(data.get("sale_price") or 0))
            self.in_purchase.setText(str(data.get("purchase_price") or 0))
            self.in_barcode.setText(data.get("barcode") or "")

        self.in_name.setFocus()

    def _on_accept(self):
        name = (self.in_name.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "Validación", "El nombre es obligatorio.")
            return

        try:
            sale = int(self.in_sale.text() or 0)
        except ValueError:
            sale = 0

        if sale <= 0:
            QMessageBox.warning(self, "Validación", "El precio de venta debe ser mayor que 0.")
            return

        try:
            purchase = int(self.in_purchase.text() or 0)
        except ValueError:
            purchase = 0

        barcode = (self.in_barcode.text() or "").strip() or None

        self.result = {
            "name": name,
            "sale_price": sale,
            "purchase_price": purchase,
            "barcode": barcode,
        }
        self.accept()
