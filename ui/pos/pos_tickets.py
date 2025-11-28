# ui/pos/pos_tickets.py

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QListWidgetItem

from core import ticket_service as ts


class POSTicketsMixin:
    """
    Mixin para manejar la lista de tickets abiertos y acciones asociadas.

    Asume que la clase hija (POSView) tiene:
      - self.list_tickets (QListWidget)
      - self.current_ticket_id (int o None)
      - self.in_ticket_name (QLineEdit)
      - self.in_search (QLineEdit)
      - self.clear_ticket_ui()
      - self.load_ticket(ticket_id: int)
    """

    # === Tickets ===
    def reload_tickets(self, initial: bool = False):
        """Carga todos los tickets abiertos en la lista de la izquierda."""
        self.list_tickets.clear()

        for t in ts.list_open_tickets():
            name = (t.get("name") or f"Ticket {t['id']}").strip()
            total = int(t.get("pending_total") or 0)  # por si luego quieres mostrarlo
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, int(t["id"]))
            self.list_tickets.addItem(it)

        # Seleccionar el primero al inicio
        if self.list_tickets.count() and initial:
            self.list_tickets.setCurrentRow(0)

        # Si no hay tickets, limpiar UI
        if self.list_tickets.count() == 0:
            self.current_ticket_id = None
            self.clear_ticket_ui()

    def _refresh_tickets_sidebar(self):
        """Recarga la lista de tickets manteniendo seleccionado el actual."""
        current_id = self.current_ticket_id
        self.reload_tickets(initial=False)

        if current_id is None:
            return

        for i in range(self.list_tickets.count()):
            it = self.list_tickets.item(i)
            if it.data(Qt.UserRole) == current_id:
                self.list_tickets.setCurrentRow(i)
                break

    def on_ticket_selected(self):
        """Cuando el usuario selecciona un ticket en la lista."""
        item = self.list_tickets.currentItem()
        if not item:
            return

        tid = item.data(Qt.UserRole)
        if tid is None:
            return

        self.load_ticket(int(tid))

    def new_ticket(self):
        """Crea un nuevo ticket (usando el nombre ingresado si existe)."""
        ts.create_ticket(self.in_ticket_name.text().strip() or None)
        self.reload_tickets(initial=False)
        # seleccionar el primero (el más nuevo queda arriba con tu lógica actual)
        if self.list_tickets.count() > 0:
            self.list_tickets.setCurrentRow(0)
        self.in_search.setFocus()

    def rename_ticket(self):
        """Renombra el ticket actual usando el texto del campo."""
        if not self.current_ticket_id:
            return

        ts.rename_ticket(
            self.current_ticket_id,
            self.in_ticket_name.text().strip() or None
        )

        self.reload_tickets(initial=False)

        # Limpiar la casilla del nombre del ticket y volver al buscador
        self.in_ticket_name.clear()
        self.in_search.setFocus()

    def delete_ticket(self):
        """Elimina el ticket actual sin cobrar (previa confirmación)."""
        if not self.current_ticket_id:
            return

        if QMessageBox.question(
            self,
            "Eliminar",
            "¿Eliminar este ticket sin cobrar?"
        ) != QMessageBox.Yes:
            return

        ts.delete_ticket(self.current_ticket_id)
        self.reload_tickets(initial=False)
        self.in_search.setFocus()
