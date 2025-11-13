from PySide6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("POS Cervecería (Escritorio)")
        tabs = QTabWidget()
        tabs.addTab(POSView(), "POS")
        tabs.addTab(ProductsView(), "Productos")
        tabs.addTab(ReportsView(), "Reportes")
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(tabs)
        self.setCentralWidget(container)
        self.resize(1100, 700)
