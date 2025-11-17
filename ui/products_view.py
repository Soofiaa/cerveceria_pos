# ui/products_view.py
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout, QGroupBox,
    QMessageBox, QDialog, QFileDialog
)
from core import product_service as ps
from core.utils_format import fmt_money
from core import product_backup_service as pbs


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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        group = QGroupBox("Datos del producto")
        form = QFormLayout()

        self.in_name = QLineEdit()
        self.in_sale = QLineEdit()
        self.in_sale.setValidator(QIntValidator(0, 10**9))
        self.in_sale.setPlaceholderText("Ej: 2200")

        self.in_purchase = QLineEdit()
        self.in_purchase.setValidator(QIntValidator(0, 10**9))
        self.in_purchase.setPlaceholderText("Opcional. Ej: 1000")

        self.in_barcode = QLineEdit()
        self.in_barcode.setPlaceholderText("Opcional")

        # Altura más cómoda en el diálogo
        for le in [self.in_name, self.in_sale, self.in_purchase, self.in_barcode]:
            le.setMinimumHeight(34)

        form.addRow("Nombre*", self.in_name)
        form.addRow("Precio venta*", self.in_sale)
        form.addRow("Precio compra", self.in_purchase)
        form.addRow("Código de barras", self.in_barcode)

        group.setLayout(form)
        layout.addWidget(group)

        # Botones Guardar / Cancelar
        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_save = QPushButton("Guardar")
        self.btn_cancel = QPushButton("Cancelar")

        self.btn_save.setMinimumHeight(36)
        self.btn_cancel.setMinimumHeight(36)

        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

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
            "barcode": barcode
        }
        self.accept()


class ProductsView(QWidget):
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

        # Fuente un poco más grande solo en esta pantalla
        self.setStyleSheet("""
        QWidget {
            font-size: 11pt;
        }
        QLineEdit {
            font-size: 11pt;
        }
        QPushButton {
            font-size: 11pt;
        }
        QHeaderView::section {
            font-size: 10pt;
        }
        """)

        # --- Título ---
        title = QLabel("Productos")
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
        hint.setStyleSheet("color: #888888; font-size: 12pt;")
        layout.addWidget(hint)

        # --- Búsqueda ---
        search_row = QHBoxLayout()
        self.in_search = QLineEdit()
        self.in_search.setPlaceholderText("Buscar por nombre o código de barras")
        self.btn_search = QPushButton("Buscar")
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

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

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
        self.btn_delete = QPushButton("Quitar producto")

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
        self.btn_import = QPushButton("Cargar lista de productos...")

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


    # --------------------------------------------------
    # Utilidades internas
    # --------------------------------------------------
    def _selected_product_id(self):
        """Devuelve el id del producto seleccionado en la tabla (o None)."""
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _on_selection_changed(self, *args):
        """Activa o desactiva el botón Quitar según haya selección."""
        self.btn_delete.setEnabled(self._selected_product_id() is not None)

    # --------------------------------------------------
    # Carga de datos
    # --------------------------------------------------
    def reload(self):
        q = (self.in_search.text() or "").strip()
        rows = ps.list_products(q)

        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(r["name"] or "")
            name_item.setData(Qt.UserRole, r["id"])
            self.table.setItem(row, 0, name_item)

            pv = QTableWidgetItem(fmt_money(r["sale_price"]))
            pv.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, pv)

            pc = QTableWidgetItem(fmt_money(r["purchase_price"]))
            pc.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, pc)

            bc = QTableWidgetItem(r["barcode"] or "")
            bc.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, bc)

        self.table.clearSelection()
        self._on_selection_changed()

    # --------------------------------------------------
    # Acciones: Agregar / Editar (doble clic) / Quitar
    # --------------------------------------------------
    def new_product(self):
        dlg = ProductDialog(self)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        data = dlg.result
        try:
            ps.create_product(
                name=data["name"],
                sale_price=data["sale_price"],
                purchase_price=data["purchase_price"],
                barcode=data["barcode"],
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear el producto:\n{e}")
            return

        self.reload()

    def edit_selected(self, row=None, col=None):
        pid = self._selected_product_id()
        if not pid:
            # Si alguien hace doble clic en un espacio vacío no hacemos nada.
            return

        data = ps.get_product(pid)
        if not data:
            QMessageBox.warning(self, "Editar", "No se pudo cargar el producto.")
            return

        dlg = ProductDialog(self, data=data)
        if dlg.exec() != QDialog.Accepted or not dlg.result:
            return

        new_data = dlg.result
        try:
            ps.update_product(
                pid,
                name=new_data["name"],
                sale_price=new_data["sale_price"],
                purchase_price=new_data["purchase_price"],
                barcode=new_data["barcode"],
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo actualizar el producto:\n{e}")
            return

        self.reload()

    def delete_selected(self):
        pid = self._selected_product_id()
        if not pid:
            QMessageBox.information(self, "Quitar producto", "Selecciona un producto de la lista.")
            return

        confirm = QMessageBox.question(
            self,
            "Quitar producto",
            "¿Estás segura/o de quitar este producto?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        # Intento normal primero
        try:
            ps.delete_product(pid)
            self.reload()
            return
        except ValueError as ve:
            # Probablemente tiene ventas / tickets relacionados
            resp = QMessageBox.question(
                self,
                "Producto con ventas",
                (
                    f"{ve}\n\n"
                    "Este producto tiene ventas o tickets relacionados.\n"
                    "Si continúas, se eliminarán las líneas de detalle "
                    "asociadas a este producto en ventas y tickets.\n\n"
                    "¿Deseas eliminarlo de todos modos?"
                ),
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            try:
                ps.force_delete_product(pid)
                self.reload()
                return
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo eliminar el producto incluso forzando:\n{e}"
                )
                return
        except Exception as e:
            # Errores técnicos inesperados
            QMessageBox.critical(self, "Error", f"No se pudo eliminar el producto:\n{e}")
            return

    def export_products_csv(self):
        """Permite al usuario guardar la lista de productos en un CSV."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar lista de productos",
            "productos.csv",
            "CSV (*.csv)"
        )
        if not path:
            return

        try:
            pbs.export_products_csv(path)
            QMessageBox.information(
                self,
                "Exportar productos",
                "La lista de productos se guardó correctamente."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Exportar productos",
                f"No se pudo guardar la lista de productos:\n{e}"
            )

    def import_products_csv(self):
        """Permite al usuario cargar/actualizar productos desde un CSV."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar lista de productos",
            "",
            "CSV (*.csv)"
        )
        if not path:
            return

        # Advertencia al usuario
        resp = QMessageBox.question(
            self,
            "Cargar productos",
            (
                "Se van a importar productos desde el archivo seleccionado.\n\n"
                "- Si un producto ya existe (mismo código de barras o nombre), se actualizará.\n"
                "- Si no existe, se creará uno nuevo.\n\n"
                "Esta acción no elimina productos existentes.\n\n"
                "¿Deseas continuar?"
            ),
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        try:
            result = pbs.import_products_csv(path)
            msg = (
                f"Productos creados: {result.get('created', 0)}\n"
                f"Productos actualizados: {result.get('updated', 0)}\n"
                f"Filas omitidas por error: {result.get('skipped', 0)}"
            )
            QMessageBox.information(self, "Cargar productos", msg)
            self.reload()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Cargar productos",
                f"No se pudieron importar los productos:\n{e}"
            )
