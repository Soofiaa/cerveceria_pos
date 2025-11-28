# main.py
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from core import db_manager
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView


def _build_palette() -> QPalette:
    """Define una paleta oscura con acentos dorados inspirados en cervecería."""

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0c1118"))
    palette.setColor(QPalette.Base, QColor("#0f172a"))
    palette.setColor(QPalette.AlternateBase, QColor("#0c1118"))
    palette.setColor(QPalette.WindowText, QColor("#e8edf2"))
    palette.setColor(QPalette.Text, QColor("#e8edf2"))
    palette.setColor(QPalette.Button, QColor("#0f172a"))
    palette.setColor(QPalette.ButtonText, QColor("#f8fafc"))
    palette.setColor(QPalette.Highlight, QColor("#f59e0b"))
    palette.setColor(QPalette.HighlightedText, QColor("#0c0f14"))
    palette.setColor(QPalette.Link, QColor("#fbbf24"))
    palette.setColor(QPalette.BrightText, QColor("#fbbf24"))
    return palette


def _build_stylesheet() -> str:
    """Estilos globales minimalistas y modernos."""

    return """
    QWidget {
        background-color: #0c1118;
        color: #e8edf2;
        font-family: "Inter", "Segoe UI", "Arial", sans-serif;
        font-size: 11pt;
    }

    QTabWidget::pane {
        border: 1px solid #1f2937;
        border-radius: 12px;
        padding: 12px;
        background-color: #0f172a;
    }
    QTabBar::tab {
        background: #0f172a;
        border: 1px solid #1f2937;
        border-radius: 10px;
        padding: 10px 16px;
        margin-right: 6px;
        color: #cbd5e1;
    }
    QTabBar::tab:selected {
        background: #f59e0b;
        color: #0c0f14;
        border-color: #f59e0b;
        font-weight: 700;
    }

    QPushButton {
        background-color: #111827;
        border: 1px solid #1f2937;
        color: #e8edf2;
        border-radius: 10px;
        padding: 8px 14px;
        font-weight: 600;
    }
    QPushButton:hover {
        border-color: #f59e0b;
        color: #f8fafc;
    }
    QPushButton:pressed {
        background-color: #0b1220;
    }
    QPushButton[buttonType="primary"] {
        background-color: #f59e0b;
        border: 1px solid #f59e0b;
        color: #0c0f14;
    }
    QPushButton[buttonType="primary"]:hover {
        background-color: #fbbf24;
        border-color: #fbbf24;
    }
    QPushButton[buttonType="danger"] {
        background-color: #b91c1c;
        border: 1px solid #b91c1c;
        color: #fef2f2;
    }
    QPushButton[buttonType="ghost"] {
        background-color: transparent;
        color: #cbd5e1;
        border: 1px dashed #1f2937;
    }

    QLineEdit, QComboBox, QSpinBox, QDateEdit {
        background-color: #101827;
        border: 1px solid #1f2733;
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: #f59e0b;
        selection-color: #0c0f14;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
        border: 1px solid #f59e0b;
    }

    QListWidget {
        background-color: #0f172a;
        border: 1px solid #1f2937;
        border-radius: 10px;
    }
    QListWidget::item {
        padding: 8px;
    }
    QListWidget::item:selected {
        background-color: #f59e0b;
        color: #0c0f14;
        border-radius: 6px;
    }

    QTableView, QTableWidget {
        background-color: #0f172a;
        alternate-background-color: #101827;
        border: 1px solid #1f2937;
        border-radius: 10px;
        gridline-color: #1f2937;
        selection-background-color: #f59e0b;
        selection-color: #0c0f14;
    }
    QHeaderView::section {
        background-color: #0b1220;
        color: #9fb3c8;
        border: none;
        padding: 8px;
        font-size: 10pt;
        font-weight: 700;
        text-transform: uppercase;
    }

    QGroupBox {
        border: 1px solid #1f2937;
        border-radius: 10px;
        margin-top: 10px;
        background-color: #0f172a;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #fbbf24;
        font-weight: 700;
    }

    QLabel#SectionTitle {
        font-size: 18pt;
        font-weight: 800;
        color: #f59e0b;
        letter-spacing: 0.5px;
    }
    QLabel#HintLabel {
        color: #9ca3af;
    }
    QLabel#TotalsBadge {
        background-color: #0b1220;
        border: 1px solid #f59e0b;
        border-radius: 14px;
        padding: 18px 22px;
        color: #fbbf24;
        font-size: 22pt;
        font-weight: 800;
    }

    QSplitter::handle {
        background-color: #1f2937;
    }
    """


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


def main() -> None:
    """Lanza la aplicación con la nueva apariencia."""

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
