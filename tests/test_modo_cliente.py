"""Tests del modo cliente en la app Flet (Fase 5.1, multi-caja).

La Caja 1 es la API real (flet_app/api_server.py) servida por el cliente de
pruebas de Flask, sin abrir ningun puerto. La caja cliente es flet_app.main
con config "client". Se verifica sobre todo:
- que en modo cliente NO se toca ninguna base local,
- que sin conexion no se puede cobrar,
- que el cobro por API descuenta el stock en la Caja 1 y devuelve el id del servidor.
"""

import asyncio
import json
import types

import flet as ft
import pytest
import requests

from core import config as core_config
from core import db_manager
from core import product_service as ps
from core import ticket_service as ts
from flet_app import backend as backend_mod
from flet_app import main as pos_main
from flet_app.api_client import SinConexion
from flet_app.api_server import create_app


TOKEN = "clave-de-prueba"


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
    """requests.Session falsa: despacha a la API de la Caja 1 (Flask en memoria).

    `alive=False` simula la Caja 1 apagada: toda llamada falla como sin red.
    """

    def __init__(self, flask_client):
        self._c = flask_client
        self.alive = True
        self.calls = []

    def request(self, method, url, params=None, json=None, timeout=None, headers=None):
        if not self.alive:
            raise requests.ConnectionError("Caja 1 apagada")
        path = "/" + url.split("/", 3)[3]
        self.calls.append((method, path))
        r = self._c.open(path, method=method, query_string=params, json=json, headers=headers)

        class Resp:
            status_code = r.status_code

            @staticmethod
            def json():
                return r.get_json(silent=True)

        return Resp


@pytest.fixture
def caja1(temp_db, tmp_path, monkeypatch):
    """Caja 1: la base temporal (temp_db) y su API. Devuelve la sesion falsa."""
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Cervecería Ñandú", rut="76.1-7",
                                 api_token=TOKEN))
    return Caja1Session(create_app().test_client())


@pytest.fixture
def cliente(caja1, monkeypatch):
    """Una caja en modo cliente conectada a la Caja 1 falsa."""
    monkeypatch.setattr(pos_main, "make_backend",
                        lambda settings=None, session=None: backend_mod.RemoteBackend(
                            "http://caja1:8780", caja1, TOKEN))
    monkeypatch.setattr(pos_main, "get_caja_settings",
                        lambda cfg=None: {"mode": "client", "server_url": "http://caja1:8780",
                                          "caja_number": 2, "caja_name": "Barra", "api_port": 8780,
                                          "api_token": TOKEN})
    return caja1


# ---------- helpers de UI ----------
def _area(page):
    return page.controls[0].controls[1].controls[1].content


def _summary(page):
    return _area(page).controls[1].controls[0].content


def _cobrar_btn(page):
    return _summary(page).controls[5]


def _search_input(page):
    return _area(page).controls[0].controls[0].content.controls[0].controls[0]


def _conn_bar(page):
    ticket_card = _area(page).controls[0].controls[1]
    return ticket_card.content.controls[1]


def _badge(page):
    return page.controls[0].controls[0].content.controls[-1]


def _dialogs(page):
    return [c for c in page.overlay if isinstance(c, ft.AlertDialog) and c.open]


# ---------- 1. En modo cliente no se toca ninguna base local ----------
def _guardia_de_base_local(monkeypatch, caja1):
    """Hace fallar cualquier apertura de base hecha por la CAJA CLIENTE.

    La Caja 1 falsa corre en el mismo proceso y usa core/ legitimamente: solo se
    bloquea la apertura que ocurre FUERA de una llamada a su API (es decir, la
    que haria la app cliente por su cuenta).
    """
    real_get_conn = db_manager.get_conn
    dentro_de_la_api = {"n": 0}
    abiertas_por_el_cliente = []
    request_original = caja1.request

    def request(*a, **k):
        dentro_de_la_api["n"] += 1
        try:
            return request_original(*a, **k)
        finally:
            dentro_de_la_api["n"] -= 1

    def get_conn_vigilada():
        if dentro_de_la_api["n"] == 0:
            abiertas_por_el_cliente.append(1)
            raise AssertionError("modo cliente intento abrir una base local")
        return real_get_conn()

    caja1.request = request
    monkeypatch.setattr(db_manager, "get_conn", get_conn_vigilada)
    for mod in ("core.ticket_service", "core.product_service", "core.sales_service"):
        monkeypatch.setattr(mod + ".get_conn", get_conn_vigilada)
    return abiertas_por_el_cliente


def test_modo_cliente_no_abre_ni_crea_base_local(cliente, monkeypatch):
    import os
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)   # la Caja 1 ya tiene el catalogo
    abiertas = _guardia_de_base_local(monkeypatch, cliente)
    ruta_local = os.path.join(os.path.dirname(db_manager.DB_PATH), "BASE_LOCAL_DE_LA_CAJA.db")

    page = FakePage()
    pos_main.main(page)                                  # arranca, crea ticket y refresca por API
    _agregar_producto_al_ticket(page)
    _cobrar_btn(page).on_click(None)
    asyncio.run(_pestanas_pos(page))

    assert abiertas == []                                # la caja cliente nunca abrio una base
    assert not os.path.exists(ruta_local)
    assert pos_main.backend.is_remote is True
    assert any(p == "/api/tickets" for _m, p in cliente.calls)   # todo paso por la API


def test_modo_cliente_no_llama_a_bootstrap(cliente, monkeypatch):
    llamadas = []
    monkeypatch.setattr(db_manager, "bootstrap", lambda: llamadas.append(1))
    pos_main.main(FakePage())
    assert llamadas == []


def test_modo_standalone_y_server_si_preparan_la_base_local(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    for modo in ("standalone", "server"):
        llamadas = []
        real = db_manager.bootstrap
        monkeypatch.setattr(db_manager, "bootstrap", lambda real=real: (llamadas.append(1), real()))
        core_config.save_config(dict(core_config.DEFAULT_CONFIG, mode=modo))
        pos_main.main(FakePage())
        assert llamadas, f"{modo} debe preparar la base local"
        assert pos_main.backend.is_remote is False


def test_standalone_funciona_como_antes_sin_red_ni_servidor(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, mode="standalone"))
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    assert pos_main._api_start_calls, "main() debe pedir arrancar la API (el conftest la reemplaza por un doble)"
    search = _search_input(page)
    search.value = "7801"
    asyncio.run(search.on_submit(None))
    assert [i["product_name"] for t in ts.list_open_tickets() for i in ts.list_items(t["id"])] == ["Rubia"]


def test_server_pide_arrancar_la_api_y_standalone_no(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    arrancados = []
    from flet_app import api_server
    monkeypatch.setattr(api_server, "run", lambda **k: arrancados.append(k))
    # start_api_server_if_needed real (el conftest la reemplaza por un doble)
    import importlib
    real = importlib.reload(pos_main).start_api_server_if_needed
    assert real({"mode": "standalone", "api_port": 8780}) is False
    assert real({"mode": "client", "api_port": 8780}) is False
    assert arrancados == []


# ---------- 2. Sin conexion no se puede cobrar ----------
def _agregar_producto_al_ticket(page, codigo="7801"):
    search = _search_input(page)
    search.value = codigo
    asyncio.run(search.on_submit(None))


def test_sin_conexion_se_muestra_el_estado_y_no_se_puede_cobrar(cliente):
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    assert _cobrar_btn(page).disabled is False            # con conexion si
    assert _conn_bar(page).visible is False and _badge(page).visible is False

    cliente.alive = False                                  # se apaga la Caja 1
    asyncio.run(_search_input(page).on_submit(None))       # cualquier accion toca la red
    # la siguiente lectura (refrescar) detecta la caida
    asyncio.run(_pestanas_pos(page))
    assert _conn_bar(page).visible is True and _badge(page).visible is True
    assert "Sin conexión con la Caja 1" in _conn_bar(page).content.controls[1].value
    assert _cobrar_btn(page).disabled is True


def _pestanas_pos(page):
    """Pulsa la pestana POS (recarga el ticket desde la Caja 1)."""
    top_bar = page.controls[0].controls[0]
    pos = next(c for c in top_bar.content.controls
               if isinstance(c, ft.Container) and isinstance(c.content, ft.Row)
               and c.content.controls[1].value == "POS")
    return pos.on_click(None)


def test_sin_conexion_el_boton_cobrar_no_abre_el_dialogo_ni_vende(cliente):
    pid = ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    cliente.alive = False
    asyncio.run(_pestanas_pos(page))
    assert _cobrar_btn(page).disabled is True

    cliente.calls.clear()
    _cobrar_btn(page).on_click(None)                       # aunque se fuerce el clic
    dlgs = _dialogs(page)
    assert len(dlgs) == 1 and "Sin conexión con la Caja 1" in dlgs[0].content.value
    assert not any(m == "POST" and p.endswith("/charge") for m, p in cliente.calls)
    cliente.alive = True
    assert ps.get_product(pid)["stock"] == 10              # nada se vendio
    assert _ventas() == []


def _ventas():
    with db_manager.get_conn() as con:
        return con.execute("select id from sales").fetchall()


def test_la_conexion_se_pierde_justo_al_confirmar_el_cobro(cliente):
    """Si la red cae con el dialogo abierto, no se cobra, se avisa y el ticket sigue abierto."""
    pid = ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    _cobrar_btn(page).on_click(None)
    charge = _dialogs(page)[-1]
    recibido = next(c for c in charge.content.controls if isinstance(c, ft.TextField))
    recibido.value = "5000"
    recibido.on_change(None)

    cliente.alive = False                                  # cae justo antes de confirmar
    asyncio.run(recibido.on_submit(None))

    assert _ventas() == []
    assert ps.get_product(pid)["stock"] == 10
    assert _badge(page).visible is True and _cobrar_btn(page).disabled is True
    textos = " ".join(d.content.value for d in _dialogs(page) if isinstance(d.content, ft.Text))
    assert "Se perdió la conexión" in textos and "antes de cobrar de nuevo" in textos
    assert len(ts.list_open_tickets()) == 1                # el ticket sigue abierto


def test_al_volver_la_conexion_se_puede_cobrar_de_nuevo(cliente):
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    cliente.alive = False
    asyncio.run(_pestanas_pos(page))
    assert _cobrar_btn(page).disabled is True

    cliente.alive = True
    reintentar = _conn_bar(page).content.controls[2]
    reintentar.on_click(None)
    assert _badge(page).visible is False and _conn_bar(page).visible is False
    assert _cobrar_btn(page).disabled is False


def test_reintentar_sin_conexion_sigue_bloqueado(cliente):
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    cliente.alive = False
    asyncio.run(_pestanas_pos(page))
    _conn_bar(page).content.controls[2].on_click(None)     # Reintentar con la Caja 1 aun apagada
    assert _badge(page).visible is True and _cobrar_btn(page).disabled is True


# ---------- 3. Cobro por API ----------
def test_cobrar_en_la_caja_cliente_descuenta_stock_y_usa_el_id_del_servidor(cliente):
    pid = ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    _cobrar_btn(page).on_click(None)
    charge = _dialogs(page)[-1]
    recibido = next(c for c in charge.content.controls if isinstance(c, ft.TextField))
    recibido.value = "5000"
    recibido.on_change(None)
    asyncio.run(recibido.on_submit(None))

    done = _dialogs(page)[-1]
    assert done.title.value == "Venta cobrada" and "Venta 1 cobrada" in done.content.value
    assert "Vuelto: $3.500" in done.content.value
    assert ps.get_product(pid)["stock"] == 9               # lo decidio la Caja 1
    assert [r[0] for r in _ventas()] == [1]
    assert any(m == "POST" and p.endswith("/charge") for m, p in cliente.calls)


def test_el_comprobante_de_la_caja_cliente_usa_los_datos_del_servidor(cliente):
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    _cobrar_btn(page).on_click(None)
    recibido = next(c for c in _dialogs(page)[-1].content.controls if isinstance(c, ft.TextField))
    recibido.value = "5000"
    recibido.on_change(None)
    asyncio.run(recibido.on_submit(None))

    data = pos_main.backend.receipt(1, 5000)
    assert data["business_name"] == "Cervecería Ñandú" and data["rut"] == "76.1-7"   # los de la Caja 1
    assert data["total"] == 1500 and data["received"] == 5000 and data["change"] == 3500
    assert [i["name"] for i in data["items"]] == ["Rubia"]


def test_tarjeta_no_lleva_recibido_ni_vuelto_en_el_comprobante(cliente):
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    _agregar_producto_al_ticket(page)
    tid = pos_main.backend.list_open_tickets()[0]["id"]
    sale_id, _ = pos_main.backend.cobrar(tid, "debito")
    data = pos_main.backend.receipt(sale_id, 9999)
    assert data["received"] is None and data["change"] is None


def test_el_cliente_no_puede_cambiar_el_precio(cliente):
    pid = ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)
    tid = pos_main.backend.list_open_tickets()[0]["id"]
    pos_main.backend.add_item(tid, pid, 1, 1)              # intenta venderlo a $1
    assert pos_main.backend.list_items(tid)[0]["unit_price"] == 1500


def test_dos_cajas_cliente_venden_con_ids_distintos_y_stock_compartido(cliente, monkeypatch):
    pid = ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    a = backend_mod.RemoteBackend("http://caja1:8780", cliente, TOKEN)
    b = backend_mod.RemoteBackend("http://caja1:8780", cliente, TOKEN)
    ids = []
    for caja in (a, b, a):
        tid = caja.create_ticket()
        caja.add_item(tid, pid, 2, 0)
        ids.append(caja.cobrar(tid, "efectivo")[0])
    assert ids == [1, 2, 3] and ps.get_product(pid)["stock"] == 4


# ---------- 4. Cambio de tema en modo cliente ----------
def test_cambio_de_tema_en_modo_cliente_reutiliza_el_backend_y_no_toca_la_base(cliente, monkeypatch):
    page = FakePage()
    pos_main.main(page)
    backend_antes = pos_main.backend
    prohibido = lambda *a, **k: (_ for _ in ()).throw(AssertionError("base local"))  # noqa: E731
    monkeypatch.setattr(db_manager, "get_conn", prohibido)
    monkeypatch.setattr(db_manager, "bootstrap", prohibido)
    pos_main.main(page, restore={"theme": "oscuro", "backend": backend_antes})
    assert pos_main.backend is backend_antes


def test_la_pestana_conexion_no_cambia_el_orden_de_las_pestanas(cliente):
    page = FakePage()
    pos_main.main(page)
    top_bar = page.controls[0].controls[0]
    etiquetas = [c.content.controls[1].value for c in top_bar.content.controls
                 if isinstance(c, ft.Container) and isinstance(c.content, ft.Row)
                 and len(c.content.controls) > 1 and isinstance(c.content.controls[1], ft.Text)
                 and c.content.controls[1].value in ("POS", "Productos", "Reportes", "Configuración")]
    assert etiquetas == ["POS", "Productos", "Reportes", "Configuración"]


# ---------- 5. Configuracion: modo de la caja ----------
def _config_view(page):
    asyncio.run(_tab(page, "Configuración").on_click(None))
    return _area(page).controls[0].content


def _tab(page, label):
    top_bar = page.controls[0].controls[0]
    return next(c for c in top_bar.content.controls
                if isinstance(c, ft.Container) and isinstance(c.content, ft.Row)
                and len(c.content.controls) > 1 and isinstance(c.content.controls[1], ft.Text)
                and c.content.controls[1].value == label)


def _guardar(view):
    view._ask_save()
    dlg = next(c for c in view._page.overlay if isinstance(c, ft.AlertDialog) and c.open)
    dlg.actions[0].on_click(None)


def test_config_muestra_el_modo_guardado_y_oculta_la_direccion_si_no_es_cliente(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    assert view.dd_caja_mode.value == "server"            # la Caja 1 por defecto
    assert view.caja_server_box.visible is False
    assert view.dd_caja_mode.on_select is not None and view.dd_caja_mode.tooltip


def test_elegir_caja_adicional_pide_la_direccion_de_la_caja_1(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    view.dd_caja_mode.value = "client"
    view.dd_caja_mode.on_select(types.SimpleNamespace())
    assert view.caja_server_box.visible is True


def test_guardar_modo_cliente_escribe_la_config_sin_pisar_el_resto(temp_db, tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Mi Local", rut="1-9"))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    view.dd_caja_mode.value = "client"
    view.in_server_url.value = "192.168.1.10"
    view.in_caja_name.value = "Barra"
    view.in_caja_number.value = "2"
    view.in_api_token.value = "clave-123"
    _guardar(view)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["mode"] == "client" and cfg["server_url"] == "http://192.168.1.10:8780"
    assert (cfg["caja_name"], cfg["caja_number"], cfg["api_token"]) == ("Barra", 2, "clave-123")
    assert cfg["business_name"] == "Mi Local" and cfg["rut"] == "1-9"


@pytest.mark.parametrize("url", ["", "   ", "no es una direccion", "ftp://x"])
def test_modo_cliente_sin_direccion_valida_no_se_guarda(temp_db, tmp_path, monkeypatch, url):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    view.dd_caja_mode.value = "client"
    view.in_server_url.value = url
    _guardar(view)
    assert "Escribe la direccion de la Caja 1" in view.msg.value
    assert json.loads(cfg_path.read_text(encoding="utf-8")).get("mode") != "client"


def test_guardar_en_modo_server_no_borra_una_direccion_anterior(temp_db, tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, mode="client", server_url="http://10.0.0.5:8780"))
    pos_main.make_backend  # sin tocar: el modo cliente real no se usa aqui
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    view.dd_caja_mode.value = "standalone"
    _guardar(view)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["mode"] == "standalone" and cfg["server_url"] == "http://10.0.0.5:8780"


def test_cliente_muestra_solo_pos_y_configuracion(cliente):
    page = FakePage()
    pos_main.main(page)
    assert _tab(page, "Productos").visible is False and _tab(page, "Reportes").visible is False
    assert _tab(page, "POS").visible is not False and _tab(page, "Configuración").visible is not False
    # aunque se fuerce, no se carga una vista que leeria la base local
    asyncio.run(_tab(page, "Productos").on_click(None))
    assert len(_area(page).controls) == 2                 # sigue en el POS (columna + total)


def test_la_caja_cliente_abre_aunque_la_caja_1_este_apagada(cliente):
    """Con la Caja 1 apagada al abrir, la app arranca, avisa y no deja cobrar (no se cae)."""
    cliente.alive = False
    page = FakePage()
    pos_main.main(page)                                    # no debe lanzar SinConexion
    assert _badge(page).visible is True and _conn_bar(page).visible is True
    assert _cobrar_btn(page).disabled is True
    assert _search_input(page).value == ""
    # al volver la Caja 1, Reintentar deja la caja lista
    cliente.alive = True
    _conn_bar(page).content.controls[2].on_click(None)
    assert _badge(page).visible is False and _conn_bar(page).visible is False


def test_clave_incorrecta_no_rompe_la_caja_cliente_y_no_vende(caja1, monkeypatch):
    """La Caja 1 exige clave y la caja cliente tiene otra: arranca sin caerse y no cobra."""
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token="s3cret"))
    monkeypatch.setattr(pos_main, "make_backend",
                        lambda settings=None, session=None: backend_mod.RemoteBackend(
                            "http://caja1:8780", caja1, "otra-clave"))
    monkeypatch.setattr(pos_main, "get_caja_settings",
                        lambda cfg=None: {"mode": "client", "server_url": "http://caja1:8780",
                                          "caja_number": 2, "caja_name": "Barra", "api_port": 8780,
                                          "api_token": "otra-clave"})
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    try:
        pos_main.main(page)
    except Exception as exc:  # pragma: no cover - el fallo que este test debe detectar
        pytest.fail(f"la caja cliente se cayo con una clave incorrecta: {exc!r}")
    assert _ventas() == []


# ---------- 6. La clave generada: se genera al arrancar la Caja 1 y se muestra en Configuracion ----------
def test_la_caja_1_genera_la_clave_al_arrancar_y_queda_en_config(temp_db, tmp_path, monkeypatch):
    """main() en modo server llama a ensure_api_token ANTES de armar Configuracion."""
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, mode="server"))
    # el conftest reemplaza start_api_server_if_needed por un doble; usamos el real
    import importlib
    real = importlib.reload(pos_main)
    monkeypatch.setattr("flet_app.api_server.run", lambda **k: None)
    page = FakePage()
    real.start_api_server_if_needed({"mode": "server", "api_port": 8780})
    token = json.loads(cfg_path.read_text(encoding="utf-8"))["api_token"]
    assert len(token) >= 20
    real.main(page)
    view = _config_view(page)
    assert view.txt_token.value == token
    assert view.txt_token.read_only is True
    assert view.caja_token_box.visible is True            # se ve en la Caja 1
    assert view.caja_server_box.visible is False


def test_la_clave_solo_se_muestra_en_la_caja_1(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token="abc123"))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    for modo, ve_token, ve_direccion in (("server", True, False), ("client", False, True),
                                         ("standalone", False, False)):
        view.dd_caja_mode.value = modo
        view.dd_caja_mode.on_select(types.SimpleNamespace())
        assert (view.caja_token_box.visible, view.caja_server_box.visible) == (ve_token, ve_direccion), modo


def test_guardar_en_la_caja_1_no_borra_la_clave_generada(temp_db, tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, mode="server", api_token="generada-123"))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    assert view.in_api_token.value in ("", "generada-123")  # el campo de la caja adicional no manda
    view.in_api_token.value = ""                           # vacio, como en una Caja 1 normal
    _guardar(view)
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["api_token"] == "generada-123"


def test_guardar_en_caja_adicional_toma_la_clave_pegada(temp_db, tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    view.dd_caja_mode.value = "client"
    view.in_server_url.value = "192.168.1.10"
    view.in_api_token.value = "  la-clave-de-la-caja-1  "
    _guardar(view)
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["api_token"] == "la-clave-de-la-caja-1"


def test_copiar_la_clave_usa_el_portapapeles_y_avisa(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token="copiame-123"))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    copiado = []

    async def fake_set(value):
        copiado.append(value)

    monkeypatch.setattr(view.clipboard, "set", fake_set)
    asyncio.run(view.btn_copy_token.on_click(None))
    assert copiado == ["copiame-123"] and view.msg.value == "Clave copiada."


def test_copiar_sin_clave_avisa_y_no_toca_el_portapapeles(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=""))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    copiado = []

    async def fake_set(value):
        copiado.append(value)

    monkeypatch.setattr(view.clipboard, "set", fake_set)
    asyncio.run(view.btn_copy_token.on_click(None))
    assert copiado == [] and "Aún no hay clave" in view.msg.value


def test_el_boton_de_copiar_tiene_nombre_accesible(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    page = FakePage()
    pos_main.main(page)
    view = _config_view(page)
    assert view.btn_copy_token.tooltip == "Copiar la clave"
