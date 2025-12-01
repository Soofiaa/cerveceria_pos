# ui/daily_sales_dialog.py

from datetime import date
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QHeaderView, QDateEdit
)

from core.utils_format import fmt_money
from core import sales_service as ss
from ui.reports_view import ModernDateEdit


class DailySalesDialog(QDialog):
    """
    Muestra las ventas de un día (por defecto hoy) usando sales_service.ventas_del_dia().

    Columnas:
      - Fecha y hora (created_at)
      - ID Venta
      - Total
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ventas por día")
        self.resize(700, 500)

        main_layout = QVBoxLayout(self)

        # --- Filtro por fecha ---
        filter_layout = QHBoxLayout()
        lbl_fecha = QLabel("Fecha:")
        self.date_edit = ModernDateEdit(self)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMinimumWidth(130)
        self.date_edit.setMinimumHeight(30)

        # --- Estilo para que el botón del calendario sea visible ---
        self.date_edit.setStyleSheet("""
            QDateEdit {
                border: 1px solid #888;
                border-radius: 6px;
                padding: 4px 6px;
                background: white;
                min-width: 130px;
            }

            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: right;
                width: 28px;
                border-left: 1px solid #888;
                background: #e6e6e6;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }

            QDateEdit::down-arrow {
                width: 14px;
                height: 14px;
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAMCAYAAABbayygAAAAAXNSR0IArs4c6QAAAH5JREFUKFNjZGBg+M9ABGBiIAT/BwYGBmYmJiY/ExMT8/8zMDDwPwPDhw9fQJGBgeH8/fv3PwPDv38/DFhYWNjFxcUwMDAQmJiY+D8jwH+YGBgYGLgTxkZmZgZmBgYGAWLjx8+PBxAwPDLwMDww8DA8PxGDAwMDDwH6GgYHh7++fPnwMDAwMDA0NDA8MDAL3FBgY8M1jYAAAAASUVORK5CYII=);
            }
            
            /* Ocultar los botones de subir/bajar fecha */
            QDateEdit::up-button {
                width: 0px;
                height: 0px;
                border: none;
            }
            
            QDateEdit::down-button {
                width: 0px;
                height: 0px;
                border: none;
            }
        """)

        # Botón actualizar
        self.btn_refresh = QPushButton("Buscar")
        self.btn_refresh.clicked.connect(self.reload_sales)

        self.date_edit.dateChanged.connect(self.reload_sales)

        filter_layout.addWidget(lbl_fecha)
        filter_layout.addWidget(self.date_edit)
        filter_layout.addStretch()
        filter_layout.addWidget(self.btn_refresh)

        main_layout.addLayout(filter_layout)

        # --- Tabla de ventas ---
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(
            ["Fecha y hora", "ID Venta", "Total"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table)

        # --- Resumen ---
        self.lbl_total_dia = QLabel("Total del día: $0")
        self.lbl_cantidad = QLabel("Cantidad de ventas: 0")

        for lbl in (self.lbl_total_dia, self.lbl_cantidad):
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        resumen_box = QVBoxLayout()
        resumen_box.addWidget(self.lbl_total_dia)
        resumen_box.addWidget(self.lbl_cantidad)

        main_layout.addLayout(resumen_box)

        # --- Botón cerrar ---
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)

        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(btn_cerrar)
        main_layout.addLayout(bottom)

        # Cargar datos iniciales
        self.reload_sales()

    # ------------------------------------------------------------------ #
    # Lógica de carga de ventas
    # ------------------------------------------------------------------ #

    def reload_sales(self):
        qdate = self.date_edit.date()
        fecha_iso = qdate.toString("yyyy-MM-dd")

        ventas = ss.ventas_del_dia(fecha_iso)

        self.table.setRowCount(0)

        total_dia = 0
        count = 0

        for v in ventas:
            r = self.table.rowCount()
            self.table.insertRow(r)

            created_at = v.get("created_at") or ""
            fecha_hora = created_at

            self.table.setItem(r, 0, QTableWidgetItem(fecha_hora))
            self.table.setItem(r, 1, QTableWidgetItem(str(v["id"])))
            self.table.setItem(r, 2, QTableWidgetItem(fmt_money(v["total"])))

            total_dia += int(v["total"] or 0)
            count += 1

        # Resumen
        self.lbl_total_dia.setText(f"Total del día: {fmt_money(total_dia)}")
        self.lbl_cantidad.setText(f"Cantidad de ventas: {count}")
