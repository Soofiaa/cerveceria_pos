# ui/pos/pos_search.py

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QDialog

from core import product_service as ps
from core import ticket_service as ts
from ui.common_product_dialog import CommonProductDialog


class POSSearchMixin:
    """
    Mixin para manejar la lógica de búsqueda de productos y 'Producto común'.

    Asume que la clase hija (POSView) tiene:
      - self.current_ticket_id
      - self.new_ticket()
      - self.load_ticket(ticket_id)
      - self._refresh_tickets_sidebar()
      - self.in_search (QLineEdit)
      - self.suggest_model (QStringListModel)
      - self.suggest_map (dict)
      - self.selected_product_id
      - self.table (QTableWidget)
      - self._preserve_table_focus (bool)
    """

    # --- Utilidad: asegurar existencia de 'Producto común' ---
    def _ensure_common_product_id(self) -> int:
        # Busca (o crea) "Producto común"
        candidates = ps.list_products("Producto común")
        for p in candidates:
            if (p["name"] or "").strip().lower() == "producto común":
                return p["id"]
        return ps.create_product(
            name="Producto común",
            sale_price=0,
            purchase_price=0,
            barcode=None
        )

    # === Autocompletar ===
    def update_suggestions(self, text: str):
        text = (text or "").strip()
        items = []
        self.suggest_map.clear()
        self.selected_product_id = None

        if len(text) >= 1:
            for p in ps.list_products(text)[:30]:
                name = p["name"]
                if name not in self.suggest_map:
                    self.suggest_map[name] = p["id"]
                    items.append(name)

        self.suggest_model.setStringList(items)

    def on_suggestion_chosen(self, chosen_text: str):
        """Cuando el usuario elige una sugerencia del autocompletar."""
        self.selected_product_id = self.suggest_map.get(chosen_text)

        # Dejamos que el QCompleter termine y luego agregamos + limpiamos.
        QTimer.singleShot(0, self.add_item_by_search)

    # === Ítems ===
    def add_common_item_dialog(self):
        """Abre el diálogo de 'Producto común' y agrega la línea al ticket."""
        if not self.current_ticket_id:
            self.new_ticket()

        dlg = CommonProductDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        unit_price = dlg.price_value
        qty = dlg.qty_value
        if unit_price is None or unit_price <= 0 or qty <= 0:
            QMessageBox.warning(self, "Producto común", "Datos inválidos.")
            return

        pid = self._ensure_common_product_id()
        ts.add_item(self.current_ticket_id, pid, qty=qty, unit_price=unit_price)

        # Recargar tabla del ticket y actualizar panel izquierdo
        self.load_ticket(self.current_ticket_id)
        self._refresh_tickets_sidebar()

        # Limpiar completamente la casilla de búsqueda
        self.in_search.clear()
        self.selected_product_id = None
        self.update_suggestions("")
        self.in_search.setFocus()

    def add_item_by_search(self):
        """Agrega producto por nombre/código: cantidad 1, precio del producto."""
        if not self.current_ticket_id:
            self.new_ticket()

        pid = self.selected_product_id
        if not pid:
            q = (self.in_search.text() or "").strip()
            if not q:
                QMessageBox.warning(self, "Agregar", "Escribe nombre o código para buscar.")
                return
            cand = ps.list_products(q)
            if not cand:
                QMessageBox.warning(self, "Producto", "No se encontró producto.")
                return
            pid = cand[0]["id"]

        prod = ps.get_product(pid)
        ts.add_item(self.current_ticket_id, pid, qty=1, unit_price=prod["sale_price"])

        # Limpiar casilla de búsqueda y sugerencias
        self.in_search.clear()
        self.selected_product_id = None
        self.update_suggestions("")

        # Recargar la tabla del ticket (sin preocuparnos del foco aún)
        self._preserve_table_focus = True
        self.load_ticket(self.current_ticket_id)
        self._preserve_table_focus = False

        # Seleccionar automáticamente la última fila (producto recién agregado)
        last_row = self.table.rowCount() - 1
        if last_row >= 0:
            self.table.setCurrentCell(last_row, 1)  # columna Cant

        # Actualizar panel izquierdo de tickets
        self._refresh_tickets_sidebar()

        # Mantener flujo rápido: foco de vuelta en el buscador
        self.in_search.setFocus()


    def _warmup_common_product(self):
        """Crea/busca el Producto común al inicio para evitar la espera en el primer uso."""
        try:
            self._ensure_common_product_id()
        except Exception:
            # No rompemos la UI si falla algo en precarga
            pass
