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
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f8fafc"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f1f5f9"))
    palette.setColor(QPalette.WindowText, QColor("#0f172a"))
    palette.setColor(QPalette.Text, QColor("#0f172a"))
    palette.setColor(QPalette.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ButtonText, QColor("#0f172a"))
    palette.setColor(QPalette.Highlight, QColor("#f4a506"))
    palette.setColor(QPalette.HighlightedText, QColor("#0f172a"))
    palette.setColor(QPalette.Link, QColor("#c26a00"))
    palette.setColor(QPalette.BrightText, QColor("#e38b00"))
    return palette


# ==========================================================
# Stylesheet claro
# ==========================================================
def _build_stylesheet() -> str:
    return """
    /* ===================== BASE ===================== */
    QWidget {
        background-color: #f3f4f6;
        color: #111827;
        font-family: "Inter", "Segoe UI", Arial, sans-serif;
        font-size: 11pt;
    }

    /* ===================== TABS ===================== */
    QTabWidget::pane {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 10px;
        background-color: #ffffff;
    }
    QTabBar::tab {
        background: #e5e7eb;
        border: 1px solid #d1d5db;
        border-radius: 999px;
        padding: 6px 18px;
        margin-right: 6px;
        color: #4b5563;
    }
    QTabBar::tab:selected {
        background: #f4a506;
        border: 1px solid #f4a506;
        color: #0f172a;
        font-weight: 700;
    }

    /* ===================== SIDEBAR (Tickets abiertos) ===================== */
    QWidget#Sidebar {
        background-color: #111827;
        border-radius: 14px;
        padding: 10px;
    }

    QLabel#SidebarTitle {
        color: #f9fafb;
        font-size: 18pt;
        font-weight: 800;
    }

    QListWidget#TicketList {
        background-color: #111827;
        border: none;
        color: #e5e7eb;
    }
    QListWidget#TicketList::item {
        padding: 8px 10px;
        border-radius: 8px;
    }
    QListWidget#TicketList::item:selected {
        background-color: #f4a506;
        color: #111827;
    }

    /* ===================== TITULOS Y TEXTOS ===================== */
    QLabel#SectionTitle {
        font-size: 18pt;
        font-weight: 800;
        color: #c26a00;
    }
    QLabel#HintLabel {
        color: #6b7280;
    }
    QLabel#TotalsBadge {
        background-color: #fff7e6;
        border: 1px solid #f4a506;
        padding: 18px 22px;
        border-radius: 14px;
        color: #c26a00;
        font-size: 22pt;
        font-weight: 800;
    }

    /* ===================== BOTONES ===================== */
    QPushButton {
        background-color: #e5e7eb;
        border: 1px solid #d1d5db;
        border-radius: 10px;
        padding: 8px 14px;
        font-weight: 600;
        color: #111827;
    }
    QPushButton:hover {
        background-color: #d4d4d8;
    }
    QPushButton:pressed {
        background-color: #cbd5e1;
    }

    QPushButton[buttonType="primary"] {
        background-color: #f4a506;
        border: 1px solid #f4a506;
        color: #0f172a;
    }
    QPushButton[buttonType="primary"]:hover {
        background-color: #f7b733;
    }

    QPushButton[buttonType="danger"] {
        background-color: #fee2e2;
        border: 1px solid #fca5a5;
        color: #991b1b;
    }
    QPushButton[buttonType="danger"]:hover {
        background-color: #fecaca;
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

    /* ===================== INPUTS ===================== */
    QLineEdit, QComboBox, QSpinBox, QDateEdit {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 10px;
        padding: 6px 10px;
        selection-background-color: #f4a506;
        selection-color: #111827;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
        border: 1px solid #f4a506;
    }

    /* ===================== TABLAS ===================== */
    QTableView, QTableWidget {
        background-color: #ffffff;
        alternate-background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        gridline-color: #e5e7eb;
        selection-background-color: #f4a506;
        selection-color: #0f172a;
    }

    QHeaderView::section {
        background-color: #e5edf5;
        color: #374151;
        padding: 6px;
        border: none;
        font-weight: 700;
    }

    /* ===================== GROUPBOX ===================== */
    QGroupBox {
        border: 1px solid #d1d5db;
        border-radius: 10px;
        margin-top: 12px;
        background-color: #ffffff;
    }
    QGroupBox::title {
        left: 10px;
        color: #c26a00;
        font-weight: 700;
    }

    /* ===================== DIALOGOS ===================== */
    QDialog {
        background-color: #ffffff;
        border: 1px solid #d1d5db;
        border-radius: 12px;
    }
    QDialog QLabel#DialogTitle {
        font-size: 16pt;
        font-weight: 700;
        color: #111827;
    }

    QMessageBox {
        background-color: #ffffff;
        border-radius: 12px;
    }
    QMessageBox QLabel {
        color: #111827;
    }
    QMessageBox QPushButton {
        min-width: 88px;
        padding: 6px 12px;
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
