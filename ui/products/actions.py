from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from core import product_service as ps
from .dialogs import ProductDialog


class ProductActionsMixin:
    """Acciones comunes para la vista de productos (CRUD)."""

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

    def reload(self):
        q = (self.in_search.text() or "").strip()
        rows = ps.list_products(q)

        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = self._make_name_item(r)
            self.table.setItem(row, 0, name_item)

            self.table.setItem(row, 1, self._make_money_item(r["sale_price"]))
            self.table.setItem(row, 2, self._make_money_item(r["purchase_price"]))
            self.table.setItem(row, 3, self._make_stock_item(r))
            self.table.setItem(row, 4, self._make_barcode_item(r))

            if int(r.get("stock") or 0) <= int(r.get("min_stock") or 0):
                self._mark_row_low_stock(row)

        self.table.clearSelection()
        self._on_selection_changed()

    def _make_stock_item(self, row_data):
        from PySide6.QtWidgets import QTableWidgetItem

        item = QTableWidgetItem(str(row_data.get("stock") or 0))
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _mark_row_low_stock(self, row):
        from PySide6.QtGui import QBrush, QColor

        brush = QBrush(QColor("#ffe0b2"))
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(brush)

    def _make_name_item(self, row_data):
        item = self._create_item(row_data["name"] or "")
        item.setData(Qt.UserRole, row_data["id"])
        return item

    def _make_money_item(self, value):
        item = self._create_item(value)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _make_barcode_item(self, row_data):
        item = self._create_item(row_data["barcode"] or "")
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _create_item(self, value):
        from PySide6.QtWidgets import QTableWidgetItem
        from core.utils_format import fmt_money  # import lazy para evitar dependencias circulares en tests

        display = fmt_money(value) if isinstance(value, int) else str(value)
        return QTableWidgetItem(display)

    def new_product(self):
        dlg = ProductDialog(self)
        if dlg.exec() != ProductDialog.Accepted or not dlg.result:
            return

        data = dlg.result
        try:
            ps.create_product(
                name=data["name"],
                sale_price=data["sale_price"],
                purchase_price=data["purchase_price"],
                barcode=data["barcode"],
                stock=data["stock"],
                min_stock=data["min_stock"],
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear el producto:\n{e}")
            return

        self.reload()

    def edit_selected(self, row=None, col=None):
        pid = self._selected_product_id()
        if not pid:
            return

        data = ps.get_product(pid)
        if not data:
            QMessageBox.warning(self, "Editar", "No se pudo cargar el producto.")
            return

        dlg = ProductDialog(self, data=data)
        if dlg.exec() != ProductDialog.Accepted or not dlg.result:
            return

        new_data = dlg.result
        try:
            ps.update_product(
                pid,
                name=new_data["name"],
                sale_price=new_data["sale_price"],
                purchase_price=new_data["purchase_price"],
                barcode=new_data["barcode"],
                stock=new_data["stock"],
                min_stock=new_data["min_stock"],
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

        try:
            ps.delete_product(pid)
            self.reload()
            return
        except ValueError as ve:
            resp = QMessageBox.question(
                self,
                "Producto con historial",
                (
                    f"{ve}\n\n"
                    "En vez de borrarlo (lo que rompería el historial de ventas ya "
                    "registradas), puedes desactivarlo: ya no aparecerá en las "
                    "búsquedas ni en el punto de venta, pero se conserva su "
                    "historial de ventas.\n\n"
                    "¿Deseas desactivar el producto?"
                ),
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
            try:
                ps.desactivar_producto(pid)
                self.reload()
                return
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo desactivar el producto:\n{e}",
                )
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo eliminar el producto:\n{e}")
            return
