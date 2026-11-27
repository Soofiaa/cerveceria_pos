import sys

import pytest
from PySide6.QtWidgets import QApplication

from core import config


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


# temp_db (conftest): MainWindow arma la vista POS, que lee productos y tickets.
# Sin esta fixture abrian la base real del usuario (~/MiPOS/cerveceria.db).
@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", str(path))
    config.save_config(dict(config.DEFAULT_CONFIG, theme="neutro"), str(path))
    return path


@pytest.mark.parametrize("theme_name", ["neutro", "cerveceria", "oscuro", "menta", "lila", "grafito"])
def test_apply_theme_does_not_raise(qapp, temp_db, temp_config, theme_name):
    import main

    window = main.MainWindow()
    window.apply_theme(theme_name)
    assert window.windowTitle() == config.DEFAULT_CONFIG["business_name"]


def test_apply_theme_reads_business_name_from_config(qapp, temp_db, temp_config):
    import main

    config.save_config(dict(config.DEFAULT_CONFIG, business_name="Local Prueba", theme="oscuro"), str(temp_config))
    window = main.MainWindow()
    window.apply_theme()
    assert window.windowTitle() == "Local Prueba"
