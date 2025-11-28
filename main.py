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
    """Define una paleta clara con acentos cálidos para toda la app."""

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


def _build_stylesheet() -> str:
    """Estilos globales claros y minimalistas, incluidos popups."""

    return """
    QWidget {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: "Inter", "Segoe UI", "Arial", sans-serif;
        font-size: 11pt;
    }

    QTabWidget::pane {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 12px;
        background-color: #ffffff;
    }
    QTabBar::tab {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 10px 16px;
        margin-right: 6px;
        color: #475569;
    }
    QTabBar::tab:selected {
        background: #f4a506;
        color: #0f172a;
        border-color: #f4a506;
        font-weight: 700;
    }

    QPushButton {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        color: #0f172a;
        border-radius: 10px;
        padding: 8px 14px;
        font-weight: 600;
    }
    QPushButton:hover {
        border-color: #f4a506;
        box-shadow: 0 4px 10px rgba(15, 23, 42, 0.08);
    }
    QPushButton:pressed {
        background-color: #f1f5f9;
    }
    QPushButton[buttonType="primary"] {
        background-color: #f4a506;
        border: 1px solid #f4a506;
        color: #0f172a;
        box-shadow: 0 6px 18px rgba(244, 165, 6, 0.3);
    }
    QPushButton[buttonType="primary"]:hover {
        background-color: #f7b733;
        border-color: #f7b733;
    }
    QPushButton[buttonType="danger"] {
        background-color: #ffe9e6;
        border: 1px solid #ff8067;
        color: #a11200;
    }
    QPushButton[buttonType="ghost"] {
        background-color: transparent;
        color: #475569;
        border: 1px dashed #e2e8f0;
    }

    QLineEdit, QComboBox, QSpinBox, QDateEdit {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 8px 10px;
        selection-background-color: #f4a506;
        selection-color: #0f172a;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
        border: 1px solid #f4a506;
        box-shadow: 0 0 0 3px rgba(244, 165, 6, 0.18);
    }

    QListWidget {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
    }
    QListWidget::item {
        padding: 8px;
    }
    QListWidget::item:selected {
        background-color: #f4a506;
        color: #0f172a;
        border-radius: 6px;
    }

    QTableView, QTableWidget {
        background-color: #ffffff;
        alternate-background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        gridline-color: #e2e8f0;
        selection-background-color: #f4a506;
        selection-color: #0f172a;
    }
    QHeaderView::section {
        background-color: #f1f5f9;
        color: #475569;
        border: none;
        padding: 8px;
        font-size: 10pt;
        font-weight: 700;
        text-transform: uppercase;
    }

    QGroupBox {
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        margin-top: 10px;
        background-color: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #c26a00;
        font-weight: 700;
    }

    QLabel#SectionTitle {
        font-size: 18pt;
        font-weight: 800;
        color: #c26a00;
        letter-spacing: 0.5px;
    }
    QLabel#HintLabel {
        color: #64748b;
    }
    QLabel#TotalsBadge {
        background-color: #fff7e6;
        border: 1px solid #f4a506;
        border-radius: 14px;
        padding: 18px 22px;
        color: #c26a00;
        font-size: 22pt;
        font-weight: 800;
    }

    QSplitter::handle {
        background-color: #e2e8f0;
    }

    /* Ventanas emergentes claras */
    QDialog, QMessageBox {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
    }
    QMessageBox QLabel {
        color: #0f172a;
    }
    QMessageBox QPushButton {
        min-width: 96px;
        padding: 8px 12px;
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
