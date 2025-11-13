from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QTableWidgetItem
from core.utils_format import fmt_money
from core import ticket_service as ts
from .pos_utils import make_remove_button

class POSTableMixin:
    def setup_table_behavior(self):
        """Instala el filtro de eventos para flechas ↑ y ↓."""
        self.table.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Permite modificar cantidad con flechas ↑↓."""
        if obj is self.table and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Up, Qt.Key_Down):
                row = self.table.currentRow()
                if row < 0:
                    return True
                qty_item = self.table.item(row, 1)
                if not qty_item:
                    return True
                try:
                    val = int(qty_item.text())
                except Exception:
                    val = 1
                val += 1 if event.key() == Qt.Key_Up else -1
                if val <= 0:
                    return True
                qty_item.setText(str(val))  # dispara on_table_item_changed
                return True
        return super().eventFilter(obj, event)

    def load_ticket_table(self, ticket_id: int):
        """Carga las líneas en la tabla POS."""
        self._updating_table = True
        self.table.setRowCount(0)
        try:
            for it in ts.list_items(ticket_id):
                r = self.table.rowCount()
                self.table.insertRow(r)

                prod_item = QTableWidgetItem(it["product_name"])
                prod_item.setData(Qt.UserRole, it["id"])
                self.table.setItem(r, 0, prod_item)

                qty_item = QTableWidgetItem(str(it["qty"]))
                qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, 1, qty_item)

                pu_item = QTableWidgetItem(fmt_money(it["unit_price"]))
                pu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, 2, pu_item)

                tot_item = QTableWidgetItem(fmt_money(it["line_total"]))
                tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, 3, tot_item)

                btn = make_remove_button(it["id"], self._remove_line_direct)
                self.table.setCellWidget(r, 4, btn)
        finally:
            self._updating_table = False
