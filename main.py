# main.py
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from core import db_manager, config
from ui.theme import get_theme
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView


# ==========================================================
# Paleta clara
# ==========================================================
def _build_palette(theme_name: str) -> QPalette:
    """Devuelve una paleta según el tema seleccionado."""
    theme = get_theme(theme_name)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(theme["background"]))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor(theme["background"]))
    palette.setColor(QPalette.WindowText, QColor(theme["text"]))
    palette.setColor(QPalette.Text, QColor(theme["text"]))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor(theme["text"]))
    palette.setColor(QPalette.Highlight, QColor(theme["primary"]))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Link, QColor(theme["secondary"]))
    palette.setColor(QPalette.BrightText, QColor(theme["accent"]))
    return palette


# ==========================================================
# Stylesheet claro
# ==========================================================
def _build_stylesheet(theme_name: str) -> str:
    """Construye un QSS según el tema seleccionado."""
    theme = get_theme(theme_name)
    return f"""
    /* ===================== BASE ===================== */
    QWidget {{
        background-color: {theme["background"]};
        color: {theme["text"]};
        font-family: "Inter", "Segoe UI", Arial, sans-serif;
        font-size: 11pt;
    }}

    /* ===================== TABS ===================== */
    QTabWidget::pane {{
        border: 1px solid {theme["secondary"]};
        border-radius: 14px;
        padding: 12px;
        background-color: #ffffff;
    }}
    QTabBar::tab {{
        background: {theme["background"]};
        border: 1px solid {theme["secondary"]};
        border-radius: 999px;
        padding: 8px 18px;
        margin-right: 8px;
        color: {theme["text"]};
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {theme["primary"]};
        border: 1px solid {theme["primary"]};
        color: white;
        font-weight: 800;
    }}

    /* ===================== SIDEBAR (Tickets abiertos) ===================== */
    QWidget#Sidebar {{
        background: {theme["background"]};
        border: 1px solid {theme["primary"]};
        border-radius: 16px;
        padding: 12px;
    }}

    QLabel#SidebarTitle {{
        color: {theme["secondary"]};
        font-size: 18pt;
        font-weight: 900;
        letter-spacing: 0.5px;
    }}

    QListWidget#TicketList {{
        background-color: transparent;
        border: none;
        color: {theme["text"]};
    }}
    QListWidget#TicketList::item {{
        padding: 10px 12px;
        border-radius: 10px;
        margin-bottom: 4px;
    }}
    QListWidget#TicketList::item:selected {{
        background-color: {theme["primary"]};
        color: white;
    }}

    /* ===================== TITULOS Y TEXTOS ===================== */
    QLabel#SectionTitle {{
        font-size: 18pt;
        font-weight: 900;
        color: {theme["secondary"]};
        letter-spacing: 0.4px;
    }}
    QLabel#HintLabel {{
        color: {theme["text"]};
    }}
    QLabel#TotalsBadge {{
        background: {theme["background"]};
        border: 1px solid {theme["primary"]};
        padding: 20px 24px;
        border-radius: 16px;
        color: {theme["secondary"]};
        font-size: 22pt;
        font-weight: 900;
    }}

    /* ===================== BOTONES ===================== */
    QPushButton {{
        background-color: {theme["background"]};
        border: 1px solid {theme["secondary"]};
        border-radius: 12px;
        padding: 9px 16px;
        font-weight: 700;
        color: {theme["text"]};
    }}
    QPushButton:hover {{
        background-color: {theme["primary"]};
        color: white;
    }}
    """

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
        border: 1px solid {theme["secondary"]};
        border-radius: 12px;
        margin-top: 18px;
        background-color: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 16px;
        padding: 0 6px;
        color: {theme["secondary"]};
        font-weight: 800;
        background-color: {theme["background"]};
    }
    
    /* ===================== DIALOGOS ===================== */
    QDialog {
        background-color: #ffffff;
        border: 1px solid {theme["secondary"]};
        border-radius: 14px;
    }
    QDialog QLabel#DialogTitle {
        font-size: 16pt;
        font-weight: 800;
        color: {theme["text"]};
    }

    QMessageBox {
        background-color: #ffffff;
        border-radius: 14px;
    }
    QMessageBox QLabel {
        color: {theme["text"]};
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
        conf = config.load_config()
        self.setWindowTitle(conf["business_name"])
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
    conf = config.load_config()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont("Inter", 11)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    theme = conf.get("theme", "neutro")
    app.setPalette(_build_palette(theme))
    app.setStyleSheet(_build_stylesheet(theme))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
