"""Tests de Fase 5.2: Reportes y Configuración en modo cliente.

Cubre:
1. Endpoints de reportes en la API (/api/reports/summary, /api/reports/sales, /api/reports/top-products).
2. Paridad entre LocalBackend y RemoteBackend.
3. ReportesView con datos y manejo de SinConexion.
4. Navegación en modo cliente (Reportes visible, Productos oculto).
5. ConfigView en modo cliente (campos del negocio de solo lectura con valores del servidor, Guardar no altera datos del negocio locales).
"""

import json
import types

import flet as ft
import pytest

from core import config as core_config
from core import db_manager
from core import product_service as ps
from core import report_service as rs
from core import sales_service as ss
from core import ticket_service as ts
from flet_app import backend as backend_mod
from flet_app import main as pos_main
from flet_app.api_client import SinConexion
from flet_app.api_server import create_app
from flet_app.reportes_view import ReportesView
from flet_app.config_view import ConfigView
from flet_app.theme import get_theme


TOKEN = "token-reportes-52"


class FakePage:
    def __init__(self):
        self.controls, self.overlay = [], []
        self.bgcolor = self.title = ""
        self.window = types.SimpleNamespace(width=1280, height=720, min_width=1000, min_height=650,
                                            maximized=False)
        self.updates = 0

    def add(self, *c):
        self.controls.extend(c)

    def update(self):
        self.updates += 1


class Caja1Session:
    def __init__(self, flask_client):
        self._c = flask_client
        self.alive = True

    def request(self, method, url, params=None, json=None, timeout=None, headers=None):
        if not self.alive:
            import requests
            raise requests.ConnectionError("Caja 1 apagada")
        path = "/" + url.split("/", 3)[3]
        r = self._c.open(path, method=method, query_string=params, json=json, headers=headers)

        class Resp:
            status_code = r.status_code

            @staticmethod
            def json():
                return r.get_json(silent=True)

        return Resp


@pytest.fixture
def caja1_env(temp_db, tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Cervecería Test", rut="12.3-4",
                                 api_token=TOKEN))
    app = create_app()
    return Caja1Session(app.test_client())


def _cobrar(p_id, qty, price):
    tid = ts.create_ticket("Ticket 1")
    ts.add_item(tid, p_id, qty, price)
    ts.set_pay_method(tid, "efectivo")
    sid, _ = ss.cobrar_ticket(tid)
    return sid


# ---------- 1. Tests de Endpoints API ----------
def test_api_reports_summary_and_sales(caja1_env):
    p1 = ps.create_product("IPA", 2000, stock=20)
    sid = _cobrar(p1, 2, 2000)
    with db_manager.get_conn() as con:
        con.execute("UPDATE sales SET created_at='2026-11-20 12:00:00' WHERE id=?", (sid,))
        con.commit()

    tc = create_app().test_client()
    
    # Sin token -> 401
    r = tc.get("/api/reports/summary?from=2026-11-01&to=2026-11-30")
    assert r.status_code == 401

    headers = {"X-Caja-Token": TOKEN}

    d1, d2 = "2026-11-01", "2026-11-30"

    # Summary: igual a report_service.summary
    r = tc.get(f"/api/reports/summary?from={d1}&to={d2}", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == rs.summary(d1, d2)
    assert r.get_json()["total"] == 4000 and r.get_json()["tickets"] == 1

    # Sales: igual a report_service.list_sales
    r = tc.get(f"/api/reports/sales?from={d1}&to={d2}", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == rs.list_sales(d1, d2)
    assert [v["id"] for v in r.get_json()] == [sid]

    # Top products: igual a report_service.top_products, con y sin limit
    r = tc.get(f"/api/reports/top-products?from={d1}&to={d2}&limit=5", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == rs.top_products(d1, d2, limit=5)
    r = tc.get(f"/api/reports/top-products?from={d1}&to={d2}", headers=headers)
    assert r.get_json() == rs.top_products(d1, d2)
    assert r.get_json()[0]["name"] == "IPA"


RUTAS = ("/api/reports/summary", "/api/reports/sales", "/api/reports/top-products")


@pytest.mark.parametrize("ruta", RUTAS)
def test_api_reports_sin_clave_o_clave_mala_da_401(caja1_env, ruta):
    tc = create_app().test_client()
    q = "?from=2026-11-01&to=2026-11-30"
    assert tc.get(ruta + q).status_code == 401
    assert tc.get(ruta + q, headers={"X-Caja-Token": "otra"}).status_code == 401


@pytest.mark.parametrize("ruta", RUTAS)
@pytest.mark.parametrize("query", [
    "",                                   # ambas ausentes
    "?from=2026-11-30",                   # falta to
    "?to=2026-11-01",                     # falta from
    "?from=&to=",                         # vacias
    "?from=30/11/2026&to=2026-12-01",     # formato invalido
    "?from=2026-11-01&to=2026-11-31",     # dia inexistente
    "?from=2026-1-5&to=2026-11-30",       # no estricto
    "?from=2026-11-30&to=2026-11-01",     # invertido
])
def test_api_reports_fechas_invalidas_dan_400(caja1_env, ruta, query):
    r = create_app().test_client().get(ruta + query, headers={"X-Caja-Token": TOKEN})
    assert r.status_code == 400
    assert r.get_json()["error"]


@pytest.mark.parametrize("limit", ["abc", "", "0", "-1", "51", "1.5"])
def test_api_top_products_limit_invalido_da_400(caja1_env, limit):
    r = create_app().test_client().get(
        f"/api/reports/top-products?from=2026-11-01&to=2026-11-30&limit={limit}",
        headers={"X-Caja-Token": TOKEN})
    assert r.status_code == 400


@pytest.mark.parametrize("limit", ["1", "50"])
def test_api_top_products_limit_en_los_bordes_es_valido(caja1_env, limit):
    r = create_app().test_client().get(
        f"/api/reports/top-products?from=2026-11-01&to=2026-11-30&limit={limit}",
        headers={"X-Caja-Token": TOKEN})
    assert r.status_code == 200


# ---------- 2. Paridad de Backends ----------
def test_backend_parity(caja1_env):
    p1 = ps.create_product("Stout", 3000, stock=10)
    p2 = ps.create_product("Lager", 1500, stock=10)
    _cobrar(p1, 1, 3000)
    _cobrar(p2, 3, 1500)

    local = backend_mod.LocalBackend()
    remote = backend_mod.RemoteBackend("http://caja1:8780", caja1_env, TOKEN)

    d1, d2 = "2020-01-01", "2030-12-31"
    assert local.report_summary(d1, d2) == remote.report_summary(d1, d2)
    assert local.report_sales(d1, d2) == remote.report_sales(d1, d2)
    assert local.report_top_products(d1, d2) == remote.report_top_products(d1, d2)
    assert local.report_top_products(d1, d2, limit=1) == remote.report_top_products(d1, d2, limit=1)
    assert len(remote.report_sales(d1, d2)) == 2 and len(remote.report_top_products(d1, d2, limit=1)) == 1

    # Rango sin ventas: mismas estructuras vacias en ambos.
    assert local.report_summary("2000-01-01", "2000-01-02") == remote.report_summary("2000-01-01", "2000-01-02")
    assert remote.report_sales("2000-01-01", "2000-01-02") == []


# ---------- 3. ReportesView ----------
def test_reportes_view_renders_data():
    class FakeBackend:
        def report_summary(self, d1, d2):
            return {"total": 5000, "tickets": 2, "avg_ticket": 2500}
        def report_sales(self, d1, d2):
            return [{"id": 1, "created_at": "2026-11-25 10:00:00", "total": 5000}]
        def report_top_products(self, d1, d2, limit=10):
            return [{"name": "IPA", "qty": 2, "revenue": 5000}]
        def shopping_list(self):
            return []

    page = FakePage()
    view = ReportesView(page, get_theme("lila"), backend=FakeBackend())
    view.load_data()

    assert view.txt_total.value == "$5.000"
    assert view.txt_count.value == "2"
    assert view.txt_avg.value == "$2.500"
    assert len(view.sales_table.rows) == 1
    assert len(view.top_table.rows) == 1


def test_reportes_view_sin_conexion():
    class OfflineBackend:
        def report_summary(self, d1, d2):
            raise SinConexion("sin red")
        def report_sales(self, d1, d2):
            raise SinConexion("sin red")
        def report_top_products(self, d1, d2, limit=10):
            raise SinConexion("sin red")

    page = FakePage()
    view = ReportesView(page, get_theme("lila"), backend=OfflineBackend())
    view.load_data()  # No debe lanzar excepción
    assert "Sin conexión con la Caja 1" in view.msg.value
    assert view.txt_total.value == "$0"
    assert view.sales_table.rows == []


def test_reportes_view_exporta_csv_por_el_backend(tmp_path):
    class FakeBackend:
        def report_sales(self, d1, d2):
            return [{"id": 7, "created_at": "2026-11-25 10:00:00", "total": 5000}]

    view = ReportesView(FakePage(), get_theme("lila"), backend=FakeBackend())
    destino = tmp_path / "v.csv"
    view._save_csv_to(str(destino), "2026-11-25", "2026-11-25")
    lineas = destino.read_text(encoding="utf-8-sig").splitlines()
    assert lineas[1] == "2026-11-25 10:00:00,7,5000"


def test_reportes_view_exportar_sin_conexion_avisa_y_no_escribe(tmp_path):
    class OfflineBackend:
        def report_sales(self, d1, d2):
            raise SinConexion("sin red")

    page = FakePage()
    view = ReportesView(page, get_theme("lila"), backend=OfflineBackend())
    destino = tmp_path / "v.csv"
    view._save_csv_to(str(destino), "2026-11-25", "2026-11-25")
    assert not destino.exists()
    dialogos = [c for c in page.overlay if isinstance(c, ft.AlertDialog)]
    assert len(dialogos) == 1 and "Sin conexión con la Caja 1" in dialogos[0].content.value


# ---------- 4. Navegación en modo cliente ----------
def test_cliente_muestra_reportes_y_oculta_productos(caja1_env, monkeypatch):
    monkeypatch.setattr(pos_main, "make_backend",
                        lambda settings=None, session=None: backend_mod.RemoteBackend(
                            "http://caja1:8780", caja1_env, TOKEN))
    monkeypatch.setattr(pos_main, "get_caja_settings",
                        lambda cfg=None: {"mode": "client", "server_url": "http://caja1:8780",
                                          "caja_number": 2, "caja_name": "Barra", "api_port": 8780,
                                          "api_token": TOKEN})
    page = FakePage()
    pos_main.main(page)

    top_bar = page.controls[0].controls[0]
    tabs = {c.content.controls[1].value: c for c in top_bar.content.controls
            if isinstance(c, ft.Container) and isinstance(c.content, ft.Row)
            and len(c.content.controls) > 1 and isinstance(c.content.controls[1], ft.Text)}

    assert tabs["Productos"].visible is False
    assert tabs["Reportes"].visible is not False

    # Reportes abre de verdad en modo cliente y pide los datos por la API.
    import asyncio
    asyncio.run(tabs["Reportes"].on_click(None))
    area = page.controls[0].controls[1].controls[1].content
    assert isinstance(area.controls[0].content.controls[1], ReportesView)
    assert area.controls[0].content.controls[1].backend is pos_main.backend

    # Productos sigue sin abrirse: vuelve al POS.
    asyncio.run(tabs["Productos"].on_click(None))
    assert len(area.controls) == 2


# ---------- 5. ConfigView en modo cliente ----------
class _ClienteBackend:
    """Caja adicional: lo unico que ConfigView le pide es config() de la Caja 1."""

    is_remote = True

    def __init__(self, server_cfg=None, falla=False):
        self._server_cfg = server_cfg or {}
        self._falla = falla

    def config(self):
        if self._falla:
            raise SinConexion("sin conexión con la Caja 1")
        return dict(self._server_cfg)


SERVER_CFG = {"business_name": "Cervecería Caja 1", "rut": "76.1-7",
              "address": "Av. Caja 1 123", "phone": "+56 9 1111 1111"}


def test_config_view_client_mode_business_read_only(temp_db, tmp_path, monkeypatch):
    """Modo cliente: los datos del negocio son de la Caja 1, deshabilitados, con la nota."""
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Local Local", rut="99-9",
                                 address="Calle Local 1", phone="+56 9 0000 0000"))

    page = FakePage()
    view = ConfigView(page, get_theme("lila"), lambda n: None, lambda c: None,
                      backend=_ClienteBackend(SERVER_CFG))

    # Valores de la Caja 1, no los del config local.
    assert view.in_name.value == "Cervecería Caja 1"
    assert view.in_rut.value == "76.1-7"
    assert view.in_address.value == "Av. Caja 1 123"
    assert view.in_phone.value == "+56 9 1111 1111"
    # Campos deshabilitados y nota visible.
    for campo in (view.in_name, view.in_rut, view.in_address, view.in_phone):
        assert campo.disabled is True
    assert view.business_note.visible is True
    assert view.business_note.value == "Los datos del negocio se editan en la Caja 1."


def test_config_view_client_mode_sin_conexion(temp_db, tmp_path, monkeypatch):
    """Si la Caja 1 no responde: campos vacios y la nota lo dice."""
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Local Local", rut="99-9"))

    view = ConfigView(FakePage(), get_theme("lila"), lambda n: None, lambda c: None,
                      backend=_ClienteBackend(falla=True))

    assert view.in_name.value == ""
    assert view.in_rut.value == ""
    assert view.in_address.value == ""
    assert view.in_phone.value == ""
    assert view.business_note.value == "Sin conexión con la Caja 1."


def test_config_view_client_mode_guardar_no_toca_los_datos_del_negocio(temp_db, tmp_path, monkeypatch):
    """Guardar en modo cliente deja intactos los datos del negocio del config local."""
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Local Local", rut="99-9",
                                 address="Calle Local 1", phone="+56 9 0000 0000",
                                 logo_path="C:/local/logo.png", theme="lila"))

    view = ConfigView(FakePage(), get_theme("lila"), lambda n: None, lambda c: None,
                      backend=_ClienteBackend(SERVER_CFG))
    view.dd_caja_mode.value = "client"
    view.in_server_url.value = "192.168.1.10"
    view.in_caja_name.value = "Barra"
    view.in_caja_number.value = "2"
    view.in_api_token.value = "clave-123"
    view.dd_prefix.value = "Mesa"
    view._save()

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    # Los datos del negocio NO se pisaron con los de la Caja 1 ni se vaciaron.
    assert cfg["business_name"] == "Local Local" and cfg["rut"] == "99-9"
    assert cfg["address"] == "Calle Local 1" and cfg["phone"] == "+56 9 0000 0000"
    assert cfg["logo_path"] == "C:/local/logo.png"
    # El resto si se guarda como hoy.
    assert cfg["mode"] == "client" and cfg["server_url"] == "http://192.168.1.10:8780"
    assert (cfg["caja_name"], cfg["caja_number"], cfg["api_token"]) == ("Barra", 2, "clave-123")
    assert cfg["ticket_prefix"] == "Mesa"


def test_config_view_modo_local_no_cambia(temp_db, tmp_path, monkeypatch):
    """Sin backend (modo local/servidor) Configuracion se comporta como antes."""
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Mi Local", rut="1-9"))

    view = ConfigView(FakePage(), get_theme("lila"), lambda n: None, lambda c: None)
    assert view.is_remote is False
    assert view.in_name.value == "Mi Local" and view.in_name.disabled is False
    assert view.business_note.visible is False

    view.in_name.value = "Nombre Nuevo"
    view.in_rut.value = "2-7"
    view._save()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["business_name"] == "Nombre Nuevo" and cfg["rut"] == "2-7"
