import json

from core import config
from ui.theme import get_theme


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    data = {
        "business_name": "Local Prueba",
        "rut": "11.111.111-1",
        "address": "Calle 1",
        "phone": "+56 9 1234 5678",
        "logo_path": "",
        "theme": "oscuro",
    }
    config.save_config(data, str(path))
    assert config.load_config(str(path)) == data


def test_corrupt_json_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ esto no es json", encoding="utf-8")
    assert config.load_config(str(path)) == config.DEFAULT_CONFIG


def test_unknown_theme_falls_back_to_neutro():
    assert get_theme("no_existe") == get_theme("neutro")
