# ui/pos/pos_shortcuts.py

from PySide6.QtCore import Qt, QEvent

from core import ticket_service as ts


class POSShortcutsMixin:
    """
    Mixin para manejar:
      - Atajos de teclado (+/- y flechas) en tabla y buscador
      - Cambio rápido de cantidades
      - Click en columna X para borrar
      - Foco rápido en tabla/búsqueda

    Asume que la clase hija (POSView) tiene:
      - self.table (QTableWidget)
      - self.in_search (QLineEdit)
      - self.current_ticket_id
      - self._preserve_table_focus
      - self._selected_line_id (opcional, para recordar línea)
      - métodos:
          * self.load_ticket(ticket_id: int)
          * self._refresh_tickets_sidebar()
    """

    # === Foco rápido ===
    def _focus_table(self):
        """Pone el foco en la tabla del ticket y selecciona una fila para navegar con ↑/↓."""
        if self.table.rowCount() == 0:
            return

        row = self.table.currentRow()
        if row < 0:
            row = 0

        self.table.setCurrentCell(row, 1)  # columna Cant
        self.table.setFocus()

    def _focus_search(self):
        """Vuelve el foco al campo de búsqueda de productos."""
        self.in_search.setFocus()
        self.in_search.selectAll()

    # === Cambio rápido de cantidad ===
    def _change_current_qty(self, delta: int):
        """
        Cambia la cantidad de la fila actualmente seleccionada en la tabla
        sumando 'delta' (por ejemplo +1 o -1).
        """
        if not self.current_ticket_id:
            return

        row = self.table.currentRow()
        if row < 0:
            return

        prod_cell = self.table.item(row, 0)   # columna Producto
        qty_item = self.table.item(row, 1)    # columna Cant
        if not prod_cell or not qty_item:
            return

        line_id = prod_cell.data(Qt.UserRole)
        if line_id is None:
            return

        # Leer cantidad actual
        try:
            current_qty = int(qty_item.text())
        except Exception:
            current_qty = 1

        new_qty = current_qty + delta
        if new_qty <= 0:
            # No permitimos cantidades 0 o negativas
            return

        # Actualizar en BD
        ts.update_item_qty(int(line_id), new_qty)

        # Recargar tabla manteniendo foco en la tabla
        self._preserve_table_focus = True
        self.load_ticket(self.current_ticket_id)
        self._preserve_table_focus = False

        # Restaurar selección en la misma fila (o la última si se acortó la tabla)
        if self.table.rowCount() > 0:
            new_row = min(row, self.table.rowCount() - 1)
            self.table.setCurrentCell(new_row, 1)
            self.table.setFocus()

        # Actualizar barra lateral
        self._refresh_tickets_sidebar()

    # === Trackear la línea seleccionada (para integrarse con load_ticket nuevo) ===
    def _on_current_cell_changed(self, row, column, prev_row, prev_column):
        """Actualiza el ID real de la línea seleccionada cada vez que cambia la fila."""
        if row < 0:
            return
        prod_cell = self.table.item(row, 0)
        if prod_cell:
            self._selected_line_id = prod_cell.data(Qt.UserRole)

    # === Atajos de teclado en tabla y búsqueda ===
    def eventFilter(self, obj, event):
        """
        Atajos de teclado:
        - En la TABLA:
            + y -  -> aumentan / disminuyen cantidad del ítem seleccionado.
            ↑ y ↓  -> navegación normal (deja que QTableWidget la maneje).
        - En la BÚSQUEDA (in_search):
            + y -  -> aumentan / disminuyen cantidad del ítem seleccionado.
            ↑ y ↓  -> cambian la fila seleccionada en la tabla, PERO
                      sin mover el foco fuera de la casilla de búsqueda.
        """
        if event.type() == QEvent.KeyPress:
            key = event.key()

            # --- Atajos cuando el foco está en la TABLA ---
            if obj is self.table:
                # Detectar + (incluye teclados donde '+' comparte con '=')
                if key in (Qt.Key_Plus, Qt.Key_Equal):
                    self._change_current_qty(+1)
                    return True  # manejamos nosotros

                # Detectar - (incluye teclados donde '-' comparte con '_')
                if key in (Qt.Key_Minus, Qt.Key_Underscore):
                    self._change_current_qty(-1)
                    return True  # manejamos nosotros

                # Flechas ↑/↓: dejamos que la tabla navegue normalmente
                return super().eventFilter(obj, event)

            # --- Atajos cuando el foco está en la BÚSQUEDA ---
            if obj is self.in_search:
                # + / - modifican cantidad del ítem seleccionado en la tabla
                if key in (Qt.Key_Plus, Qt.Key_Equal):
                    self._change_current_qty(+1)
                    return True  # IMPORTANTE: no dejar que QLineEdit procese la tecla

                if key in (Qt.Key_Minus, Qt.Key_Underscore):
                    self._change_current_qty(-1)
                    return True

                # Flecha ARRIBA: seleccionar ítem anterior en la tabla
                if key == Qt.Key_Up:
                    if self.table.rowCount() > 0:
                        row = self.table.currentRow()
                        if row < 0:
                            row = self.table.rowCount() - 1
                        else:
                            row = max(0, row - 1)
                        self.table.setCurrentCell(row, 1)  # columna Cant
                    return True  # no dejamos que el QLineEdit cambie selección/cursor

                # Flecha ABAJO: seleccionar ítem siguiente en la tabla
                if key == Qt.Key_Down:
                    if self.table.rowCount() > 0:
                        row = self.table.currentRow()
                        if row < 0:
                            row = 0
                        else:
                            row = min(self.table.rowCount() - 1, row + 1)
                        self.table.setCurrentCell(row, 1)
                    return True

        return super().eventFilter(obj, event)

    # === Click en la X para borrar línea ===
    def _on_table_cell_clicked(self, row: int, column: int):
        """Si se hace clic en la columna de la X, elimina la línea; si no, permite editar cantidad."""
        # Columna 4 = X (eliminar línea)
        if column == 4:
            if not self.current_ticket_id:
                return

            prod_cell = self.table.item(row, 0)
            if not prod_cell:
                return

            line_id = prod_cell.data(Qt.UserRole)
            if line_id is None:
                return

            ts.remove_item(int(line_id))
            self.load_ticket(self.current_ticket_id)
            self._refresh_tickets_sidebar()
            self.in_search.setFocus()
            return

        # Cualquier otra columna: solo enfocar la cantidad, SIN abrir editor
        qty_item = self.table.item(row, 1)
        if qty_item:
            self.table.setCurrentCell(row, 1)
            # Mantener _selected_line_id coherente con la fila clickeada
            prod_cell = self.table.item(row, 0)
            if prod_cell:
                self._selected_line_id = prod_cell.data(Qt.UserRole)

    # === Suprimir: borrar fila seleccionada ===
    def _delete_current_row(self):
        """Elimina la línea actualmente seleccionada en la tabla (atajo Supr)."""
        if not self.current_ticket_id:
            return

        row = self.table.currentRow()
        if row < 0:
            return

        prod_cell = self.table.item(row, 0)
        if not prod_cell:
            return

        line_id = prod_cell.data(Qt.UserRole)
        if line_id is None:
            return

        ts.remove_item(int(line_id))

        # Recargar manteniendo foco en la tabla
        self._preserve_table_focus = True
        self.load_ticket(self.current_ticket_id)
        self._preserve_table_focus = False
        self._refresh_tickets_sidebar()

        # Seleccionar una fila coherente tras el borrado
        if self.table.rowCount() > 0:
            new_row = min(row, self.table.rowCount() - 1)
            self.table.setCurrentCell(new_row, 1)
            self.table.setFocus()
