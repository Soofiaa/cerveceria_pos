# main.py
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from core import db_manager
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView


# ==========================================================
# Paleta clara (única)
# ==========================================================
def _build_palette() -> QPalette:
    """
    Devuelve una paleta clara pensada para un POS de cervecería.

    Los colores están inspirados en tonos dorados y espumas claras para que
    toda la interfaz luzca moderna, fresca y claramente identificable con un
    negocio de cerveza artesanal.
    """

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#fbf7ef"))  # Fondo cálido general
    palette.setColor(QPalette.Base, QColor("#ffffff"))  # Fondos de inputs/tablas
    palette.setColor(QPalette.AlternateBase, QColor("#f4efe3"))
    palette.setColor(QPalette.WindowText, QColor("#1f2937"))
    palette.setColor(QPalette.Text, QColor("#111827"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#1f2937"))
    palette.setColor(QPalette.Highlight, QColor("#f2a72a"))  # Dorado principal
    palette.setColor(QPalette.HighlightedText, QColor("#111827"))
    palette.setColor(QPalette.Link, QColor("#c26a00"))
    palette.setColor(QPalette.BrightText, QColor("#ad6200"))
    return palette


# ==========================================================
# Stylesheet claro
# ==========================================================
def _build_stylesheet() -> str:
    """
    Construye un QSS inspirado en el branding de una cervecería.

    Se prioriza el uso de tonos claros, bordes redondeados y acentos dorados
    para que todas las pantallas (ventana principal y subventanas) se perciban
    modernas y coherentes.
    """

    return """
    /* ===================== BASE ===================== */
    QWidget {
        background-color: #fdfaf3;
        color: #1f2937;
        font-family: "Inter", "Segoe UI", Arial, sans-serif;
        font-size: 11pt;
    }

    /* ===================== TABS ===================== */
    QTabWidget::pane {
        border: 1px solid #eadfc8;
        border-radius: 14px;
        padding: 12px;
        background-color: #ffffff;
    }
    QTabBar::tab {
        background: #f4efe3;
        border: 1px solid #e4d9c5;
        border-radius: 999px;
        padding: 8px 18px;
        margin-right: 8px;
        color: #4b5563;
        font-weight: 600;
    }
    QTabBar::tab:selected {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f6c058, stop:1 #f2a72a);
        border: 1px solid #f2a72a;
        color: #0f172a;
        font-weight: 800;
    }

    /* ===================== SIDEBAR (Tickets abiertos) ===================== */
    QWidget#Sidebar {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fff4dd, stop:1 #ffe9b6);
        border: 1px solid #f2a72a;
        border-radius: 16px;
        padding: 12px;
    }

    QLabel#SidebarTitle {
        color: #8b5a1a;
        font-size: 18pt;
        font-weight: 900;
        letter-spacing: 0.5px;
    }

    QListWidget#TicketList {
        background-color: transparent;
        border: none;
        color: #3f3f46;
    }
    QListWidget#TicketList::item {
        padding: 10px 12px;
        border-radius: 10px;
        margin-bottom: 4px;
    }
    QListWidget#TicketList::item:selected {
        background-color: #f2a72a;
        color: #0f172a;
    }

    /* ===================== TITULOS Y TEXTOS ===================== */
    QLabel#SectionTitle {
        font-size: 18pt;
        font-weight: 900;
        color: #c26a00;
        letter-spacing: 0.4px;
    }
    QLabel#HintLabel {
        color: #6b7280;
    }
    QLabel#TotalsBadge {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff4dd, stop:1 #ffe7b0);
        border: 1px solid #f2a72a;
        padding: 20px 24px;
        border-radius: 16px;
        color: #8b5a1a;
        font-size: 22pt;
        font-weight: 900;
    }

    /* ===================== BOTONES ===================== */
    QPushButton {
        background-color: #f4efe3;
        border: 1px solid #dfd4bf;
        border-radius: 12px;
        padding: 9px 16px;
        font-weight: 700;
        color: #1f2937;
    }
    QPushButton:hover {
        background-color: #ebe2ce;
    }
    QPushButton:pressed {
        background-color: #dfd4bf;
    }

    QPushButton[buttonType="primary"] {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8c86b, stop:1 #f2a72a);
        border: 1px solid #f2a72a;
        color: #0f172a;
    }
    QPushButton[buttonType="primary"]:hover {
        background-color: #f6b84b;
    }

    QPushButton[buttonType="danger"] {
        background-color: #fff2f2;
        border: 1px solid #fbc2c2;
        color: #9b1c1c;
    }
    QPushButton[buttonType="danger"]:hover {
        background-color: #ffdede;
    }

    QPushButton[buttonType="ghost"] {
        background-color: #f9fafb;
        border: 1px dashed #cbd5e1;
        color: #374151;
    }
    QPushButton[buttonType="ghost"]:hover {
        background-color: #e5e7eb;
        border-style: solid;
    }
    
    /* Botones de filtro en PAGAR */
        QPushButton#PayMethodButton {
        border-radius: 999px;
        padding: 6px 14px;
    }
    QPushButton#PayMethodButton:checked {
        background-color: #fde68a;
        border: 1px solid #f59e0b;
        color: #92400e;
    }

    /* Botones de filtro en Reportes (Hoy, Semana, Mes, Año) */
    QPushButton#ReportFilter {
        background-color: #fff7e6;
        border-radius: 999px;
        border: 1px solid #fcd34d;
        color: #92400e;
        padding: 6px 14px;
        font-weight: 600;
    }
    QPushButton#ReportFilter:hover {
        background-color: #fde68a;
    }
    
    
    /* ===================== INPUTS ===================== */
    QLineEdit, QComboBox, QSpinBox {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 10px;
        padding: 6px 10px;
        selection-background-color: #f4a506;
        selection-color: #111827;
    }

    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
        border: 1px solid #f2a72a;
    }

    
        /* ===================== QDateEdit (Desde / Hasta) ===================== */
    QDateEdit {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 10px;
        padding: 4px 8px;
        /* no tocar el icono aquí */
        selection-background-color: #f4a506;
        selection-color: #111827;
    }

    QDateEdit:focus {
        border: 1px solid #f2a72a;
    }

    /* Solo reubicamos el área del botón, SIN cambiar el icono nativo */
    QDateEdit::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 18px;
        border: none;
        background: transparent;   /* sin barra de color */
        margin-right: 2px;
    }



    /* ===================== TABLAS ===================== */
    QTableView, QTableWidget {
        background-color: #ffffff;
        alternate-background-color: #fbf2de;
        border: 1px solid #eadfc8;
        border-radius: 12px;
        gridline-color: #eadfc8;
        selection-background-color: #f2a72a;
        selection-color: #0f172a;
    }

    QHeaderView::section {
        background: #f4efe3;
        color: #4b5563;
        padding: 8px;
        border: none;
        font-weight: 800;
    }

    /* ===================== GROUPBOX ===================== */
    QGroupBox {
        border: 1px solid #e4d9c5;
        border-radius: 12px;
        margin-top: 18px;
        background-color: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 16px;
        padding: 0 6px;
        color: #c26a00;
        font-weight: 800;
        background-color: #fdfaf3;  /* mismo fondo general para que se "corte" el borde */
    }
    

    /* ===================== DIALOGOS ===================== */
    QDialog {
        background-color: #ffffff;
        border: 1px solid #eadfc8;
        border-radius: 14px;
    }
    QDialog QLabel#DialogTitle {
        font-size: 16pt;
        font-weight: 800;
        color: #1f2937;
    }

    QMessageBox {
        background-color: #ffffff;
        border-radius: 14px;
    }
    QMessageBox QLabel {
        color: #1f2937;
    }
    QMessageBox QPushButton {
        min-width: 94px;
        padding: 7px 12px;
    }
    """


# ==========================================================
# Ventana principal
# ==========================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cervecería POS")
        self.resize(1100, 720)

        tabs = QTabWidget()
        tabs.addTab(POSView(), "POS")
        tabs.addTab(ProductsView(), "Productos")
        tabs.addTab(ReportsView(), "Reportes")

        self.setCentralWidget(tabs)


# ==========================================================
# Main
# ==========================================================
def main() -> None:
    db_manager.bootstrap()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont("Inter", 11)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    app.setPalette(_build_palette())
    app.setStyleSheet(_build_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
