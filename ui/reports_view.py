# ui/reports_view.py
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateEdit,
    QTableWidget, QHeaderView, QGroupBox, QGridLayout,
    QAbstractItemView, QToolButton, QCalendarWidget
)

from ui.reports.actions import ReportActionsMixin


class MonthOnlyCalendar(QCalendarWidget):
    """
    Calendario que SOLO dibuja los días del mes actualmente mostrado.
    Los días de meses anterior/siguiente quedan como celdas vacías.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        # Altura fija razonable (ajústala si quieres)
        self.setFixedHeight(280)

    def paintCell(self, painter, rect, date):
        current_year = self.yearShown()
        current_month = self.monthShown()

        # Solo dibujamos si pertenece al mes actual
        if date.year() == current_year and date.month() == current_month:
            super().paintCell(painter, rect, date)
        else:
            # No dibujar nada en celdas de otros meses
            return


class ModernDateEdit(QDateEdit):
    """
    QDateEdit con flecha moderna dibujada con QToolButton interno
    y un calendario popup propio.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # Estilo del campo
        self.setStyleSheet(
            """
            QDateEdit {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 4px 8px;
                padding-right: 22px;  /* espacio para la flecha moderna */
                selection-background-color: #f4a506;
                selection-color: #111827;
            }
            QDateEdit:focus {
                border: 1px solid #f2a72a;
            }

            /* Ocultar drop-down nativo (flecha vieja) */
            QDateEdit::drop-down {
                width: 0px;
                border: 0px;
            }

            /* OCULTAR LOS BOTONES DE SUBIR Y BAJAR FECHA */
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
            """
        )

        # Calendario popup propio
        self._calendar = MonthOnlyCalendar(self)
        self._calendar.setWindowFlags(Qt.Popup)
        self._calendar.clicked.connect(self._on_calendar_clicked)
        self._calendar.hide()


        # Botón interno con flecha moderna
        self._btn = QToolButton(self)
        self._btn.setText("▼")
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet(
            """
            QToolButton {
                border: none;
                padding: 0px;
                font-weight: 900;
                color: #6b7280;
            }
            QToolButton:hover {
                color: #374151;
            }
            """
        )
        self._btn.clicked.connect(self.showCalendarPopup)

    def resizeEvent(self, event):
        """Reubicar la flecha siempre pegada a la derecha."""
        super().resizeEvent(event)
        sz = self._btn.sizeHint()
        x = self.rect().right() - sz.width() - 4
        y = (self.rect().height() - sz.height()) // 2
        self._btn.setGeometry(x, y, sz.width(), sz.height())

    def showCalendarPopup(self):
        """Muestra el calendario como popup justo debajo del control."""
        # Sincronizar fecha seleccionada
        self._calendar.setSelectedDate(self.date())
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._calendar.move(pos)
        self._calendar.show()
        self._calendar.raise_()
        self._calendar.setFocus()

    def _on_calendar_clicked(self, date: QDate):
        """Cuando el usuario elige una fecha en el calendario."""
        self.setDate(date)
        self._calendar.hide()


class ReportsView(QWidget, ReportActionsMixin):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("Reportes")
        title.setObjectName("SectionTitle")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        hint = QLabel(
            'En caso de querer buscar entre una fecha específica, elegir intervalo y hacer clic en "Buscar".'
        )
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # DateEdits con flecha moderna
        self.in_from = ModernDateEdit()
        self.in_from.setDate(QDate.currentDate())

        self.in_to = ModernDateEdit()
        self.in_to.setDate(QDate.currentDate())

        # Formato y tamaño suficientes para ver dd-MM-yyyy completo
        for d in (self.in_from, self.in_to):
            d.setDisplayFormat("dd-MM-yyyy")
            d.setMinimumWidth(115)
            d.setMinimumHeight(30)

        self.btn_today = QPushButton("Hoy")
        self.btn_today.setProperty("buttonType", "ghost")
        self.btn_today.setObjectName("ReportFilter")

        self.btn_week = QPushButton("Semana actual")
        self.btn_week.setProperty("buttonType", "ghost")
        self.btn_week.setObjectName("ReportFilter")

        self.btn_month = QPushButton("Mes actual")
        self.btn_month.setProperty("buttonType", "ghost")
        self.btn_month.setObjectName("ReportFilter")

        self.btn_year = QPushButton("Año actual")
        self.btn_year.setProperty("buttonType", "ghost")
        self.btn_year.setObjectName("ReportFilter")

        self.btn_run = QPushButton("Buscar")
        self.btn_run.setProperty("buttonType", "primary")

        self.btn_export = QPushButton("Exportar CSV")
        self.btn_export.setProperty("buttonType", "primary")

        self.btn_today.clicked.connect(self._set_today)
        self.btn_week.clicked.connect(self._set_week_current)
        self.btn_month.clicked.connect(self._set_month_current)
        self.btn_year.clicked.connect(self._set_year_current)
        self.btn_run.clicked.connect(self.load_data)
        self.btn_export.clicked.connect(self.export_csv)

        # Fila superior con filtros
        top = QHBoxLayout()
        top.addWidget(QLabel("Desde:"))
        top.addWidget(self.in_from)
        top.addSpacing(8)
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

        # Resumen
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

        # Tabla top productos
        self.tbl_top = QTableWidget(0, 3)
        self.tbl_top.setAlternatingRowColors(True)
        self.tbl_top.setHorizontalHeaderLabels(["Producto", "Cant.", "Ingreso"])

        header = self.tbl_top.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)

        self.tbl_top.setEditTriggers(QAbstractItemView.NoEditTriggers)
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


    def showEvent(self, event):
        super().showEvent(event)
        # Cada vez que se entra a la pestaña Reportes, refrescamos datos
        self._set_today()
