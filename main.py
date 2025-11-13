# main.py
import sys
import os, sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
from core import db_manager
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cervecería POS")
        self.resize(1100, 700)

        tabs = QTabWidget()
        tabs.addTab(POSView(), "POS")
        tabs.addTab(ProductsView(), "Productos")
        tabs.addTab(ReportsView(), "Reportes")

        self.setCentralWidget(tabs)


def main():
    db_manager.bootstrap()   # crea BD y tablas si no existen

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
