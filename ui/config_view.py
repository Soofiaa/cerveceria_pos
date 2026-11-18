# ui/config_view.py
import os
import shutil

from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from core import config
from ui.theme import THEMES


class ConfigView(QWidget):
    """Pantalla de configuración del negocio. Los cambios se aplican al reiniciar."""

    def __init__(self):
        super().__init__()
        conf = config.load_config()

        self.business_name = QLineEdit(conf["business_name"])
        self.rut = QLineEdit(conf["rut"])
        self.address = QLineEdit(conf["address"])
        self.phone = QLineEdit(conf["phone"])

        self.theme = QComboBox()
        self.theme.addItems(list(THEMES.keys()))
        self.theme.setCurrentText(conf["theme"] if conf["theme"] in THEMES else "neutro")

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

        hint = QLabel("Los cambios de nombre y tema se aplican al reiniciar la aplicación.")
        hint.setObjectName("HintLabel")

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addLayout(buttons)
        lay.addStretch()

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
        QMessageBox.information(
            self, "Configuración",
            "Configuración guardada. Reinicia la aplicación para aplicar nombre y tema.",
        )

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
