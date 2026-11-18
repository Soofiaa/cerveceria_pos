# ui/config_view.py
import os
import shutil

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabBar, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from core import config
from ui.theme import THEMES, build_stylesheet


class ConfigView(QWidget):
    """Pantalla de configuración del negocio. Guardar aplica los cambios en caliente."""

    def __init__(self, on_saved=None):
        super().__init__()
        self._on_saved = on_saved
        conf = config.load_config()

        self.business_name = QLineEdit(conf["business_name"])
        self.rut = QLineEdit(conf["rut"])
        self.address = QLineEdit(conf["address"])
        self.phone = QLineEdit(conf["phone"])

        self.theme = QComboBox()
        self.theme.addItems(list(THEMES.keys()))
        self.theme.setCurrentText(conf["theme"] if conf["theme"] in THEMES else "neutro")
        self.theme.currentTextChanged.connect(self._update_preview)

        self.logo_path = QLineEdit(conf["logo_path"])
        btn_logo = QPushButton("Elegir...")
        btn_logo.clicked.connect(self._pick_logo)
        logo_row = QHBoxLayout()
        logo_row.addWidget(self.logo_path)
        logo_row.addWidget(btn_logo)

        form = QFormLayout()
        form.addRow("Nombre del negocio:", self.business_name)
        form.addRow("RUT:", self.rut)
        form.addRow("Dirección:", self.address)
        form.addRow("Teléfono:", self.phone)
        form.addRow("Tema:", self.theme)
        form.addRow("Logo (PNG/JPG):", logo_row)

        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        btn_export = QPushButton("Exportar configuración")
        btn_export.clicked.connect(self._export)
        buttons = QHBoxLayout()
        buttons.addWidget(btn_save)
        buttons.addWidget(btn_export)
        buttons.addStretch()

        hint = QLabel("Los cambios se aplican al guardar, sin reiniciar.")
        hint.setObjectName("HintLabel")

        self.preview = self._build_preview()

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addLayout(buttons)
        lay.addWidget(self.preview)
        lay.addStretch()

        self._update_preview(self.theme.currentText())

    def _build_preview(self) -> QFrame:
        """Mini POS de muestra. Solo visual: no escribe nada."""
        frame = QFrame()
        frame.setObjectName("PreviewFrame")
        lay = QVBoxLayout(frame)

        title = QLabel("Vista previa")
        title.setObjectName("SectionTitle")

        tabs = QTabBar()
        tabs.addTab("POS")
        tabs.addTab("Productos")
        tabs.addTab("Reportes")

        search = QLineEdit()
        search.setPlaceholderText("Buscar producto...")

        table = QTableWidget(1, 3)
        table.setHorizontalHeaderLabels(["Producto", "Cant", "Total"])
        table.setItem(0, 0, QTableWidgetItem("Cerveza ejemplo"))
        table.setItem(0, 1, QTableWidgetItem("2"))
        table.setItem(0, 2, QTableWidgetItem("$5.000"))
        table.setMaximumHeight(90)

        cobrar = QPushButton("F12 - COBRAR")
        cobrar.setProperty("buttonType", "primary")

        lay.addWidget(title)
        lay.addWidget(tabs)
        lay.addWidget(search)
        lay.addWidget(table)
        lay.addWidget(cobrar)
        return frame

    def _update_preview(self, theme_name: str):
        """Aplica el QSS del tema elegido solo a la vista previa (no a la app)."""
        self.preview.setStyleSheet(build_stylesheet(theme_name))

    def _pick_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir logo", "", "Imágenes (*.png *.jpg *.jpeg)"
        )
        if path:
            self.logo_path.setText(path)

    def _collect(self) -> dict:
        return {
            "business_name": self.business_name.text().strip(),
            "rut": self.rut.text().strip(),
            "address": self.address.text().strip(),
            "phone": self.phone.text().strip(),
            "logo_path": self.logo_path.text().strip(),
            "theme": self.theme.currentText(),
        }

    def _save(self):
        data = self._collect()
        if not data["business_name"]:
            QMessageBox.warning(self, "Configuración", "El nombre del negocio no puede estar vacío.")
            return
        if data["theme"] not in THEMES:
            QMessageBox.warning(self, "Configuración", "Tema no válido.")
            return
        if data["logo_path"] and not os.path.isfile(data["logo_path"]):
            QMessageBox.warning(self, "Configuración", "El archivo del logo no existe.")
            return
        try:
            config.save_config(data)
        except OSError as e:
            QMessageBox.critical(self, "Configuración", f"No se pudo guardar:\n{e}")
            return
        if self._on_saved:
            self._on_saved(data["theme"])
        QMessageBox.information(self, "Configuración", "Configuración guardada.")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar configuración", "config.json", "JSON (*.json)")
        if not path:
            return
        try:
            shutil.copy2(config.CONFIG_PATH, path)
        except OSError as e:
            QMessageBox.critical(self, "Exportar", f"No se pudo exportar:\n{e}")
            return
        QMessageBox.information(self, "Exportar", f"Configuración exportada a:\n{path}")
