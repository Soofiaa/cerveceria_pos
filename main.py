# main.py
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from core import db_manager, config
from ui.theme import get_theme, build_stylesheet
from ui.pos.pos_view import POSView
from ui.products_view import ProductsView
from ui.reports_view import ReportsView
from ui.config_view import ConfigView


# ==========================================================
# Paleta clara
# ==========================================================
def _build_palette(theme_name: str) -> QPalette:
    """Devuelve una paleta según el tema seleccionado."""
    theme = get_theme(theme_name)
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(theme["background"]))
    palette.setColor(QPalette.Base, QColor(theme["surface"]))
    palette.setColor(QPalette.AlternateBase, QColor(theme["background"]))
    palette.setColor(QPalette.WindowText, QColor(theme["text"]))
    palette.setColor(QPalette.Text, QColor(theme["input_text"]))
    palette.setColor(QPalette.Button, QColor(theme["surface"]))
    palette.setColor(QPalette.ButtonText, QColor(theme["input_text"]))
    palette.setColor(QPalette.Highlight, QColor(theme["primary"]))
    palette.setColor(QPalette.HighlightedText, QColor(theme["primary_text"]))
    palette.setColor(QPalette.Link, QColor(theme["secondary"]))
    palette.setColor(QPalette.BrightText, QColor(theme["accent"]))
    return palette


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
        products_view = ProductsView()
        tabs.addTab(POSView(), "POS")
        tabs.addTab(products_view, "Productos")
        tabs.addTab(ReportsView(), "Reportes")
        tabs.addTab(ConfigView(on_saved=self.apply_theme), "Configuración")
        tabs.currentChanged.connect(
            lambda i: products_view.reload() if tabs.widget(i) is products_view else None
        )

        self.setCentralWidget(tabs)

    def apply_theme(self, theme_name=None):
        """
        Aplica tema y nombre a toda la app sin reiniciar.
        Sin argumento, lee el tema y el nombre desde config.json.
        """
        conf = config.load_config()
        theme = theme_name or conf.get("theme", "neutro")
        app = QApplication.instance()
        app.setPalette(_build_palette(theme))
        app.setStyleSheet(build_stylesheet(theme))
        self.setWindowTitle(conf["business_name"])


# ==========================================================
# Main
# ==========================================================
def main() -> None:
    db_manager.bootstrap()
    conf = config.load_config()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Icono de la app. Con PyInstaller los datos viven en sys._MEIPASS
    # (empaquetar con: --icon assets/icon.ico --add-data "assets;assets").
    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    icon_path = base_dir / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    font = QFont("Inter", 11)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    window = MainWindow()
    window.apply_theme()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
