# ui/products_view.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QHeaderView, QAbstractItemView
)

from ui.products import ProductActionsMixin, ProductBackupMixin


class ProductsView(QWidget, ProductActionsMixin, ProductBackupMixin):
    """
    Vista principal de productos:
    - Lista con búsqueda
    - Botones: Agregar, Quitar
    - Editar se hace con doble clic (subventana ProductDialog).
    """

    def __init__(self):
        super().__init__()

        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- Título ---
        title = QLabel("Productos")
        title.setObjectName("SectionTitle")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # --- Instrucción clara ---
        hint = QLabel(
            "Usa \"Agregar producto\" para crear uno nuevo.\n"
            "Haz doble clic en un producto para modificarlo.\n"
            "Haz un clic en un producto y usa \"Quitar producto\" para eliminarlo."
        )
        hint.setObjectName("HintLabel")
        layout.addWidget(hint)

        # --- Búsqueda ---
        search_row = QHBoxLayout()
        self.in_search = QLineEdit()
        self.in_search.setPlaceholderText("Buscar por nombre o código de barras")
        self.btn_search = QPushButton("Buscar")
        self.btn_search.setProperty("buttonType", "primary")   # <<--- NUEVA LÍNEA
        self.btn_search.clicked.connect(self.reload)

        search_row.addWidget(self.in_search)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        # --- Tabla de productos ---
        self.table = QTableWidget(0, 4)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalHeaderLabels(["Nombre", "Venta", "Compra", "Código"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Filas más altas para hacer clic más fácil
        self.table.verticalHeader().setDefaultSectionSize(42)

        layout.addWidget(self.table)

        # Doble clic = editar
        self.table.cellDoubleClicked.connect(self.edit_selected)

        # Habilitar / deshabilitar botón Quitar según selección
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # --- Botones inferiores (Agregar / Quitar) ---
        buttons_row = QHBoxLayout()
        self.btn_new = QPushButton("Agregar producto")
        self.btn_new.setProperty("buttonType", "primary")
        self.btn_delete = QPushButton("Quitar producto")
        self.btn_delete.setProperty("buttonType", "danger")

        self.btn_new.clicked.connect(self.new_product)
        self.btn_delete.clicked.connect(self.delete_selected)

        buttons_row.addWidget(self.btn_new)
        buttons_row.addWidget(self.btn_delete)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        # ------------------------------
        # Botones de respaldo CSV
        # ------------------------------
        backup_row = QHBoxLayout()
        backup_row.addWidget(QLabel("Respaldo de productos:"))
        self.btn_export = QPushButton("Guardar lista de productos...")
        self.btn_export.setProperty("buttonType", "ghost")
        self.btn_import = QPushButton("Cargar lista de productos...")
        self.btn_import.setProperty("buttonType", "ghost")

        self.btn_export.clicked.connect(self.export_products_csv)
        self.btn_import.clicked.connect(self.import_products_csv)

        backup_row.addWidget(self.btn_export)
        backup_row.addWidget(self.btn_import)
        backup_row.addStretch()

        layout.addLayout(backup_row)

        # --- Ajustes de tamaño para usuarios no técnicos ---
        self.in_search.setMinimumHeight(34)
        self.btn_search.setMinimumHeight(36)

        self.btn_new.setMinimumHeight(36)
        self.btn_delete.setMinimumHeight(36)
        self.btn_export.setMinimumHeight(34)
        self.btn_import.setMinimumHeight(34)

        # Carga inicial
        self.reload()
        self._on_selection_changed()  # para desactivar Quitar al inicio

    
    def _hide_common_product_rows(self):
        """
        Elimina de la tabla las filas cuyo nombre sea 'Producto común'.
        No borra nada de la BD, solo de la vista.
        """
        name_col = 0  # columna Nombre
        row = self.table.rowCount() - 1

        while row >= 0:
            item = self.table.item(row, name_col)
            if item:
                nombre = item.text().strip().lower()
                if nombre == "producto común":
                    self.table.removeRow(row)
            row -= 1
            
    
    def reload(self):
        """
        Recarga la tabla de productos usando la lógica del mixin
        y luego oculta 'Producto común' de la vista.
        """
        # Usamos la implementación original del mixin:
        from ui.products import ProductActionsMixin
        ProductActionsMixin.reload(self)

        # Después de llenar la tabla, ocultamos el Producto común:
        self._hide_common_product_rows()

