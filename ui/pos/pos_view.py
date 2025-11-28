# ui/pos/pos_view.py
from PySide6.QtCore import Qt, QStringListModel, QTimer, Signal, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QListWidget,
    QSplitter, QCompleter, QLineEdit, QAbstractItemView
)

from core import ticket_service as ts

from ui.pos.pos_table import POSTableMixin
from ui.pos.pos_search import POSSearchMixin
from ui.pos.pos_tickets import POSTicketsMixin
from ui.pos.pos_actions import POSActionsMixin
from ui.pos.pos_widgets import IntSpinDelegate, SearchLine


class POSView(
    QWidget,
    POSTableMixin,
    POSSearchMixin,
    POSTicketsMixin,
    POSActionsMixin,
):
    # Señal que se emitirá cuando se complete una venta
    sale_completed = Signal()

    def __init__(self):
        super().__init__()
        self.current_ticket_id = None
        self._updating_table = False
        self._preserve_table_focus = False

        self._selected_line_id = None

        # === Panel izquierdo: Tickets abiertos ===
        self.list_tickets = QListWidget()
        self.list_tickets.setObjectName("TicketList")

        self.btn_new = QPushButton("Nuevo")
        self.btn_new.setProperty("buttonType", "primary")
        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setProperty("buttonType", "danger")

        self.btn_new.clicked.connect(self.new_ticket)
        self.btn_delete.clicked.connect(self.delete_ticket)
        self.list_tickets.itemSelectionChanged.connect(self.on_ticket_selected)

        left = QVBoxLayout()
        tickets_title = QLabel("Tickets abiertos")
        tickets_title.setObjectName("SidebarTitle")   # <<--- CAMBIO AQUÍ
        left.addWidget(tickets_title)
        left.addWidget(self.list_tickets)

        row_left = QHBoxLayout()
        row_left.addWidget(self.btn_new)
        row_left.addWidget(self.btn_delete)
        left.addLayout(row_left)

        left_widget = QWidget()
        left_widget.setObjectName("Sidebar")
        self.list_tickets.setObjectName("TicketList")
        left_widget.setLayout(left)

        # === Panel derecho: datos del ticket + ítems ===
        self.in_ticket_name = QLineEdit()
        self.in_ticket_name.setPlaceholderText("Nombre del ticket (opcional)")

        self.btn_rename = QPushButton("Renombrar")
        self.btn_rename.setProperty("buttonType", "ghost")
        self.btn_rename.clicked.connect(self.rename_ticket)

        top_right = QHBoxLayout()
        top_right.addWidget(QLabel("Ticket:"))
        top_right.addWidget(self.in_ticket_name)
        top_right.addWidget(self.btn_rename)

        # --- Búsqueda + producto común ---
        self.in_search = SearchLine()
        self.in_search.setPlaceholderText("Buscar producto o código (Enter para agregar)")

        # Autocompletar
        self.suggest_model = QStringListModel(self)
        self.completer = QCompleter(self.suggest_model, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.in_search.setCompleter(self.completer)

        self.suggest_map = {}
        self.selected_product_id = None

        self.in_search.textEdited.connect(self.update_suggestions)
        self.completer.activated.connect(self.on_suggestion_chosen)
        self.in_search.returnPressed.connect(self.add_item_by_search)

        self.btn_add_common = QPushButton("Agregar producto común")
        self.btn_add_common.setProperty("buttonType", "ghost")
        self.btn_add_common.clicked.connect(self.add_common_item_dialog)

        add_row = QHBoxLayout()
        add_row.addWidget(self.in_search, 1)
        add_row.addStretch()
        add_row.addWidget(self.btn_add_common)

        # === Tabla: Producto | Cant | P.Unit | Total | ✕ ===
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Producto", "Cant", "P.Unit", "Total", ""])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setColumnWidth(4, 48)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        self.table.setEditTriggers(
            QAbstractItemView.EditKeyPressed
        )

        self.table.setItemDelegateForColumn(1, IntSpinDelegate(self))
        self.table.itemChanged.connect(self.on_table_item_changed)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        
        # Permitir atajos de teclado (+/- y navegación) tanto en la tabla como en la búsqueda
        self.table.installEventFilter(self)
        self.in_search.installEventFilter(self)

        # === Totales + botones inferiores ===
        self.lbl_totals = QLabel("Total: $0")
        self.lbl_totals.setObjectName("TotalsBadge")

        # --- Estilo tipo 'card' para el total ---
        font_total = self.lbl_totals.font()
        font_total.setBold(True)
        font_total.setPointSize(20)
        self.lbl_totals.setFont(font_total)

        self.lbl_totals.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_totals.setMinimumHeight(70)

        self.btn_clear = QPushButton("Limpiar ticket")
        self.btn_clear.setProperty("buttonType", "ghost")
        self.btn_charge = QPushButton("F12 - COBRAR")
        self.btn_charge.setProperty("buttonType", "primary")

        self.btn_clear.clicked.connect(self.clear_ticket_items)
        self.btn_charge.clicked.connect(self.charge_ticket)

        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_clear)
        bottom.addStretch()
        bottom.addWidget(self.btn_charge)

        right = QVBoxLayout()
        right.setContentsMargins(6, 6, 6, 6)
        right.setSpacing(6)
        right.addLayout(top_right)
        right.addLayout(add_row)
        right.addWidget(self.table)
        right.addWidget(self.lbl_totals)
        right.addLayout(bottom)

        right_widget = QWidget()
        right_widget.setObjectName("ContentArea")
        right_widget.setLayout(right)

        # === Splitter principal ===
        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 800])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)  # margen interno
        layout.setSpacing(10)                       # espacio entre elementos
        layout.addWidget(splitter)


        # --- Ajustes de tamaños cómodos ---
        self.in_ticket_name.setMinimumHeight(32)
        self.in_search.setMinimumHeight(32)
        for btn in [
            self.btn_new, self.btn_delete, self.btn_rename,
            self.btn_add_common, self.btn_clear, self.btn_charge
        ]:
            btn.setMinimumHeight(32)

        # --- Atajos de teclado ---
        # F12 para cobrar
        shortcut_charge = QShortcut(QKeySequence("F12"), self)
        shortcut_charge.activated.connect(self.charge_ticket)
        
        # Suprimir para eliminar la línea seleccionada del ticket
        shortcut_del = QShortcut(QKeySequence("Delete"), self)
        shortcut_del.activated.connect(self._delete_current_row)
        
        # F2: ir a la tabla del ticket para navegar con ↑/↓ y usar +/-
        shortcut_focus_table = QShortcut(QKeySequence("F2"), self)
        shortcut_focus_table.activated.connect(self._focus_table)

        # F3: volver rápido al buscador de productos
        shortcut_focus_search = QShortcut(QKeySequence("F3"), self)
        shortcut_focus_search.activated.connect(self._focus_search)

        self.reload_tickets(initial=True)

        # --- Tamaños cómodos para usuarios no técnicos ---
        # Campos de texto más grandes
        self.in_ticket_name.setMinimumHeight(34)
        self.in_search.setMinimumHeight(34)

        # Botones principales más grandes
        for btn in [
            self.btn_new, self.btn_delete,
            self.btn_rename, self.btn_add_common,
            self.btn_clear, self.btn_charge
        ]:
            btn.setMinimumHeight(38)

        # Filas de tabla más altas
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setMinimumSectionSize(44)

        # Foco inicial en la búsqueda
        self.in_search.setFocus()

        # Precarga silenciosa del "Producto común" para evitar demora la primera vez
        QTimer.singleShot(0, self._warmup_common_product)


    # === Carga y tabla ===
    def load_ticket(self, ticket_id: int):
        """Producto | Cant (editable) | P.Unit | Total | ✕"""
        # Guardamos el ID actual del ticket
        self.current_ticket_id = int(ticket_id)

        # Obtenemos el ticket desde la capa de servicio
        t = ts.get_ticket(self.current_ticket_id)
        if not t:
            self.clear_ticket_ui()
            return

        # Limpiamos el nombre visible (el nombre real se muestra en la lista de la izquierda)
        self.in_ticket_name.clear()

        # Recordar la fila seleccionada ANTES de recargar,
        # solo si queremos preservar contexto desde la acción que nos llamó.
        prev_row = self.table.currentRow() if self._preserve_table_focus else -1

        # --- Cargar la tabla usando el mixin POSTableMixin ---
        self._updating_table = True
        try:
            # Esta función viene desde POSTableMixin (pos_table.py)
            self.load_ticket_table(self.current_ticket_id)
        finally:
            self._updating_table = False

        # Actualizamos los totales del ticket
        self.refresh_totals()

        # --- Restaurar selección REAL basada en _selected_line_id ---
        restored = False
        if self._selected_line_id is not None:
            for r in range(self.table.rowCount()):
                prod_cell = self.table.item(r, 0)
                if prod_cell and prod_cell.data(Qt.UserRole) == self._selected_line_id:
                    self.table.setCurrentCell(r, 1)  # columna Cant
                    restored = True
                    break

        # Si no se pudo restaurar (ej: línea eliminada)
        if not restored and self.table.rowCount() > 0:
            # Si venimos de una acción de tabla y había fila previa, intentamos respetarla
            if self._preserve_table_focus and prev_row >= 0:
                row = min(prev_row, self.table.rowCount() - 1)
            else:
                row = 0

            self.table.setCurrentCell(row, 1)  # columna Cant

            # también actualizamos el ID seleccionado
            prod_cell = self.table.item(row, 0)
            if prod_cell:
                self._selected_line_id = prod_cell.data(Qt.UserRole)

        # Solo devolvemos el foco al buscador si NO venimos de una acción de tabla
        if not self._preserve_table_focus:
            self.in_search.setFocus()


    # === Edición de cantidad en línea ===
    def on_table_item_changed(self, item: QTableWidgetItem):
        """Se dispara cuando cambia una celda; solo nos importa la columna Cant (1)."""
        if self._updating_table or item.column() != 1:
            return

        row = item.row()
        prod_cell = self.table.item(row, 0)
        if not prod_cell:
            return

        line_id = prod_cell.data(Qt.UserRole)
        if line_id is None:
            return

        # Validar nueva cantidad
        try:
            new_qty = int(item.text())
            if new_qty <= 0:
                raise ValueError
        except Exception:
            QMessageBox.warning(self, "Cantidad inválida", "Debe ser un número mayor que 0.")
            # Recargar dejando todo consistente
            self._preserve_table_focus = False
            self.load_ticket(self.current_ticket_id)
            return

        # ===== Actualizar en BD =====
        ts.update_item_qty(line_id, new_qty)

        # ===== Recargar ticket y sidebar =====
        self._preserve_table_focus = True
        try:
            self.load_ticket(self.current_ticket_id)
            self._refresh_tickets_sidebar()
        finally:
            self._preserve_table_focus = False

        # ===== Volver a seleccionar la MISMA línea que se editó =====
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, 0)
            if cell and cell.data(Qt.UserRole) == line_id:
                self.table.setCurrentCell(r, 1)  # columna Cant
                break


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

        # Eliminar ítem en BD
        ts.remove_item(int(line_id))

        # Recargar manteniendo foco/selección coherente en la tabla
        self._preserve_table_focus = True
        self.load_ticket(self.current_ticket_id)
        self._preserve_table_focus = False
        self._refresh_tickets_sidebar()

        # Seleccionar una fila lógica tras el borrado
        if self.table.rowCount() > 0:
            new_row = min(row, self.table.rowCount() - 1)
            self.table.setCurrentCell(new_row, 1)
            self.table.setFocus()
        else:
            # Si ya no quedan ítems en el ticket, devolvemos el foco al buscador
            self.in_search.setFocus()
    
    
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

        # ===== Actualizar en BD =====
        ts.update_item_qty(int(line_id), new_qty)

        # ===== Recargar ticket y sidebar preservando la fila =====
        self._preserve_table_focus = True
        try:
            self.load_ticket(self.current_ticket_id)
            self._refresh_tickets_sidebar()
        finally:
            self._preserve_table_focus = False

        # Mantener la misma fila seleccionada,
        # PERO SIN cambiar el foco (si estaba en la búsqueda, sigue allí).
        if self.table.rowCount() > 0:
            new_row = min(row, self.table.rowCount() - 1)
            self.table.setCurrentCell(new_row, 1)
            # OJO: aquí ya NO llamamos a self.table.setFocus()


    def eventFilter(self, obj, event):
        """
        Atajos de teclado:
        - En la TABLA:
            + y -  -> aumentan / disminuyen cantidad del ítem seleccionado.
            Supr   -> elimina la línea seleccionada.
            ↑ y ↓  -> navegación normal (deja que QTableWidget la maneje).
        - En la BÚSQUEDA (in_search):
            + y -  -> aumentan / disminuyen cantidad del ítem seleccionado.
            Supr   -> elimina la línea seleccionada.
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

                # Suprimir: eliminar la línea seleccionada
                if key == Qt.Key_Delete:
                    self._delete_current_row()
                    return True

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

                # Suprimir: eliminar la línea seleccionada del ticket
                if key == Qt.Key_Delete:
                    self._delete_current_row()
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


    # === Cobro ===
    def showEvent(self, event):
        """Cuando se muestra la pestaña POS, devuelve el foco a Buscar producto."""
        super().showEvent(event)
        # Un pequeño delay para que Qt termine de dibujar y luego ponemos el foco
        QTimer.singleShot(0, self.in_search.setFocus)
