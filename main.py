# main.py
import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PySide6.QtGui import QFont, QPalette, QColor
from core import db_manager
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cervecería POS")
        self.resize(1100, 700)

        tabs = QTabWidget()

        self.pos_view = POSView()
        self.products_view = ProductsView()
        self.reports_view = ReportsView()

        tabs.addTab(self.pos_view, "POS")
        tabs.addTab(self.products_view, "Productos")
        tabs.addTab(self.reports_view, "Reportes")

        self.setCentralWidget(tabs)

        # Al completar venta, refrescar reportes
        self.pos_view.sale_completed.connect(self.reports_view.load_data)


def main():
    db_manager.bootstrap()   # crea BD y tablas si no existen

    app = QApplication(sys.argv)

    # --- Fuente general más grande ---
    font = QFont()
    font.setPointSize(11)      # sube si quieres más grande (12, 13…)
    app.setFont(font)

    # --- Estilos globales para inputs, botones y tablas ---
    app.setStyleSheet("""
    QWidget {
        font-size: 11pt;
    }

    QLineEdit, QComboBox, QSpinBox {
        min-height: 32px;
        padding: 4px 8px;
    }

    QPushButton {
        min-height: 34px;
        padding: 6px 14px;
        font-weight: 600;
    }

    QTableView::item, QTableWidget::item {
        padding: 6px;
    }

    QHeaderView::section {
        padding: 6px;
    }

    QTabBar::tab {
        min-height: 30px;
        padding: 6px 12px;
        font-weight: 600;
    }
    """)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Paleta blanca global
    palette = QPalette()
    palette.setColor(QPalette.Window, Qt.white)
    palette.setColor(QPalette.Base, Qt.white)
    palette.setColor(QPalette.AlternateBase, QColor("#fafafa"))
    palette.setColor(QPalette.WindowText, Qt.black)
    palette.setColor(QPalette.Text, Qt.black)
    palette.setColor(QPalette.Button, Qt.white)
    palette.setColor(QPalette.ButtonText, Qt.black)
    palette.setColor(QPalette.Highlight, QColor("#dbeafe"))      # celeste suave
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    # === Estilo global más cómodo ===
    app.setStyleSheet("""
        QWidget {
            font-family: "Segoe UI", "Arial";
            font-size: 10.5pt;
        }

        QTabBar::tab {
            padding: 6px 18px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            font-weight: 600;
        }

        QPushButton {
            padding: 6px 14px;
            border-radius: 6px;
            border: 1px solid #d0d0d0;
            background-color: #ffffff;
        }
        QPushButton:hover {
            background-color: #f3f3f3;
        }
        QPushButton:pressed {
            background-color: #e5e5e5;
        }

        QLineEdit, QComboBox, QDateEdit {
            border-radius: 6px;
            border: 1px solid #d0d0d0;
            padding: 4px 6px;
        }
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
            border: 1px solid #7ca5ff;
        }

        QTableView {
            gridline-color: #e4e4e4;
            selection-background-color: #dbeafe;
            selection-color: #000000;
        }
        QHeaderView::section {
            background-color: #f5f5f5;
            border: none;
            padding: 6px;
            font-weight: 600;
            font-size: 10pt;
        }

        QListWidget {
            border: 1px solid #e0e0e0;
        }
        QListWidget::item:selected {
            background-color: #dbeafe;
            color: #000000;
        }
    """)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())