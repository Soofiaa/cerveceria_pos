"""Concurrencia multi-caja: Fase 5.1c.

Cubre:
- add_item concurrente (dos hilos, mismo ticket, mismo producto): qty final
  es la suma exacta, sin unidades perdidas.
- cobrar_ticket con expected_total: correcto pasa; distinto -> ValueError,
  no se crea venta y el ticket queda intacto.
- doble cobro simultáneo mismo ticket, pay_method distintos: una sola venta,
  y su pay_method es el de la llamada que cobro.
- adjust_item_qty concurrente (+1 dos hilos suma todo; ajuste a 0 elimina
  la linea).
- Via API (test_client): POST /charge con expected_total que no calza -> 409
  y ninguna venta; POST /adjust suma y resta correctamente.
- Modo cliente (app): al arrancar habiendo tickets abiertos en el servidor, la
  app crea un ticket nuevo en vez de adoptar uno; y tras un cobro, el ticket
  activo es nuevo aunque exista otro ticket vacio.
"""

import asyncio
import json
import threading
import types

import flet as ft
import pytest
import requests

from core import config as core_config
from core import db_manager
from core import product_service as ps
from core import sales_service as ss
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
        self.window = types.SimpleNamespace(width=1280, height=720, min_width=1000,
                                            min_height=650, maximized=False)
        self.updates = 0

    def add(self, *c):
        self.controls.extend(c)

    def update(self):
        self.updates += 1


class Caja1Session:
    """requests.Session falsa: despacha a la API de la Caja 1 (Flask en memoria)."""

    def __init__(self, flask_client):
        self._c = flask_client
        self.alive = True
        self.calls = []

    def request(self, method, url, params=None, json=None, timeout=None, headers=None):
        if not self.alive:
            raise requests.ConnectionError("Caja 1 apagada")
        path = "/" + url.split("/", 3)[3]
        self.calls.append((method, path))
        r = self._c.open(path, method=method, query_string=params, json=json,
                         headers=headers)

        class Resp:
            status_code = r.status_code

            @staticmethod
            def json():
                return r.get_json(silent=True)

        return Resp


@pytest.fixture
def caja1(temp_db, tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG,
                                 business_name="Cervecería Ñandú", rut="76.1-7",
                                 api_token=TOKEN))
    return Caja1Session(create_app().test_client())


@pytest.fixture
def cliente_app(caja1, monkeypatch):
    """Una caja en modo cliente conectada a la Caja 1 falsa."""
    monkeypatch.setattr(pos_main, "make_backend",
                        lambda settings=None, session=None: backend_mod.RemoteBackend(
                            "http://caja1:8780", caja1, TOKEN))
    monkeypatch.setattr(pos_main, "get_caja_settings",
                        lambda cfg=None: {"mode": "client", "server_url": "http://caja1:8780",
                                          "caja_number": 2, "caja_name": "Barra",
                                          "api_port": 8780, "api_token": TOKEN})
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    return caja1


def _auth_headers():
    return {"X-Caja-Token": TOKEN}


def _ventas():
    with db_manager.get_conn() as con:
        return con.execute("select id from sales").fetchall()


# ---------- 1. add_item concurrente ----------
def _agregar_a_la_vez(ticket_id, pid, precio, por_hilo=3, hilos=2):
    barrera = threading.Barrier(hilos)
    errores = []
    candado = threading.Lock()

    def add(tid, p, p2):
        barrera.wait()
        try:
            ts.add_item(tid, p, por_hilo, p2)
        except Exception as exc:  # pragma: no cover
            with candado:
                errores.append((type(exc).__name__, str(exc)))

    hilos_lista = [threading.Thread(target=add, args=(ticket_id, pid, precio))
                   for _ in range(hilos)]
    for h in hilos_lista:
        h.start()
    for h in hilos_lista:
        h.join(timeout=30)
    assert not any(h.is_alive() for h in hilos_lista), "un hilo quedo colgado"
    assert not errores, f"errores inesperados: {errores}"


def test_add_item_concurrente_mismo_ticket_sin_unidades_perdidas(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=1000, barcode="R1")
    tid = ts.create_ticket("Mesa")
    ts.add_item(tid, pid, 1, 1500)

    _agregar_a_la_vez(tid, pid, 1500, por_hilo=5, hilos=4)

    items = ts.list_items(tid)
    assert len(items) == 1
    assert items[0]["qty"] == 1 + 4 * 5


def test_add_item_concurrente_mismo_producto_diferente_precio_crea_lineas(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=1000, barcode="R1")
    tid = ts.create_ticket("Mesa")

    def add(precio):
        ts.add_item(tid, pid, 2, precio)

    hilos_lista = [threading.Thread(target=add, args=(p,)) for p in (1500, 2000)]
    for h in hilos_lista:
        h.start()
    for h in hilos_lista:
        h.join(timeout=30)

    items = ts.list_items(tid)
    assert len(items) == 2
    assert sum(i["qty"] for i in items) == 4


# ---------- 2. cobrar_ticket con expected_total ----------
def test_cobrar_con_expected_total_correcto_pasa(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = ts.create_ticket("Mesa")
    ts.add_item(tid, pid, 3, 1500)
    sale_id, _ = ss.cobrar_ticket(tid, pay_method="efectivo", expected_total=4500)
    assert sale_id == 1
    assert _ventas() == [(1,)]
    assert ts.get_ticket(tid) is None


def test_cobrar_con_expected_total_distinto_valueerror_y_ticket_intacto(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = ts.create_ticket("Mesa")
    ts.add_item(tid, pid, 3, 1500)  # total 4500
    ventas_antes = _ventas()
    with pytest.raises(ValueError, match="El ticket cambió, revisa el total."):
        ss.cobrar_ticket(tid, pay_method="efectivo", expected_total=4501)
    assert _ventas() == ventas_antes
    ticket = ts.get_ticket(tid)
    assert ticket is not None
    assert ps.get_product(pid)["stock"] == 100


# ---------- 3. doble cobro simultaneo mismo ticket ----------
def test_doble_cobro_simultaneo_pay_method_distinto_una_sola_venta(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = ts.create_ticket("Mesa")
    ts.add_item(tid, pid, 2, 1500)

    jobs = [(tid, "efectivo"), (tid, "debito")]
    barrera = threading.Barrier(len(jobs))
    resultados = []
    candado = threading.Lock()

    def cobrar(tid, metodo):
        barrera.wait()
        try:
            sale_id, _ = ss.cobrar_ticket(tid, pay_method=metodo)
            with candado:
                resultados.append(("ok", sale_id, metodo))
        except ValueError as exc:
            with candado:
                resultados.append(("error", str(exc), metodo))

    hilos_lista = [threading.Thread(target=cobrar, args=j) for j in jobs]
    for h in hilos_lista:
        h.start()
    for h in hilos_lista:
        h.join(timeout=30)
    assert not any(h.is_alive() for h in hilos_lista)

    oks = [r for r in resultados if r[0] == "ok"]
    assert len(oks) == 1
    assert _ventas() == [(1,)]
    # Verificar que el pay_method en la base coincida con el ganador
    metodo_ganador = oks[0][2]
    with db_manager.get_conn() as con:
        venta = con.execute("SELECT pay_method FROM sales WHERE id=?", (1,)).fetchone()
        assert venta[0] == metodo_ganador
    assert ps.get_product(pid)["stock"] == 98
    # Verificar que el medio de pago guardado es el correcto
    with db_manager.get_conn() as con:
        metodo_guardado = con.execute("SELECT pay_method FROM sales WHERE id=1").fetchone()[0]
    assert metodo_guardado == oks[0][2]


# ---------- 4. adjust_item_qty concurrente ----------
def test_adjust_item_qty_concurrente_suma_todo(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=1000, barcode="R1")
    tid = ts.create_ticket("Mesa")
    ts.add_item(tid, pid, 10, 1500)
    item = ts.list_items(tid)[0]

    def ajustar():
        ts.adjust_item_qty(item["id"], 1)

    hilos_lista = [threading.Thread(target=ajustar) for _ in range(6)]
    for h in hilos_lista:
        h.start()
    for h in hilos_lista:
        h.join(timeout=30)

    item = ts.get_item(item["id"])
    assert item["qty"] == 16


def test_adjust_item_qty_a_0_elimina_la_linea(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = ts.create_ticket("Mesa")
    ts.add_item(tid, pid, 3, 1500)
    item = ts.list_items(tid)[0]

    def restar():
        ts.adjust_item_qty(item["id"], -1)

    hilos_lista = [threading.Thread(target=restar) for _ in range(3)]
    for h in hilos_lista:
        h.start()
    for h in hilos_lista:
        h.join(timeout=30)

    assert ts.get_item(item["id"]) is None
    assert ts.list_items(tid) == []


# ---------- 5. Vía API ----------
def test_api_charge_expected_total_no_calza_409_y_sin_venta(caja1):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = caja1._c.open("/api/tickets", method="POST", json={"name": "Mesa"},
                        headers=_auth_headers()).get_json()["id"]
    caja1._c.open(f"/api/tickets/{tid}/items", method="POST",
                  json={"product_id": pid, "qty": 3}, headers=_auth_headers())

    r = caja1._c.open(f"/api/tickets/{tid}/charge", method="POST",
                      json={"pay_method": "efectivo", "expected_total": 4501},
                      headers=_auth_headers())
    assert r.status_code == 409
    assert _ventas() == []
    assert caja1._c.get(f"/api/tickets/{tid}", headers=_auth_headers()).status_code == 200


def test_api_charge_expected_total_correcto_crea_venta(caja1):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = caja1._c.open("/api/tickets", method="POST", json={"name": "Mesa"},
                        headers=_auth_headers()).get_json()["id"]
    caja1._c.open(f"/api/tickets/{tid}/items", method="POST",
                  json={"product_id": pid, "qty": 3}, headers=_auth_headers())

    r = caja1._c.open(f"/api/tickets/{tid}/charge", method="POST",
                      json={"pay_method": "efectivo", "expected_total": 4500},
                      headers=_auth_headers())
    assert r.status_code == 201
    assert _ventas() == [(1,)]
    r = caja1._c.get(f"/api/tickets/{tid}", headers=_auth_headers())
    assert r.status_code == 404


def test_api_adjust_suma_y_resta(caja1):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = caja1._c.open("/api/tickets", method="POST", json={"name": "Mesa"},
                        headers=_auth_headers()).get_json()["id"]
    caja1._c.open(f"/api/tickets/{tid}/items", method="POST",
                  json={"product_id": pid, "qty": 5}, headers=_auth_headers())
    item_id = caja1._c.get(f"/api/tickets/{tid}/items",
                           headers=_auth_headers()).get_json()[0]["id"]

    r = caja1._c.open(f"/api/items/{item_id}/adjust", method="POST",
                      json={"delta": 2}, headers=_auth_headers())
    assert r.status_code == 200
    assert r.get_json()["new_qty"] == 7

    r = caja1._c.open(f"/api/items/{item_id}/adjust", method="POST",
                      json={"delta": -7}, headers=_auth_headers())
    assert r.status_code == 200
    assert r.get_json()["new_qty"] == 0
    r = caja1._c.get(f"/api/items/{item_id}", headers=_auth_headers())
    assert r.status_code == 404


def test_api_adjust_delta_invalido_400(caja1):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = caja1._c.open("/api/tickets", method="POST", json={"name": "Mesa"},
                        headers=_auth_headers()).get_json()["id"]
    caja1._c.open(f"/api/tickets/{tid}/items", method="POST",
                  json={"product_id": pid, "qty": 5}, headers=_auth_headers())
    item_id = caja1._c.get(f"/api/tickets/{tid}/items",
                           headers=_auth_headers()).get_json()[0]["id"]

    r = caja1._c.open(f"/api/items/{item_id}/adjust", method="POST",
                      json={"delta": 0}, headers=_auth_headers())
    assert r.status_code == 400
    r = caja1._c.open(f"/api/items/{item_id}/adjust", method="POST",
                      json={"delta": "no"}, headers=_auth_headers())
    assert r.status_code == 400
    r = caja1._c.open(f"/api/items/{item_id}/adjust", method="POST",
                      json={}, headers=_auth_headers())
    assert r.status_code == 400


def test_api_adjust_item_inexistente_404(caja1):
    r = caja1._c.open("/api/items/99999/adjust", method="POST",
                      json={"delta": 1}, headers=_auth_headers())
    assert r.status_code == 404


# ---------- 6. Modo cliente: no adopta tickets abiertos ----------
def test_modo_cliente_al_arrancar_con_tickets_abiertos_no_adopta_ni_uno(temp_db, cliente_app):
    """Al arrancar habiendo tickets abiertos en el servidor, la app cliente
    crea uno nuevo en vez de adoptar el existente."""
    caja1_tid = cliente_app._c.open("/api/tickets", method="POST",
                                    json={"name": "Mesa 1"},
                                    headers=_auth_headers()).get_json()["id"]

    page = FakePage()
    pos_main.main(page)

    # El servidor tiene el ticket viejo (1) y el nuevo creado por la app (2)
    abiertos = cliente_app._c.open("/api/tickets", headers=_auth_headers()).get_json()
    assert len(abiertos) == 2
    # El ticket nuevo tiene id distinto al viejo de la Caja 1
    ids = [t["id"] for t in abiertos]
    assert caja1_tid in ids
    assert max(ids) > caja1_tid


def test_modo_cliente_tras_cobro_ticket_activo_es_nuevo_aunque_haya_vacio(temp_db, cliente_app):
    """Tras un cobro, el ticket activo es nuevo aunque exista otro ticket vacio
    (after_charge nunca reutiliza tickets vacíos)."""
    vacio_tid = cliente_app._c.open("/api/tickets", method="POST", json={"name": "Vacio"},
                                    headers=_auth_headers()).get_json()["id"]

    page = FakePage()
    pos_main.main(page)

    # Agregar producto mediante el buscador de la app (sobre el ticket nuevo creado al arrancar)
    search = page.controls[0].controls[1].controls[1].content.controls[0].controls[0].content.controls[0].controls[0]
    search.value = "7801"
    asyncio.run(search.on_submit(None))

    # Cobrar mediante el botón Cobrar de la app (dispara after_charge)
    summary = page.controls[0].controls[1].controls[1].content.controls[1].controls[0].content
    cobrar_btn = summary.controls[5]
    cobrar_btn.on_click(None)

    charge = [c for c in page.overlay if isinstance(c, ft.AlertDialog) and c.open][-1]
    recibido = next(c for c in charge.content.controls if isinstance(c, ft.TextField))
    recibido.value = "5000"
    recibido.on_change(None)
    asyncio.run(recibido.on_submit(None))

    abiertos_despues = cliente_app._c.open("/api/tickets", headers=_auth_headers()).get_json()
    ids_despues = [t["id"] for t in abiertos_despues]
    # Debe existir el ticket 'Vacio' original (1) y uno nuevo creado por after_charge (3),
    # el ticket activo (2) ya fue cobrado y cerrado.
    assert vacio_tid in ids_despues
    assert len(ids_despues) == 2
    # El ticket nuevo de after_charge debe tener un ID mayor que el vacio
    assert max(ids_despues) > vacio_tid

    # --- Limpieza para que otros tests no vean el backend cliente ---
@pytest.fixture(autouse=True)
def restaurar_estado_main():
    backend_original = pos_main.backend
    yield
    pos_main.backend = backend_original
    pos_main.apply_palette("lila")
