"""Tests de la Fase D: los 4 should-fix de la auditoria.

1. El nombre propio del producto comun (display_name) llega a sale_items y al comprobante.
2. La ganancia queda congelada al cobrar: cambiar el costo despues no altera ventas pasadas.
3. Respaldo de productos en utf-8 (round-trip exacto) y lectura de respaldos antiguos latin-1.
4. El buscador sin conexion dice la verdad en vez de "Sin resultados".
"""

import types

import requests

from core import config as core_config
from core import db_manager
from core import product_backup_service as bs
from core import product_service as ps
from core import report_service as rs
from core import sales_service as ss
from core import ticket_service as ts
from flet_app import backend as backend_mod
from flet_app import main as pos_main


TOKEN = "clave-shouldfix"


def _hoy():
    from datetime import date
    return date.today().isoformat()


def _cobrar(tid):
    ts.set_pay_method(tid, "efectivo")
    return ss.cobrar_ticket(tid)[0]


def _ganancias():
    with db_manager.get_conn() as con:
        return [r[0] for r in con.execute("SELECT gain_per_unit FROM sale_items ORDER BY id")]


# ---------- 1. display_name en sale_items y en items_de_venta ----------
def test_migracion_agrega_display_name_a_sale_items(temp_db):
    with db_manager.get_conn() as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(sale_items)")]
    assert "display_name" in cols


def test_la_migracion_es_idempotente(temp_db):
    db_manager.migrate_sale_items_add_display_name_if_missing()   # segunda vez: no falla
    db_manager.bootstrap()                                         # bootstrap completo otra vez
    with db_manager.get_conn() as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(sale_items)")]
    assert cols.count("display_name") == 1


def test_producto_comun_vendido_con_nombre_propio_llega_al_comprobante(temp_db):
    tid = ts.create_ticket()
    ts.add_common_item(tid, "Vaso de schop", qty=1, unit_price=3000, gain_per_unit=1000)
    sid = _cobrar(tid)

    with db_manager.get_conn() as con:
        dn = con.execute("SELECT display_name FROM sale_items WHERE sale_id=?", (sid,)).fetchone()[0]
    assert dn == "Vaso de schop (Producto común)"

    nombre = ss.items_de_venta(sid)[0]["product_name"]
    assert nombre == "Vaso de schop (Producto común)"
    assert nombre != "Producto común"


def test_producto_regular_sigue_con_su_nombre_de_catalogo(temp_db):
    pid = ps.create_product("Rubia IPA", 2500, 1000, stock=10)
    tid = ts.create_ticket()
    ts.add_item(tid, pid, qty=1, unit_price=2500)
    sid = _cobrar(tid)

    assert ss.items_de_venta(sid)[0]["product_name"] == "Rubia IPA"


# ---------- 2. Ganancia congelada al cobrar ----------
def test_ganancia_congelada_y_venta_nueva_usa_el_costo_nuevo(temp_db):
    pid = ps.create_product("Lager", 1500, purchase_price=1000, stock=50)
    hoy = _hoy()

    tid = ts.create_ticket()
    ts.add_item(tid, pid, qty=2, unit_price=1500)
    _cobrar(tid)
    assert _ganancias() == [500]                       # 1500 - 1000, no el 0 del ticket
    assert rs.summary(hoy, hoy)["profit"] == 1000      # 2 unidades * 500

    ps.update_product(pid, purchase_price=1300)
    assert rs.summary(hoy, hoy)["profit"] == 1000      # la venta pasada sigue en 500/u, no 200

    tid2 = ts.create_ticket()
    ts.add_item(tid2, pid, qty=1, unit_price=1500)
    _cobrar(tid2)
    assert _ganancias() == [500, 200]                  # la venta nueva si usa el costo nuevo
    assert rs.summary(hoy, hoy)["profit"] == 1200      # 1000 + 200


def test_producto_comun_conserva_la_ganancia_que_trae_el_ticket(temp_db):
    tid = ts.create_ticket()
    ts.add_common_item(tid, "Servicio", qty=2, unit_price=1000, gain_per_unit=400)
    _cobrar(tid)

    assert _ganancias() == [400]
    assert rs.summary(_hoy(), _hoy())["profit"] == 800


# ---------- 3. Respaldo CSV en utf-8 ----------
NOMBRE_RARO = "Cerveza 🍺 € ñandú"


def test_csv_round_trip_exacto_con_emoji_euro_y_enie(temp_db, tmp_path):
    pid = ps.create_product(NOMBRE_RARO, 3000, 1200, barcode="E1", stock=5, min_stock=2)
    path = tmp_path / "respaldo.csv"

    bs.export_products_csv(str(path))
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")             # utf-8 con BOM
    assert NOMBRE_RARO in path.read_text(encoding="utf-8-sig")

    # Se pisa el nombre y se reimporta: el codigo de barras lo encuentra y lo restaura exacto.
    ps.update_product(pid, name="Nombre pisado")
    res = bs.import_products_csv(str(path))
    assert res == {"created": 0, "updated": res["updated"], "skipped": 0}
    p = ps.get_product(pid)
    assert p["name"] == NOMBRE_RARO
    assert (p["sale_price"], p["purchase_price"], p["stock"], p["min_stock"]) == (3000, 1200, 5, 2)


def test_csv_antiguo_escrito_a_mano_en_latin1_se_importa(temp_db, tmp_path):
    path = tmp_path / "respaldo_viejo.csv"
    texto = ("Nombre;PrecioVenta;PrecioCompra;CodigoBarra;Stock;StockMinimo\r\n"
             "Caña de azúcar;1000;500;L1;10;2\r\n"
             "Cerveza Ñandú;2500;1000;L2;4;1\r\n")
    path.write_bytes(texto.encode("latin-1"))
    # Sanidad del caso: esos bytes NO son utf-8 valido (asi se fuerza el reintento latin-1).
    try:
        path.read_bytes().decode("utf-8")
        raise AssertionError("el archivo de prueba deberia ser latin-1 invalido como utf-8")
    except UnicodeDecodeError:
        pass

    res = bs.import_products_csv(str(path))
    assert res["created"] == 2 and res["skipped"] == 0
    assert ps.find_product_by_exact_code_or_name("L1")["name"] == "Caña de azúcar"
    assert ps.find_product_by_exact_code_or_name("L2")["name"] == "Cerveza Ñandú"


# ---------- 4. Buscador sin conexion (a nivel app, patron de test_modo_cliente) ----------
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


def _search_card(page):
    area = page.controls[0].controls[1].controls[1].content
    return area.controls[0].controls[0].content          # Column([Row([search]), info, empty, grid])


def _buscar(page, texto):
    search = _search_card(page).controls[0].controls[0]
    search.value = texto
    search.on_change(None)
    return _search_card(page).controls[2]                 # grid_empty


class SesionCaida:
    """La Caja 1 apagada: toda llamada falla como sin red."""

    def request(self, *a, **k):
        raise requests.ConnectionError("Caja 1 apagada")


def test_cliente_sin_conexion_el_buscador_dice_sin_conexion(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(pos_main, "make_backend",
                        lambda settings=None, session=None: backend_mod.RemoteBackend(
                            "http://caja1:8780", SesionCaida(), TOKEN))
    monkeypatch.setattr(pos_main, "get_caja_settings",
                        lambda cfg=None: {"mode": "client", "server_url": "http://caja1:8780",
                                          "caja_number": 2, "caja_name": "Barra", "api_port": 8780,
                                          "api_token": TOKEN})
    page = FakePage()
    pos_main.main(page)                                   # abre sin conexion, no se cae

    vacio = _buscar(page, "rubia")
    assert vacio.visible is True
    assert vacio.value == "Sin conexión con la Caja 1."


def test_local_sin_coincidencias_sigue_diciendo_sin_resultados(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, mode="standalone"))
    ps.create_product("Rubia", 1500, barcode="7801", stock=10)
    page = FakePage()
    pos_main.main(page)

    vacio = _buscar(page, "xyz-no-existe")
    assert vacio.visible is True
    assert vacio.value == 'Sin resultados para "xyz-no-existe".'
