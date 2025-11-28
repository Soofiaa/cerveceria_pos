# ui/pos/pos_actions.py

from PySide6.QtWidgets import QMessageBox

from core import ticket_service as ts
from core import sales_service as ss
from core.utils_format import fmt_money
from ui.charge_dialog import ChargeDialog


class POSActionsMixin:
    """
    Mixin para acciones sobre el ticket actual:
      - Refrescar totales
      - Limpiar ticket (UI + items)
      - Eliminar una línea directa
      - Cobrar ticket

    Asume que la clase hija (POSView) tiene:
      - self.current_ticket_id
      - self.table
      - self.lbl_totals (QLabel)
      - self.in_search (QLineEdit)
      - self.in_ticket_name (QLineEdit)
      - métodos:
          * self.load_ticket(ticket_id: int)
          * self.reload_tickets(initial: bool = False)
          * self._refresh_tickets_sidebar()
      - señal:
          * self.sale_completed (Signal)
    """

    # === Totales ===
    def refresh_totals(self):
        """Recalcula y actualiza el total del ticket actual en la etiqueta."""
        if not self.current_ticket_id:
            self.lbl_totals.setText("Total: $0")
            return

        _, _, tot = ts.calc_ticket_totals(self.current_ticket_id)
        self.lbl_totals.setText(f"Total: {fmt_money(tot)}")

    def clear_ticket_ui(self):
        """Limpia la UI del ticket cuando no hay ticket seleccionado."""
        self.in_ticket_name.clear()
        self.table.setRowCount(0)
        self.lbl_totals.setText("Total: $0")

    # === Ítems del ticket ===
    def clear_ticket_items(self):
        """Elimina todos los ítems del ticket actual."""
        if not self.current_ticket_id:
            return

        for it in ts.list_items(self.current_ticket_id):
            ts.remove_item(it["id"])

        self.load_ticket(self.current_ticket_id)
        self._refresh_tickets_sidebar()
        self.in_search.setFocus()

    def _remove_line_direct(self, line_id: int):
        """Elimina una línea específica (se usa por atajo u otras acciones directas)."""
        if not self.current_ticket_id:
            return

        ts.remove_item(int(line_id))
        self.load_ticket(self.current_ticket_id)
        self._refresh_tickets_sidebar()
        self.in_search.setFocus()

    # === Cobro ===
    def charge_ticket(self):
        """Abre el diálogo de cobro y registra la venta si todo es válido."""
        if not self.current_ticket_id:
            return

        _, _, tot = ts.calc_ticket_totals(self.current_ticket_id)
        if tot <= 0:
            QMessageBox.warning(self, "Cobrar", "El ticket está vacío.")
            return

        dlg = ChargeDialog(total=tot, parent=self)
        if dlg.exec() != ChargeDialog.Accepted:
            return

        pay_method = dlg.selected_method or "efectivo"

        # Guardar último nombre escrito en el ticket antes de cobrar
        ts.rename_ticket(self.current_ticket_id, self.in_ticket_name.text().strip() or None)
        ts.set_pay_method(self.current_ticket_id, pay_method)

        try:
            sid = ss.cobrar_ticket(self.current_ticket_id)
            QMessageBox.information(
                self,
                "Venta",
                f"Venta registrada (ID {sid}) — Pago: {pay_method}."
            )

            # Recargar tickets abiertos y notificar al resto de la app
            self.reload_tickets(initial=True)
            self.sale_completed.emit()  # el MainWindow puede escuchar esto

            # Volvemos al buscador
            self.in_search.setFocus()

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
