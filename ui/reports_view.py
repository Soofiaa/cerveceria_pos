# ui/reports_view.py
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateEdit,
    QTableWidget, QHeaderView, QGroupBox, QGridLayout
)

from ui.reports import ReportActionsMixin


class ReportsView(QWidget, ReportActionsMixin):
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Reportes")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        hint = QLabel(
            'En caso de querer buscar entre una fecha específica, elegir intervalo y hacer clic en "Buscar".'
        )
        hint.setStyleSheet("color: #888888; font-size: 12pt;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.in_from = QDateEdit(QDate.currentDate())
        self.in_from.setCalendarPopup(True)
        self.in_to = QDateEdit(QDate.currentDate())
        self.in_to.setCalendarPopup(True)

        self.btn_today = QPushButton("Hoy")
        self.btn_week = QPushButton("Semana actual")
        self.btn_month = QPushButton("Mes actual")
        self.btn_year = QPushButton("Año actual")
        self.btn_run = QPushButton("Buscar")
        self.btn_export = QPushButton("Exportar CSV")

        self.btn_today.clicked.connect(self._set_today)
        self.btn_week.clicked.connect(self._set_week_current)
        self.btn_month.clicked.connect(self._set_month_current)
        self.btn_year.clicked.connect(self._set_year_current)
        self.btn_run.clicked.connect(self.load_data)
        self.btn_export.clicked.connect(self.export_csv)

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

        box = QGroupBox("Resumen")
        grid = QGridLayout()

        self.lbl_total = QLabel("$0")
        self.lbl_profit = QLabel("$0")
        self.lbl_count = QLabel("0")
        self.lbl_avg = QLabel("$0")
        self.lbl_avg_margin = QLabel("0,0 %")

        for lbl in [self.lbl_total, self.lbl_profit, self.lbl_count, self.lbl_avg, self.lbl_avg_margin]:
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        grid.addWidget(QLabel("Total vendido:"), 0, 0); grid.addWidget(self.lbl_total, 0, 1)
        grid.addWidget(QLabel("Ganancia total:"), 1, 0); grid.addWidget(self.lbl_profit, 1, 1)
        grid.addWidget(QLabel("N° ventas:"), 2, 0); grid.addWidget(self.lbl_count, 2, 1)
        grid.addWidget(QLabel("Venta promedio:"), 3, 0); grid.addWidget(self.lbl_avg, 3, 1)
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

        self.tbl_top = QTableWidget(0, 3)
        self.tbl_top.setAlternatingRowColors(True)
        self.tbl_top.setHorizontalHeaderLabels(["Producto", "Cant.", "Ingreso"])

        header = self.tbl_top.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)

        self.tbl_top.setEditTriggers(self.tbl_top.NoEditTriggers)
        self.tbl_top.verticalHeader().setDefaultSectionSize(32)

        layout.addLayout(top)
        layout.addWidget(box)
        layout.addWidget(QLabel("Top productos"))
        layout.addWidget(self.tbl_top)

        self._tune_sizes()
        self._set_today()

    def _tune_sizes(self):
        """Ajusta alturas de controles para ser más amigables."""
        self.in_from.setMinimumHeight(30)
        self.in_to.setMinimumHeight(30)

        for btn in [
            self.btn_today, self.btn_week, self.btn_month,
            self.btn_year, self.btn_run, self.btn_export
        ]:
            btn.setMinimumHeight(34)
