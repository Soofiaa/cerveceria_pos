from PySide6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("POS Cervecería (Escritorio)")

        # --- Crear pestañas y guardar referencias ---
        self.tabs = QTabWidget()

        self.pos_view = POSView()
        self.products_view = ProductsView()
        self.reports_view = ReportsView()

        self.tabs.addTab(self.pos_view, "POS")
        self.tabs.addTab(self.products_view, "Productos")
        self.tabs.addTab(self.reports_view, "Reportes")

        # --- Conectar cambio de pestaña ---
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- Layout principal ---
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.tabs)
        self.setCentralWidget(container)

        self.resize(1100, 700)
