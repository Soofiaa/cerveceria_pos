"""Tests de seguridad Fase 5.1b: registro de intentos fallidos y clave enmascarada."""

import json
import os
import pytest
import asyncio
import types

from core import config as core_config
from flet_app.api_server import create_app
from flet_app.config_view import ConfigView
from flet_app.theme import get_theme


class FakePage:
    def __init__(self):
        self.controls = []
        self.overlay = []
        self.bgcolor = ""
        self.title = ""
        self.window = types.SimpleNamespace(width=1280, height=720)
        self.updates = 0

    def add(self, *c):
        self.controls.extend(c)

    def update(self):
        self.updates += 1


TOKEN = "clave-secreta-muy-larga-1234567890"


@pytest.fixture
def api_client(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=TOKEN))
    app = create_app()
    return app.test_client(), tmp_path / "api_seguridad.log"


def test_intentos_fallidos_registran_ip_metodo_ruta_sin_filtrar_claves(api_client, monkeypatch):
    client, log_path = api_client
    # Forzar la ruta del log a tmp_path
    from flet_app import api_server
    monkeypatch.setattr(api_server, "_LOG_PATH", str(log_path))
    # Reiniciar logger cache para que tome la nueva ruta
    monkeypatch.setattr(api_server, "_LOG_SEGURIDAD", None)

    # 1. Request sin clave
    r1 = client.get("/api/products")
    assert r1.status_code == 401

    # 2. Request con clave mala (intentando colar la clave real o mala)
    r2 = client.post("/api/tickets", json={}, headers={"X-Caja-Token": "clave-mala-xyz"})
    assert r2.status_code == 401

    assert os.path.exists(log_path)
    contenido = log_path.read_text(encoding="utf-8")
    
    # Debe registrar IP (ej. 127.0.0.1), método y ruta
    assert "GET /api/products" in contenido
    assert "POST /api/tickets" in contenido
    # NUNCA debe contener la clave mala ni la clave real
    assert "clave-mala-xyz" not in contenido
    assert TOKEN not in contenido


def test_requests_correctas_no_se_registran(api_client, monkeypatch):
    client, log_path = api_client
    from flet_app import api_server
    monkeypatch.setattr(api_server, "_LOG_PATH", str(log_path))
    monkeypatch.setattr(api_server, "_LOG_SEGURIDAD", None)

    # 1. GET /api/health sin clave (ruta pública)
    r1 = client.get("/api/health")
    assert r1.status_code == 200

    # 2. GET /api/products con clave correcta
    r2 = client.get("/api/products", headers={"X-Caja-Token": TOKEN})
    assert r2.status_code == 200

    assert not os.path.exists(log_path) or log_path.read_text(encoding="utf-8").strip() == ""


def test_error_de_escritura_en_log_no_bota_request_401(api_client, monkeypatch):
    client, log_path = api_client
    from flet_app import api_server
    # Forzar _logger_seguridad a lanzar excepcion o registrar en ruta prohibida
    monkeypatch.setattr(api_server, "_LOG_PATH", "Z:\\ruta\\imposible\\api_seguridad.log")
    monkeypatch.setattr(api_server, "_LOG_SEGURIDAD", None)

    r = client.get("/api/products")
    assert r.status_code == 401
    assert "error" in r.get_json()


def test_modo_cliente_campo_clave_tiene_password_true(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=TOKEN))
    view = ConfigView(FakePage(), get_theme("lila"), lambda n: None, lambda c: None)
    view.dd_caja_mode.value = "client"
    view._sync_caja_visibility()
    # shortcut: el campo in_api_token es el campo de contraseña de la caja cliente
    assert view.in_api_token.password is True
    assert view.in_api_token.can_reveal_password is True


def test_modo_servidor_clave_enmascarada_y_copia_completa(temp_db, tmp_path, monkeypatch):
    token_real = "1234567890abcdefAB12"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=token_real))
    
    page = FakePage()
    view = ConfigView(page, get_theme("lila"), lambda n: None, lambda c: None)
    view.dd_caja_mode.value = "server"
    view._sync_caja_visibility()

    # 1. El texto visible del campo txt_token debe estar enmascarado y terminar en AB12
    visible = view.txt_token.value
    assert token_real not in visible
    assert visible.endswith("AB12")
    assert "•" in visible

    # 2. El boton copiar debe copiar la clave COMPLETA real al portapapeles
    copiado = []
    async def fake_set(val):
        copiado.append(val)
    monkeypatch.setattr(view.clipboard, "set", fake_set)

    asyncio.run(view._copy_token(None))
    assert copiado == [token_real]
