# ui/pos/pos_table.py

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import QTableWidgetItem
from core.utils_format import fmt_money
from core import ticket_service as ts


class POSTableMixin:
    """
    Mixin para manejar SOLO la carga de la tabla del POS.
    Asume que la clase hija tiene:
      - self.table (QTableWidget)
      - self._updating_table (bool)
    """

    def load_ticket_table(self, ticket_id: int):
        """Carga las líneas del ticket en la tabla.

        Columnas:
        0: Producto (UserRole = line_id)
        1: Cantidad (editable)
        2: P.Unit (solo lectura)
        3: Total (solo lectura)
        4: ✕ (solo lectura, texto)
        """
        self._updating_table = True
        try:
            self.table.setRowCount(0)

            for it in ts.list_items(ticket_id):
                r = self.table.rowCount()
                self.table.insertRow(r)

                # Producto
                prod_item = QTableWidgetItem(it["product_name"])
                prod_item.setData(Qt.UserRole, it["id"])  # line_id
                self.table.setItem(r, 0, prod_item)

                # Cantidad (editable)
                qty_item = QTableWidgetItem(str(it["qty"]))
                qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, 1, qty_item)

                # Precio unitario
                pu_item = QTableWidgetItem(fmt_money(it["unit_price"]))
                pu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                pu_item.setFlags(pu_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 2, pu_item)

                # Total línea
                tot_item = QTableWidgetItem(fmt_money(it["line_total"]))
                tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tot_item.setFlags(tot_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 3, tot_item)

                # Columna de borrar (X) - Rojo suave
                del_item = QTableWidgetItem("✕")
                del_item.setTextAlignment(Qt.AlignCenter)
                del_item.setFlags(del_item.flags() & ~Qt.ItemIsEditable)
                
                # Estilo rojo suave
                del_item.setBackground(QBrush(QColor("#ffcccc")))  # Fondo rojo suave
                del_item.setForeground(QBrush(QColor("#cc0000")))  # Texto rojo oscuro
                font = QFont()
                font.setBold(True)
                del_item.setFont(font)
                
                self.table.setItem(r, 4, del_item)

        finally:
            self._updating_table = False
