"""Tests de la API de la Caja 1 (flet_app/api_server.py).

Cliente de pruebas de Flask contra la base temporal (fixture temp_db): nunca
se toca ~/MiPOS. La config tambien se redirige a un archivo temporal.
"""

import json

import pytest

from core import config as core_config
from core import db_manager
from core import product_service as ps
from core import ticket_service as ts
from flet_app.api_server import create_app


TOKEN = "clave-de-prueba"


class ClienteConClave:
    """Cliente de pruebas de Flask que manda la clave de la Caja 1 en cada llamada.

    Como una caja real: la API ya no responde sin clave (ver los tests de la
    seccion "Clave compartida"). `sin_clave()` da el cliente sin cabecera.
    """

    def __init__(self, flask_client, token=TOKEN):
        self._c, self._token = flask_client, token

    def sin_clave(self):
        return self._c

    def _h(self, kw):
        headers = dict(kw.pop("headers", None) or {})
        if self._token is not None:
            headers.setdefault("X-Caja-Token", self._token)
        return headers

    def get(self, *a, **kw):
        return self._c.get(*a, headers=self._h(kw), **kw)

    def post(self, *a, **kw):
        return self._c.post(*a, headers=self._h(kw), **kw)

    def put(self, *a, **kw):
        return self._c.put(*a, headers=self._h(kw), **kw)

    def delete(self, *a, **kw):
        return self._c.delete(*a, headers=self._h(kw), **kw)


@pytest.fixture
def client(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=TOKEN))
    return ClienteConClave(create_app().test_client())


def _producto(name="Rubia", price=1500, stock=10, barcode="7801"):
    return ps.create_product(name, price, stock=stock, barcode=barcode)


def _ticket(client, name="Ticket 1"):
    r = client.post("/api/tickets", json={"name": name})
    assert r.status_code == 201
    return r.get_json()["id"]


# ---------- Estado y config ----------
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["api_version"] == 1 and body["business_name"]


def test_config_devuelve_datos_del_negocio_para_el_comprobante(client, tmp_path):
    cfg = dict(core_config.DEFAULT_CONFIG, business_name="Cervecería Ñandú", rut="76.1-7",
               address="Calle 1", phone=56912345678, ticket_prefix="Mesa", api_token=TOKEN)
    core_config.save_config(cfg)
    body = client.get("/api/config").get_json()
    assert body == {"business_name": "Cervecería Ñandú", "rut": "76.1-7", "address": "Calle 1",
                    "phone": "56912345678", "ticket_prefix": "Mesa"}


def test_ruta_inexistente_y_metodo_no_permitido_son_json(client):
    assert client.get("/api/nada").get_json() == {"error": "Ruta no encontrada."}
    assert client.delete("/api/health").status_code == 405


# ---------- Productos ----------
def test_listar_y_buscar_productos(client):
    _producto("Rubia", barcode="7801")
    _producto("Negra", barcode="7802")
    nombres = [p["name"] for p in client.get("/api/products").get_json()]
    assert "Rubia" in nombres and "Negra" in nombres
    assert [p["name"] for p in client.get("/api/products?q=neg").get_json()] == ["Negra"]


def test_producto_exacto_y_get(client):
    pid = _producto("Rubia", barcode="7801")
    assert client.get("/api/products/exact?q=7801").get_json()["id"] == pid
    assert client.get("/api/products/exact?q=zzz").get_json() is None
    assert client.get(f"/api/products/{pid}").get_json()["name"] == "Rubia"
    assert client.get("/api/products/9999").status_code == 404


# ---------- Tickets y lineas ----------
def test_crear_listar_y_borrar_ticket(client):
    tid = _ticket(client, "Mesa 4")
    assert [t["name"] for t in client.get("/api/tickets").get_json()] == ["Mesa 4"]
    assert client.get(f"/api/tickets/{tid}").get_json()["id"] == tid
    assert client.delete(f"/api/tickets/{tid}").status_code == 200
    assert client.get(f"/api/tickets/{tid}").status_code == 404
    assert client.delete(f"/api/tickets/{tid}").status_code == 404


def test_agregar_linea_usa_el_precio_del_servidor(client):
    pid = _producto("Rubia", price=1500)
    tid = _ticket(client)
    # Aunque la caja mande otro precio, el servidor usa el del producto.
    r = client.post(f"/api/tickets/{tid}/items", json={"product_id": pid, "qty": 2, "unit_price": 1})
    assert r.status_code == 201
    items = r.get_json()["items"]
    assert items[0]["unit_price"] == 1500 and items[0]["qty"] == 2
    assert r.get_json()["ticket"]["pending_total"] == 3000


def test_agregar_el_mismo_producto_acumula_cantidad(client):
    pid = _producto()
    tid = _ticket(client)
    client.post(f"/api/tickets/{tid}/items", json={"product_id": pid})
    r = client.post(f"/api/tickets/{tid}/items", json={"product_id": pid})
    assert len(r.get_json()["items"]) == 1 and r.get_json()["items"][0]["qty"] == 2


@pytest.mark.parametrize("body", [{}, {"product_id": "1"}, {"product_id": 0}, {"product_id": True},
                                  {"product_id": 1, "qty": 0}, {"product_id": 1, "qty": -3},
                                  {"product_id": 1, "qty": 1.5}])
def test_agregar_linea_con_datos_invalidos_da_400(client, body):
    tid = _ticket(client)
    assert client.post(f"/api/tickets/{tid}/items", json=body).status_code == 400


def test_agregar_linea_producto_o_ticket_inexistente_o_inactivo(client):
    pid = _producto()
    tid = _ticket(client)
    assert client.post(f"/api/tickets/{tid}/items", json={"product_id": 9999}).status_code == 404
    assert client.post("/api/tickets/9999/items", json={"product_id": pid}).status_code == 404
    ps.desactivar_producto(pid)
    assert client.post(f"/api/tickets/{tid}/items", json={"product_id": pid}).status_code == 404


def test_cambiar_cantidad_y_quitar_linea(client):
    pid = _producto()
    tid = _ticket(client)
    item = client.post(f"/api/tickets/{tid}/items", json={"product_id": pid}).get_json()["items"][0]
    r = client.put(f"/api/items/{item['id']}", json={"qty": 5})
    assert r.get_json()["items"][0]["qty"] == 5 and r.get_json()["ticket"]["pending_total"] == 7500
    assert client.put(f"/api/items/{item['id']}", json={"qty": "x"}).status_code == 400
    r = client.delete(f"/api/items/{item['id']}")
    assert r.get_json()["items"] == [] and r.get_json()["ticket"]["pending_total"] == 0
    assert client.delete(f"/api/items/{item['id']}").status_code == 404
    assert client.put("/api/items/9999", json={"qty": 1}).status_code == 404


def test_cantidad_cero_elimina_la_linea(client):
    pid = _producto()
    tid = _ticket(client)
    item = client.post(f"/api/tickets/{tid}/items", json={"product_id": pid}).get_json()["items"][0]
    assert client.put(f"/api/items/{item['id']}", json={"qty": 0}).get_json()["items"] == []


# ---------- Cobro ----------
def test_cobrar_descuenta_stock_y_devuelve_id_de_venta(client):
    pid = _producto(stock=10, price=1500)
    tid = _ticket(client)
    client.post(f"/api/tickets/{tid}/items", json={"product_id": pid, "qty": 3})
    r = client.post(f"/api/tickets/{tid}/charge", json={"pay_method": "efectivo"})
    assert r.status_code == 201
    assert r.get_json()["sale_id"] == 1 and r.get_json()["warnings"] == []
    assert ps.get_product(pid)["stock"] == 7            # el stock lo decide el servidor
    assert client.get(f"/api/tickets/{tid}").status_code == 404   # el ticket ya no esta abierto


def test_los_ids_de_venta_los_asigna_el_servidor_en_secuencia(client):
    pid = _producto(stock=100)
    ids = []
    for _ in range(3):
        tid = _ticket(client)
        client.post(f"/api/tickets/{tid}/items", json={"product_id": pid})
        ids.append(client.post(f"/api/tickets/{tid}/charge", json={"pay_method": "debito"}).get_json()["sale_id"])
    assert ids == [1, 2, 3]


def test_cobrar_con_stock_negativo_avisa_pero_vende(client):
    pid = _producto(stock=1)
    tid = _ticket(client)
    client.post(f"/api/tickets/{tid}/items", json={"product_id": pid, "qty": 3})
    pre = client.get(f"/api/tickets/{tid}/stock_warnings").get_json()
    assert pre[0]["stock_resultante"] == -2
    r = client.post(f"/api/tickets/{tid}/charge", json={"pay_method": "efectivo"})
    assert r.status_code == 201 and r.get_json()["warnings"][0]["product_name"] == "Rubia"


def test_cobrar_ticket_vacio_da_409(client):
    tid = _ticket(client)
    r = client.post(f"/api/tickets/{tid}/charge", json={"pay_method": "efectivo"})
    assert r.status_code == 409
    assert r.get_json()["error"] == "El ticket no tiene ítems."


@pytest.mark.parametrize("body", [{}, {"pay_method": "cheque"}, {"pay_method": None}])
def test_cobrar_con_medio_de_pago_invalido_da_400(client, body):
    pid = _producto()
    tid = _ticket(client)
    client.post(f"/api/tickets/{tid}/items", json={"product_id": pid})
    assert client.post(f"/api/tickets/{tid}/charge", json=body).status_code == 400
    assert ps.get_product(pid)["stock"] == 10            # no se cobro nada


def test_cobrar_dos_veces_el_mismo_ticket_solo_vende_una_vez(client):
    """Dos cajas cobrando el mismo ticket: la segunda recibe 404 y el stock baja una sola vez."""
    pid = _producto(stock=10)
    tid = _ticket(client)
    client.post(f"/api/tickets/{tid}/items", json={"product_id": pid, "qty": 2})
    assert client.post(f"/api/tickets/{tid}/charge", json={"pay_method": "efectivo"}).status_code == 201
    assert client.post(f"/api/tickets/{tid}/charge", json={"pay_method": "efectivo"}).status_code == 404
    assert ps.get_product(pid)["stock"] == 8


def test_medio_de_pago_del_ticket(client):
    tid = _ticket(client)
    assert client.put(f"/api/tickets/{tid}/pay_method", json={"pay_method": "credito"}).get_json()["pay_method"] == "credito"
    assert client.put(f"/api/tickets/{tid}/pay_method", json={"pay_method": "x"}).status_code == 400
    assert client.put("/api/tickets/9999/pay_method", json={"pay_method": "credito"}).status_code == 404


# ---------- Comprobante ----------
def test_comprobante_trae_ids_items_y_datos_del_negocio(client):
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Cervecería Ñandú", rut="76.1-7",
                                 api_token=TOKEN))
    pid = _producto("Rubia", price=1500)
    tid = _ticket(client)
    client.post(f"/api/tickets/{tid}/items", json={"product_id": pid, "qty": 2})
    sale_id = client.post(f"/api/tickets/{tid}/charge", json={"pay_method": "efectivo"}).get_json()["sale_id"]
    data = client.get(f"/api/sales/{sale_id}/receipt").get_json()
    assert data["sale_id"] == sale_id and data["total"] == 3000
    assert data["business_name"] == "Cervecería Ñandú" and data["rut"] == "76.1-7"
    assert data["items"] == [{"name": "Rubia", "qty": 2, "unit_price": 1500, "line_total": 3000}]
    assert data["pay_method"] == "efectivo" and data["received"] is None
    assert client.get("/api/sales/999/receipt").status_code == 404


# ---------- Robustez ----------
def test_cuerpo_que_no_es_json_no_rompe_el_servidor(client):
    tid = _ticket(client)
    r = client.post(f"/api/tickets/{tid}/items", data="no es json", content_type="text/plain")
    assert r.status_code == 400
    r = client.post("/api/tickets", data="[1,2]", content_type="application/json")
    assert r.status_code == 201  # un arreglo se ignora y el ticket se crea sin nombre


def test_error_inesperado_no_filtra_el_traceback(client, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secreto interno C:\\ruta\\privada")

    monkeypatch.setattr(ts, "list_open_tickets", boom)
    r = client.get("/api/tickets")
    assert r.status_code == 500
    assert r.get_json() == {"error": "Error interno del servidor."}
    assert "secreto" not in json.dumps(r.get_json())


# ---------- Clave compartida (api_token) ----------
def test_con_token_configurado_las_rutas_exigen_la_clave(client):
    sin = client.sin_clave()
    r = sin.get("/api/products")
    assert r.status_code == 401 and "Clave" in r.get_json()["error"]
    assert sin.get("/api/products", headers={"X-Caja-Token": "otra"}).status_code == 401
    assert sin.post("/api/tickets", json={}).status_code == 401
    assert client.get("/api/products").status_code == 200
    assert client.post("/api/tickets", json={}).status_code == 201


def test_health_no_pide_clave_para_poder_diagnosticar_la_conexion(client):
    assert client.sin_clave().get("/api/health").status_code == 200


def test_sin_token_configurado_la_api_responde_401_no_queda_abierta(temp_db, tmp_path, monkeypatch):
    """Sin clave en config.json la API NO se abre: rechaza todo, con o sin cabecera."""
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG))        # sin api_token
    c = create_app().test_client()
    for path in ("/api/products", "/api/tickets", "/api/config"):
        assert c.get(path).status_code == 401
    assert c.post("/api/tickets", json={}).status_code == 401
    assert c.get("/api/products", headers={"X-Caja-Token": "lo-que-sea"}).status_code == 401
    assert c.get("/api/products", headers={"X-Caja-Token": ""}).status_code == 401
    assert c.get("/api/health").status_code == 200                   # solo el diagnostico queda abierto


@pytest.mark.parametrize("token", ["", "   ", None])
def test_token_vacio_o_solo_espacios_cuenta_como_sin_token(temp_db, tmp_path, monkeypatch, token):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=token))
    c = create_app().test_client()
    assert c.get("/api/products").status_code == 401
    assert c.get("/api/products", headers={"X-Caja-Token": token or ""}).status_code == 401


def test_el_arranque_del_servidor_genera_y_guarda_una_clave_si_falta(temp_db, tmp_path, monkeypatch):
    """run() (arranque de la Caja 1) con token vacio: genera uno aleatorio y lo guarda en config."""
    import json
    from flet_app import api_server

    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, business_name="Mi Local"))
    assert "api_token" not in json.loads(cfg_path.read_text(encoding="utf-8"))

    servidas = []
    monkeypatch.setattr(api_server, "run_simple", lambda host, port, app, **k: servidas.append((host, port, k)))
    api_server.run(port=8780, bootstrap=False)

    guardado = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert len(guardado["api_token"]) >= 20                              # aleatorio y no trivial
    assert guardado["business_name"] == "Mi Local"                       # no pisa el resto
    assert servidas and servidas[0][0] == "0.0.0.0" and servidas[0][1] == 8780
    # y con esa clave la API responde; sin ella, 401
    c = create_app().test_client()
    assert c.get("/api/products").status_code == 401
    assert c.get("/api/products", headers={"X-Caja-Token": guardado["api_token"]}).status_code == 200


def test_el_arranque_no_cambia_una_clave_que_ya_existe(temp_db, tmp_path, monkeypatch):
    import json
    from flet_app import api_server

    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token="la-que-puso-el-dueno"))
    monkeypatch.setattr(api_server, "run_simple", lambda *a, **k: None)
    api_server.run(port=8780, bootstrap=False)
    api_server.run(port=8780, bootstrap=False)                           # reiniciar la app
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["api_token"] == "la-que-puso-el-dueno"


def test_dos_arranques_sin_clave_dejan_una_sola_y_estable(temp_db, tmp_path, monkeypatch):
    import json
    from flet_app import api_server

    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(cfg_path))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG))
    monkeypatch.setattr(api_server, "run_simple", lambda *a, **k: None)
    api_server.run(port=8780, bootstrap=False)
    primera = json.loads(cfg_path.read_text(encoding="utf-8"))["api_token"]
    api_server.run(port=8780, bootstrap=False)
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["api_token"] == primera


def test_las_claves_generadas_son_distintas_entre_instalaciones(tmp_path, monkeypatch):
    from flet_app import multicaja

    tokens = set()
    for n in range(5):
        monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / f"c{n}.json"))
        core_config.save_config(dict(core_config.DEFAULT_CONFIG))
        tokens.add(multicaja.ensure_api_token())
    assert len(tokens) == 5


def test_el_cliente_manda_la_clave_y_el_rechazo_es_un_error_claro(temp_db, tmp_path, monkeypatch):
    from flet_app.api_client import ApiClient, ApiError
    from tests.test_api_client import FlaskSession
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token="s3cret"))
    sess = FlaskSession(create_app().test_client())
    assert ApiClient("http://c:8780", sess, token="s3cret").list_open_tickets() == []
    with pytest.raises(ApiError) as exc:
        ApiClient("http://c:8780", sess, token="mala").list_open_tickets()
    assert exc.value.status == 401 and "Clave" in str(exc.value)
    with pytest.raises(ApiError):
        ApiClient("http://c:8780", sess).list_open_tickets()


# ---------- Dos cajas cobran el mismo ticket a la vez (venta doble) ----------
def test_dos_cajas_cobran_el_mismo_ticket_a_la_vez_solo_una_vende(temp_db, tmp_path, monkeypatch):
    """Por la API, en paralelo y con hilos reales: una venta, un 201 y el otro rechazado (409/404)."""
    import threading

    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=TOKEN))
    app = create_app()
    pid = _producto(stock=50, price=1500)
    c = ClienteConClave(app.test_client())
    tid = c.post("/api/tickets", json={"name": "Mesa 1"}).get_json()["id"]
    c.post(f"/api/tickets/{tid}/items", json={"product_id": pid, "qty": 3})

    barrera = threading.Barrier(2)
    codigos = []

    def cobrar():
        cli = ClienteConClave(app.test_client())      # cada caja con su propia conexion HTTP
        barrera.wait()
        codigos.append(cli.post(f"/api/tickets/{tid}/charge", json={"pay_method": "efectivo"}).status_code)

    hilos = [threading.Thread(target=cobrar) for _ in range(2)]
    [h.start() for h in hilos]
    [h.join(timeout=30) for h in hilos]

    assert codigos.count(201) == 1, codigos            # una sola caja vendio
    assert [c for c in codigos if c != 201][0] in (404, 409), codigos   # la otra fue rechazada limpio
    assert ps.get_product(pid)["stock"] == 47          # descontado una sola vez
    with db_manager.get_conn() as con:
        assert con.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
