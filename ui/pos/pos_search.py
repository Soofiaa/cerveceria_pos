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
        """
        Cuando el usuario elige una sugerencia del autocompletar.

        Solo marcamos el producto seleccionado; el agregado real lo
        hace add_item_by_search cuando el usuario presiona Enter.
        """
        self.selected_product_id = self.suggest_map.get(chosen_text)
        # Importante: NO llamamos aquí a add_item_by_search


    # === Ítems ===
    def add_common_item_dialog(self):
        """Abre el diálogo de producto común y agrega la línea al ticket."""
        if not self.current_ticket_id:
            self.new_ticket()

        dlg = CommonProductDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_data()
        name = data["name"]
        qty = data["qty"]
        unit_price = data["unit_price"]
        gain_type = data["gain_type"]      # "%" o "$"
        gain_value = data["gain_value"]    # int o None

        # ==== Calcular ganancia por unidad (gain_per_unit) ====
        # Regla:
        # - Si gain_value es None -> 0 (no afecta reportes)
        # - Si gain_type == "%" -> unit_price * (gain_value/100)
        # - Si gain_type == "$" -> gain_value directo
        if gain_value is None:
            gain_per_unit = 0
        else:
            if gain_type == "%":
                gain_per_unit = int(unit_price * (gain_value / 100.0))
            else:  # "$"
                gain_per_unit = int(gain_value)

        # Guardar línea de producto común en el ticket
        ts.add_common_item(
            ticket_id=self.current_ticket_id,
            name=name,
            qty=qty,
            unit_price=unit_price,
            gain_per_unit=gain_per_unit,
        )

        # Recargar tabla
        self.load_ticket(self.current_ticket_id)
    

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
