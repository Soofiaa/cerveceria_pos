# ui/reports_view.py
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout
)
from core.report_service import (
    summary, top_products
)
from core.utils_format import fmt_money
from datetime import datetime
import csv


def _fmt_pct(value) -> str:
    """
    Formatea un porcentaje como '25,0 %'.
    Supone que value viene como fracción (0.25 -> 25 %).
    Si viene como número grande (ej: 25), lo deja tal cual.
    """
    try:
        v = float(value)
    except Exception:
        return "-"

    if 0 <= v <= 1:
        v = v * 100.0
    return f"{v:,.1f} %".replace(",", ".")


class ReportsView(QWidget):
    def __init__(self):
        super().__init__()

        # Estilo local: fuente un poco más grande
        self.setStyleSheet("""
        QWidget {
            font-size: 11pt;
        }
        QLineEdit, QDateEdit, QPushButton {
            font-size: 11pt;
        }
        QHeaderView::section {
            font-size: 10pt;
        }
        """)

        # --- Layout principal (lo creamos AL INICIO) ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Título grande arriba
        title = QLabel("Reportes")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # --- Hint / instrucción clara (debajo del título) ---
        hint = QLabel(
            'En caso de querer buscar entre una fecha específica, elegir intervalo y hacer clic en "Buscar".'
        )
        hint.setStyleSheet("color: #888888; font-size: 12pt;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # --- Filtros de fechas ---
        self.in_from = QDateEdit(QDate.currentDate())
        self.in_from.setCalendarPopup(True)
        self.in_to = QDateEdit(QDate.currentDate())
        self.in_to.setCalendarPopup(True)

        self.btn_today  = QPushButton("Hoy")
        self.btn_week   = QPushButton("Semana actual")
        self.btn_month  = QPushButton("Mes actual")
        self.btn_year   = QPushButton("Año actual")
        self.btn_run    = QPushButton("Buscar")
        self.btn_export = QPushButton("Exportar CSV")

        self.btn_today.clicked.connect(self._set_today)
        self.btn_week.clicked.connect(self._set_week_current)
        self.btn_month.clicked.connect(self._set_month_current)
        self.btn_year.clicked.connect(self._set_year_current)
        self.btn_run.clicked.connect(self.load_data)
        self.btn_export.clicked.connect(self.export_csv)

        # --- Layout superior (filtros + botones) ---
        top = QHBoxLayout()
        top.addWidget(QLabel("Desde:"))
        top.addWidget(self.in_from)
        top.addWidget(QLabel("Hasta:"))
        top.addWidget(self.in_to)
        top.addWidget(self.btn_run)
        top.addStretch()
        top.addWidget(self.btn_today)
        top.addWidget(self.btn_week)
        top.addWidget(self.btn_month)
        top.addWidget(self.btn_year)
        top.addSpacing(20)
        top.addWidget(self.btn_export)

        # --- KPIs / Resumen ---
        box = QGroupBox("Resumen")
        grid = QGridLayout()

        self.lbl_total      = QLabel("$0");    self.lbl_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_profit     = QLabel("$0");    self.lbl_profit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_count      = QLabel("0");     self.lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_avg        = QLabel("$0");    self.lbl_avg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_avg_margin = QLabel("0,0 %"); self.lbl_avg_margin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        grid.addWidget(QLabel("Total vendido:"),            0, 0); grid.addWidget(self.lbl_total,      0, 1)
        grid.addWidget(QLabel("Ganancia total:"),           1, 0); grid.addWidget(self.lbl_profit,     1, 1)
        grid.addWidget(QLabel("N° ventas:"),                2, 0); grid.addWidget(self.lbl_count,      2, 1)
        grid.addWidget(QLabel("Venta promedio:"),           3, 0); grid.addWidget(self.lbl_avg,        3, 1)
        grid.addWidget(QLabel("Margen utilidad promedio:"), 4, 0); grid.addWidget(self.lbl_avg_margin, 4, 1)

        grid.setContentsMargins(10, 8, 10, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        box.setLayout(grid)
        box.setStyleSheet("""
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)

        # --- Tabla Top productos ---
        self.tbl_top = QTableWidget(0, 3)
        self.tbl_top.setAlternatingRowColors(True)
        self.tbl_top.setHorizontalHeaderLabels(["Producto", "Cant.", "Ingreso"])

        header = self.tbl_top.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)

        self.tbl_top.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_top.verticalHeader().setDefaultSectionSize(32)

        # --- Agregar todo al layout principal ---
        layout.addLayout(top)
        layout.addWidget(box)
        layout.addWidget(QLabel("Top productos"))
        layout.addWidget(self.tbl_top)

        # Ajustes de tamaño más cómodos
        self._tune_sizes()

        # Carga inicial
        self._set_today()


    def _tune_sizes(self):
        """Ajusta alturas de controles para ser más amigables."""
        # DateEdits y botones superiores
        self.in_from.setMinimumHeight(30)
        self.in_to.setMinimumHeight(30)

        for btn in [
            self.btn_today, self.btn_week, self.btn_month,
            self.btn_year, self.btn_run, self.btn_export
        ]:
            btn.setMinimumHeight(34)

    # --- Rangos rápidos ---
    def _set_today(self):
        today = QDate.currentDate()
        self.in_from.setDate(today)
        self.in_to.setDate(today)
        self.load_data()

    def _set_week_current(self):
        """Semana actual: desde lunes hasta hoy."""
        to = QDate.currentDate()
        dow = to.dayOfWeek()  # 1=lunes ... 7=domingo
        fr = to.addDays(-(dow - 1))
        self.in_from.setDate(fr)
        self.in_to.setDate(to)
        self.load_data()

    def _set_month_current(self):
        to = QDate.currentDate()
        fr = QDate(to.year(), to.month(), 1)
        self.in_from.setDate(fr)
        self.in_to.setDate(to)
        self.load_data()

    def _set_year_current(self):
        """Año actual: desde 1 de enero hasta hoy."""
        today = QDate.currentDate()
        fr = QDate(today.year(), 1, 1)
        to = today
        self.in_from.setDate(fr)
        self.in_to.setDate(to)
        self.load_data()

    # --- Carga de datos ---
    def load_data(self):
        d1, d2 = self.in_from.date(), self.in_to.date()
        s = summary(d1, d2)

        # Se asume que summary retorna:
        #   s["total"], s["tickets"], s["avg_ticket"],
        #   s.get("profit", 0), s.get("avg_margin", 0.0)
        total   = s.get("total", 0)
        tickets = s.get("tickets", 0)
        avg     = s.get("avg_ticket", 0)
        profit  = s.get("profit", 0)
        avg_mgn = s.get("avg_margin", 0.0)

        self.lbl_total.setText(fmt_money(total))
        self.lbl_profit.setText(fmt_money(profit))
        self.lbl_count.setText(str(tickets))
        self.lbl_avg.setText(fmt_money(avg))
        self.lbl_avg_margin.setText(_fmt_pct(avg_mgn))

        # Top productos
        tops = top_products(d1, d2, limit=10)
        self.tbl_top.setRowCount(0)
        for tp in tops:
            i = self.tbl_top.rowCount()
            self.tbl_top.insertRow(i)

            name_item = QTableWidgetItem(tp["name"])
            qty_item = QTableWidgetItem(str(tp["qty"]))
            rv = QTableWidgetItem(fmt_money(tp["revenue"]))

            qty_item.setTextAlignment(Qt.AlignCenter)
            rv.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            self.tbl_top.setItem(i, 0, name_item)
            self.tbl_top.setItem(i, 1, qty_item)
            self.tbl_top.setItem(i, 2, rv)

    # --- Exportar CSV (solo resumen) ---
    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar CSV",
            "resumen_ventas.csv",
            "CSV (*.csv)"
        )
        if not path:
            return

        try:
            d1, d2 = self.in_from.date(), self.in_to.date()
            s = summary(d1, d2)

            total   = s.get("total", 0)
            tickets = s.get("tickets", 0)
            avg     = s.get("avg_ticket", 0)
            profit  = s.get("profit", 0)
            avg_mgn = s.get("avg_margin", 0.0)

            # Fechas en formato amigable
            desde_str = d1.toString("dd-MM-yyyy")
            hasta_str = d2.toString("dd-MM-yyyy")

            with open(path, "w", newline="", encoding="latin-1") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Métrica", "Valor"])
                w.writerow(["Desde", desde_str])
                w.writerow(["Hasta", hasta_str])
                w.writerow(["Total vendido", fmt_money(total)])
                w.writerow(["Ganancia total", fmt_money(profit)])
                w.writerow(["Número de ventas", tickets])
                w.writerow(["Venta promedio", fmt_money(avg)])
                w.writerow(["Margen de utilidad promedio", _fmt_pct(avg_mgn)])

            QMessageBox.information(self, "Exportar", "CSV de resumen exportado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Exportar", f"No se pudo exportar:\n{e}")
