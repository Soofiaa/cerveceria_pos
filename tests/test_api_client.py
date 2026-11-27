"""Tests del cliente de la API (flet_app/api_client.py) y de multicaja.py.

El cliente se prueba contra la API REAL de la Caja 1 (flet_app/api_server.py)
sin abrir ningun puerto: una sesion de requests que despacha al cliente de
pruebas de Flask. La base es la temporal (temp_db).
"""

import pytest
import requests

from core import config as core_config
from core import product_service as ps
from core import ticket_service as ts
from flet_app import multicaja
from flet_app.api_client import ApiClient, ApiError, SinConexion
from flet_app.api_server import create_app


TOKEN = "clave-de-prueba"


class FlaskSession:
    """Sesion de requests falsa: llama a la app Flask en memoria, no a la red."""

    def __init__(self, flask_client):
        self._c = flask_client

    def request(self, method, url, params=None, json=None, timeout=None, headers=None):
        path = "/" + url.split("/", 3)[3]
        r = self._c.open(path, method=method, query_string=params, json=json, headers=headers)

        class Resp:
            status_code = r.status_code

            @staticmethod
            def json():
                data = r.get_json(silent=True)
                if data is None and r.mimetype != "application/json":
                    raise ValueError("no json")
                return data

        return Resp


class DeadSession:
    """Caja 1 apagada: toda llamada falla como si no hubiera red."""

    def __init__(self, exc=None):
        self.exc = exc or requests.ConnectionError("connection refused")
        self.calls = 0

    def request(self, *a, **k):
        self.calls += 1
        raise self.exc


@pytest.fixture
def api(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=TOKEN))
    return ApiClient("http://caja1:8780", FlaskSession(create_app().test_client()), token=TOKEN)


# ---------- Flujo completo por la API ----------
def test_flujo_de_venta_completo_desde_el_cliente(api):
    pid = ps.create_product("Rubia", 1500, stock=10, barcode="7801")
    assert api.is_alive() is True
    assert [p["name"] for p in api.list_products("rub")] == ["Rubia"]
    assert api.find_product_by_exact_code_or_name("7801")["id"] == pid

    tid = api.create_ticket("Mesa 1")
    assert api.get_ticket(tid)["name"] == "Mesa 1"
    api.add_item(tid, pid, 1, 1)                    # unit_price se ignora
    item = api.list_items(tid)[0]
    assert item["unit_price"] == 1500
    api.update_item_qty(item["id"], 3)
    assert api.get_item(item["id"])["qty"] == 3
    assert api.stock_warnings_for_ticket(tid) == []

    sale_id, warnings = api.cobrar(tid, "efectivo")
    assert sale_id == 1 and warnings == []
    assert ps.get_product(pid)["stock"] == 7        # lo decidio el servidor
    data = api.receipt(sale_id)
    assert data["total"] == 4500 and data["items"][0]["name"] == "Rubia"


def test_los_ids_de_venta_son_los_del_servidor_aunque_haya_dos_cajas(api, temp_db):
    pid = ps.create_product("Rubia", 1500, stock=50)
    otra_caja = ApiClient("http://caja1:8780", api._session, token=TOKEN)   # segunda caja, misma Caja 1
    ids = []
    for caja in (api, otra_caja, api):
        tid = caja.create_ticket()
        caja.add_item(tid, pid, 1, 0)
        ids.append(caja.cobrar(tid, "efectivo")[0])
    assert ids == [1, 2, 3]
    assert ps.get_product(pid)["stock"] == 47


def test_dos_cajas_ven_los_mismos_tickets_y_productos(api):
    otra = ApiClient("http://caja1:8780", api._session, token=TOKEN)
    ps.create_product("Negra", 1800, barcode="7802")
    tid = api.create_ticket("Mesa 7")
    assert [t["name"] for t in otra.list_open_tickets()] == ["Mesa 7"]
    assert [p["name"] for p in otra.list_products("neg")] == ["Negra"]
    assert otra.get_ticket(tid)["id"] == tid


# ---------- Valores vacios y rechazos ----------
def test_objetos_inexistentes_devuelven_none_o_vacio(api):
    assert api.get_product(999) is None
    assert api.get_ticket(999) is None
    assert api.get_item(999) is None
    assert api.list_items(999) == []
    assert api.find_product_by_exact_code_or_name("zzz") is None
    api.delete_ticket(999)            # ya no existe: no es error
    api.remove_item(999)
    api.update_item_qty(999, 2)


def test_rechazo_del_servidor_es_apierror_con_mensaje(api):
    tid = api.create_ticket()
    with pytest.raises(ApiError) as exc:
        api.cobrar(tid, "efectivo")   # ticket vacio
    assert exc.value.status == 409 and "ítems" in str(exc.value)
    with pytest.raises(ApiError) as exc:
        api.cobrar(tid, "cheque")
    assert exc.value.status == 400
    with pytest.raises(ApiError) as exc:
        api.add_product(tid, 9999)
    assert exc.value.status == 404


def test_cobrar_dos_veces_la_segunda_es_rechazada(api):
    pid = ps.create_product("Rubia", 1500, stock=10)
    tid = api.create_ticket()
    api.add_item(tid, pid, 1, 0)
    api.cobrar(tid, "efectivo")
    with pytest.raises(ApiError) as exc:
        api.cobrar(tid, "efectivo")
    assert exc.value.status == 404 and ps.get_product(pid)["stock"] == 9


# ---------- Sin conexion ----------
@pytest.mark.parametrize(
    "exc",
    [requests.ConnectionError("x"), requests.Timeout("x"), requests.exceptions.ConnectTimeout("x")],
)
def test_sin_conexion_lanza_sinconexion_en_cada_operacion(exc):
    api = ApiClient("http://caja1:8780", DeadSession(exc))
    for call in (
        lambda: api.health(), lambda: api.list_products("x"), lambda: api.list_open_tickets(),
        lambda: api.get_ticket(1), lambda: api.create_ticket("x"), lambda: api.add_product(1, 1),
        lambda: api.cobrar(1, "efectivo"), lambda: api.receipt(1), lambda: api.stock_warnings_for_ticket(1),
    ):
        with pytest.raises(SinConexion, match="sin conexión con la Caja 1"):
            call()


def test_is_alive_es_falso_sin_conexion_y_no_lanza():
    assert ApiClient("http://caja1:8780", DeadSession()).is_alive() is False


def test_respuesta_que_no_es_json_o_error_500_cuenta_como_sin_conexion(temp_db):
    class Html:
        status_code = 200

        @staticmethod
        def json():
            raise ValueError("no json")

    class Boom:
        status_code = 500

        @staticmethod
        def json():
            return {"error": "Error interno del servidor."}

    class Fixed:
        def __init__(self, resp):
            self.resp = resp

        def request(self, *a, **k):
            return self.resp

    with pytest.raises(SinConexion, match="no responde como la Caja 1"):
        ApiClient("http://x:1", Fixed(Html)).health()
    with pytest.raises(SinConexion, match="error interno"):
        ApiClient("http://x:1", Fixed(Boom)).health()


def test_timeouts_cortos_para_no_colgar_la_caja():
    from flet_app import api_client

    assert api_client.CONNECT_TIMEOUT <= 3 and api_client.READ_TIMEOUT <= 10


# ---------- multicaja: modo y config ----------
def test_modo_por_defecto_es_server_y_el_numero_de_caja_1():
    s = multicaja.get_caja_settings({})
    assert (s["mode"], s["caja_number"], s["caja_name"], s["server_url"]) == ("server", 1, "Caja 1", "")


@pytest.mark.parametrize("mode", ["standalone", "server", "client"])
def test_los_tres_modos_se_guardan_y_se_leen(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    multicaja.save_caja_settings(mode=mode, server_url="192.168.1.10", caja_number=2, caja_name="Barra")
    s = multicaja.get_caja_settings()
    assert s["mode"] == mode and s["server_url"] == "http://192.168.1.10:8780"
    assert (s["caja_number"], s["caja_name"]) == (2, "Barra")


def test_guardar_modo_no_pisa_el_resto_de_la_config(tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Mi Local", theme="oscuro"))
    multicaja.save_caja_settings(mode="client", server_url="10.0.0.5")
    cfg = core_config.load_config()
    assert cfg["business_name"] == "Mi Local" and cfg["theme"] == "oscuro" and cfg["mode"] == "client"


@pytest.mark.parametrize(
    "url,expected",
    [("192.168.1.10", "http://192.168.1.10:8780"), ("http://10.0.0.2:9000", "http://10.0.0.2:9000"),
     ("caja1.local", "http://caja1.local:8780"), ("http://192.168.1.10:8780/", "http://192.168.1.10:8780"),
     ("", ""), ("   ", ""), (None, ""), ("ftp://x", ""), ("not a url", ""), ("10.0.0.1:99999", "")],
)
def test_normalizar_direccion_del_servidor(url, expected):
    assert multicaja.normalize_url(url) == expected


def test_valores_raros_en_config_caen_a_los_defaults():
    s = multicaja.get_caja_settings({"mode": "otro", "caja_number": -4, "caja_name": None, "server_url": 5})
    assert (s["mode"], s["caja_number"], s["caja_name"]) == ("server", 1, "Caja 1")


def test_modo_invalido_al_guardar_se_rechaza(tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    with pytest.raises(ValueError):
        multicaja.save_caja_settings(mode="nube")
    assert multicaja.validate_client_url("") is not None
    assert multicaja.validate_client_url("192.168.1.10") is None


def test_standalone_no_necesita_servidor_ni_url():
    s = multicaja.get_caja_settings({"mode": "standalone"})
    assert s["mode"] == "standalone" and s["server_url"] == ""
