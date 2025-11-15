# ui/pos/pos_view.py
from PySide6.QtCore import Qt, QStringListModel, QTimer, Signal, QEvent
from PySide6.QtGui import QKeySequence, QShortcut, QBrush, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QListWidget,
    QListWidgetItem, QSplitter, QCompleter, QStyledItemDelegate, QSpinBox,
    QDialog
)

from core import product_service as ps
from core import ticket_service as ts
from core import sales_service as ss
from ui.charge_dialog import ChargeDialog
from ui.common_product_dialog import CommonProductDialog
from core.utils_format import fmt_money


# --- Delegate: cantidades editables en tabla ---
class IntSpinDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, minimum=1, maximum=10**6):
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum

    def createEditor(self, parent, option, index):
        spin = QSpinBox(parent)
        spin.setRange(self.minimum, self.maximum)
        spin.setAccelerated(True)
        spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return spin

    def setEditorData(self, editor, index):
        try:
            val = int(index.data() or 0)
        except Exception:
            val = self.minimum
        editor.setValue(max(self.minimum, min(self.maximum, val)))

    def setModelData(self, editor, model, index):
        model.setData(index, str(editor.value()))


class POSView(QWidget):
    # Señal que se emitirá cuando se complete una venta
    sale_completed = Signal()

    def __init__(self):
        super().__init__()
        self.current_ticket_id = None
        self._updating_table = False

        # Fuente un poco más grande para esta pantalla
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

        # === Panel izquierdo: Tickets abiertos ===
        self.list_tickets = QListWidget()
        self.btn_new = QPushButton("Nuevo")
        self.btn_delete = QPushButton("Eliminar")

        self.btn_new.clicked.connect(self.new_ticket)
        self.btn_delete.clicked.connect(self.delete_ticket)
        self.list_tickets.itemSelectionChanged.connect(self.on_ticket_selected)

        left = QVBoxLayout()
        left.addWidget(QLabel("Tickets abiertos"))
        left.addWidget(self.list_tickets)
        row_left = QHBoxLayout()
        row_left.addWidget(self.btn_new)
        row_left.addWidget(self.btn_delete)
        left.addLayout(row_left)

        left_widget = QWidget()
        left_widget.setLayout(left)

        # === Panel derecho: datos del ticket + ítems ===
        self.in_ticket_name = QLineEdit()
        self.in_ticket_name.setPlaceholderText("Nombre del ticket (opcional)")

        self.btn_rename = QPushButton("Renombrar")
        self.btn_rename.clicked.connect(self.rename_ticket)

        top_right = QHBoxLayout()
        top_right.addWidget(QLabel("Ticket:"))
        top_right.addWidget(self.in_ticket_name)
        top_right.addWidget(self.btn_rename)

        # --- Búsqueda + producto común ---
        self.in_search = QLineEdit()
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
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked |
            QTableWidget.EditKeyPressed |
            QTableWidget.SelectedClicked
        )
        self.table.setItemDelegateForColumn(1, IntSpinDelegate(self))
        self.table.itemChanged.connect(self.on_table_item_changed)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        
        # Permitir cambiar cantidad con flechas ↑/↓
        self.table.installEventFilter(self)


        # === Totales + botones inferiores ===
        self.lbl_totals = QLabel("Total: $0")

        self.btn_clear = QPushButton("Limpiar ticket")
        self.btn_charge = QPushButton("F12 - COBRAR")

        self.btn_clear.clicked.connect(self.clear_ticket_items)
        self.btn_charge.clicked.connect(self.charge_ticket)

        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_clear)
        bottom.addStretch()
        bottom.addWidget(self.btn_charge)

        right = QVBoxLayout()
        right.addLayout(top_right)
        right.addLayout(add_row)
        right.addWidget(self.table)
        right.addWidget(self.lbl_totals)
        right.addLayout(bottom)

        right_widget = QWidget()
        right_widget.setLayout(right)

        # === Splitter principal ===
        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 800])

        layout = QVBoxLayout(self)
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
        # Suprimir para eliminar la línea seleccionada
        shortcut_del = QShortcut(QKeySequence("Delete"), self.table)
        shortcut_del.activated.connect(self._delete_current_row)

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

    # --- Utilidades ---
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

    # === Tickets ===
    def reload_tickets(self, initial=False):
        self.list_tickets.clear()
        for t in ts.list_open_tickets():
            name = (t.get("name") or f"Ticket {t['id']}").strip()
            total = int(t.get("pending_total") or 0)
            it = QListWidgetItem(f"{name} — {fmt_money(total)}")
            it.setData(Qt.UserRole, int(t["id"]))
            self.list_tickets.addItem(it)
        if self.list_tickets.count() and initial:
            self.list_tickets.setCurrentRow(0)
        if self.list_tickets.count() == 0:
            self.current_ticket_id = None
            self.clear_ticket_ui()

    def on_ticket_selected(self):
        item = self.list_tickets.currentItem()
        if not item:
            return
        tid = item.data(Qt.UserRole)
        if tid is None:
            return
        self.load_ticket(int(tid))

    def new_ticket(self):
        ts.create_ticket(self.in_ticket_name.text().strip() or None)
        self.reload_tickets()
        self.list_tickets.setCurrentRow(0)
        self.in_search.setFocus()

    def rename_ticket(self):
        if not self.current_ticket_id:
            return
        ts.rename_ticket(
            self.current_ticket_id,
            self.in_ticket_name.text().strip() or None
        )
        self.reload_tickets()
        self.in_search.setFocus()

    def delete_ticket(self):
        if not self.current_ticket_id:
            return
        if QMessageBox.question(
            self,
            "Eliminar",
            "¿Eliminar este ticket sin cobrar?"
        ) != QMessageBox.Yes:
            return
        ts.delete_ticket(self.current_ticket_id)
        self.reload_tickets()
        self.in_search.setFocus()

    # === Ítems ===
    def add_common_item_dialog(self):
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

        self.load_ticket(self.current_ticket_id)

        # Limpiar completamente la casilla
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

        # Limpiar casilla
        self.in_search.clear()
        self.selected_product_id = None
        self.update_suggestions("")
        self.in_search.setFocus()

        self.load_ticket(self.current_ticket_id)

    # === Carga y tabla ===
    def load_ticket(self, ticket_id: int):
        """Producto | Cant (editable) | P.Unit | Total | ✕"""
        self.current_ticket_id = int(ticket_id)
        t = ts.get_ticket(self.current_ticket_id)
        if not t:
            self.clear_ticket_ui()
            return

        self.in_ticket_name.setText((t.get("name") or "").strip())

        self._updating_table = True
        try:
            self.table.setRowCount(0)
            for it in ts.list_items(self.current_ticket_id):
                r = self.table.rowCount()
                self.table.insertRow(r)

                prod_item = QTableWidgetItem(it["product_name"])
                prod_item.setData(Qt.UserRole, it["id"])
                self.table.setItem(r, 0, prod_item)

                qty_item = QTableWidgetItem(str(it["qty"]))
                qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                qty_item.setFlags(qty_item.flags() | Qt.ItemIsEditable)
                self.table.setItem(r, 1, qty_item)

                pu_item = QTableWidgetItem(fmt_money(it["unit_price"]))
                pu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                pu_item.setFlags(pu_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 2, pu_item)

                tot_item = QTableWidgetItem(fmt_money(it["line_total"]))
                tot_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                tot_item.setFlags(tot_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, 3, tot_item)

                # Columna 4: "botón" de eliminar como celda roja con X
                del_item = QTableWidgetItem("✕")
                del_item.setTextAlignment(Qt.AlignCenter)
                del_item.setFlags(del_item.flags() & ~Qt.ItemIsEditable)
                del_item.setBackground(QBrush(QColor("#d9534f")))
                del_item.setForeground(QBrush(QColor("white")))
                self.table.setItem(r, 4, del_item)
        finally:
            self._updating_table = False

        self.refresh_totals()
        self.in_search.setFocus()

    def clear_ticket_items(self):
        if not self.current_ticket_id:
            return
        for it in ts.list_items(self.current_ticket_id):
            ts.remove_item(it["id"])
        self.load_ticket(self.current_ticket_id)
        self.in_search.setFocus()

    # === Edición de cantidad en línea ===
    def on_table_item_changed(self, item: QTableWidgetItem):
        if self._updating_table or item.column() != 1:
            return
        row = item.row()
        prod_cell = self.table.item(row, 0)
        if not prod_cell:
            return
        line_id = prod_cell.data(Qt.UserRole)
        if line_id is None:
            return
        try:
            new_qty = int(item.text())
            if new_qty <= 0:
                raise ValueError
        except Exception:
            QMessageBox.warning(self, "Cantidad inválida", "Debe ser un número mayor que 0.")
            self.load_ticket(self.current_ticket_id)
            return
        ts.update_item_qty(line_id, new_qty)
        self.load_ticket(self.current_ticket_id)
        self.in_search.setFocus()

    def refresh_totals(self):
        if not self.current_ticket_id:
            self.lbl_totals.setText("Total: $0")
            return
        _, _, tot = ts.calc_ticket_totals(self.current_ticket_id)
        self.lbl_totals.setText(f"Total: {fmt_money(tot)}")

    def clear_ticket_ui(self):
        self.in_ticket_name.clear()
        self.table.setRowCount(0)
        self.lbl_totals.setText("Total: $0")

    # === Cobro ===
    def charge_ticket(self):
        if not self.current_ticket_id:
            return
        _, _, tot = ts.calc_ticket_totals(self.current_ticket_id)
        if tot <= 0:
            QMessageBox.warning(self, "Cobrar", "El ticket está vacío.")
            return
        dlg = ChargeDialog(total=tot, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        pay_method = dlg.selected_method or "efectivo"
        ts.rename_ticket(self.current_ticket_id, self.in_ticket_name.text().strip() or None)
        ts.set_pay_method(self.current_ticket_id, pay_method)
        try:
            sid = ss.cobrar_ticket(self.current_ticket_id)
            QMessageBox.information(
                self,
                "Venta",
                f"Venta registrada (ID {sid}) — Pago: {pay_method}."
            )
            self.reload_tickets()
            self.sale_completed.emit()   # avisamos al main para refrescar reportes
            self.in_search.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _warmup_common_product(self):
        """Crea/busca el Producto común al inicio para evitar la espera en el primer uso."""
        try:
            self._ensure_common_product_id()
        except Exception:
            pass

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
        self.load_ticket(self.current_ticket_id)
        self.in_search.setFocus()
        
    def eventFilter(self, obj, event):
        """Permite modificar cantidad con flechas ↑/↓ en la fila seleccionada."""
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
                # ↑ suma, ↓ resta
                if event.key() == Qt.Key_Up:
                    val += 1
                else:
                    val -= 1
                if val <= 0:
                    return True
                qty_item.setText(str(val))  # dispara on_table_item_changed
                return True
        return super().eventFilter(obj, event)

    def _on_table_cell_clicked(self, row: int, column: int):
        """Si se hace clic en la X, elimina; en otras columnas, edita cantidad."""
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
            self.in_search.setFocus()
            return

        # Cualquier otra columna: enfocamos la cantidad y abrimos editor
        qty_item = self.table.item(row, 1)
        if qty_item:
            self.table.setCurrentCell(row, 1)
            self.table.editItem(qty_item)


    def showEvent(self, event):
        """Cuando se muestra la pestaña POS, devuelve el foco a Buscar producto."""
        super().showEvent(event)
        # Un pequeño delay para que Qt termine de dibujar y luego ponemos el foco
        QTimer.singleShot(0, self.in_search.setFocus)
