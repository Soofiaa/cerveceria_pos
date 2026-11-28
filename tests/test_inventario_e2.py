import pytest
from core import product_service as ps
from core import category_service as cs
from core import config as core_config
from core import db_manager
from flet_app import multicaja
from flet_app.api_server import create_app

try:
    from flet_app.config_view import ConfigView
    from flet_app.inventario_page import INVENTARIO_HTML
except Exception:  # pragma: no cover - flet puede faltar en algunos entornos
    ConfigView = None
    INVENTARIO_HTML = None


# ---------- inventory_snapshot ----------

def test_inventory_snapshot_orden_categoria_y_faltantes(temp_db):
    cat_a = cs.create_category("Bebidas")
    cat_b = cs.create_category("Carnes")

    ps.create_product("Hamburguesa", 5000, stock=0, min_stock=5, category_id=cat_b)
    ps.create_product("Refresco", 1000, stock=100, min_stock=5, category_id=cat_a)
    ps.create_product("Cerveza", 2000, stock=1, min_stock=5, category_id=cat_a)
    ps.create_product("Sin categoria producto", 3000, stock=20, min_stock=5)

    snap = ps.inventory_snapshot()

    assert set(snap.keys()) == {"faltantes", "inventario"}

    nombres = [p["name"] for p in snap["inventario"]]
    assert "Hamburguesa" in nombres
    assert "Sin categoria producto" in nombres
    # producto comun excluido
    assert all(p["name"] != "Producto común" for p in snap["inventario"])

    # orden: nombre de categoria, sin categoria al final, luego nombre producto
    cats = [p["category_name"] for p in snap["inventario"]]
    if "Bebidas" in cats and "Carnes" in cats:
        assert cats.index("Bebidas") < cats.index("Carnes")
    # sin categoria al final
    sin_cat = [p for p in snap["inventario"] if p["category_name"] is None]
    if sin_cat:
        assert snap["inventario"][-1]["category_name"] is None

    # cada item tiene los campos esperados
    for p in snap["inventario"]:
        assert set(p.keys()) == {"id", "name", "stock", "min_stock", "category_id", "category_name"}

    # faltantes coincide con shopping_list()
    assert snap["faltantes"] == ps.shopping_list()


def test_inventory_snapshot_excluye_inactivos(temp_db):
    cat = cs.create_category("Lacteos")
    pid_activo = ps.create_product("Leche", 1000, stock=100, min_stock=5, category_id=cat)
    pid_inactivo = ps.create_product("Yogur", 1000, stock=0, min_stock=5, category_id=cat)
    ps.desactivar_producto(pid_inactivo)

    snap = ps.inventory_snapshot()
    nombres = [p["name"] for p in snap["inventario"]]
    assert "Leche" in nombres
    assert "Yogur" not in nombres


# ---------- API ----------

def _cliente_api(temp_db, tmp_path, monkeypatch, token=None):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    if token is not None:
        core_config.save_config(dict(core_config.DEFAULT_CONFIG, api_token=token, inventory_key="clave-inv"))
    else:
        core_config.save_config(dict(core_config.DEFAULT_CONFIG, inventory_key="clave-inv"))
    return create_app().test_client()


def test_api_inventory_autenticacion(temp_db, tmp_path, monkeypatch):
    c = _cliente_api(temp_db, tmp_path, monkeypatch, token="tok-caja")

    # sin clave -> 401
    r = c.get("/api/inventory")
    assert r.status_code == 401

    # clave mala -> 401
    r = c.get("/api/inventory", headers={"X-Inventory-Key": "clave-mala"})
    assert r.status_code == 401

    # token de caja NO autoriza -> 401
    r = c.get("/api/inventory", headers={"X-Caja-Token": "tok-caja"})
    assert r.status_code == 401

    # clave de inventario -> 200 y forma del payload
    r = c.get("/api/inventory", headers={"X-Inventory-Key": "clave-inv"})
    assert r.status_code == 200
    data = r.get_json()
    assert set(data.keys()) == {"faltantes", "inventario", "business_name", "generated_at"}

    # la clave de inventario NO autoriza /api/products
    r = c.get("/api/products", headers={"X-Inventory-Key": "clave-inv"})
    assert r.status_code == 401


# ---------- ensure_inventory_key ----------

def test_ensure_inventory_key_estable(temp_db):
    k1 = multicaja.ensure_inventory_key()
    k2 = multicaja.ensure_inventory_key()
    assert k1 == k2
    assert k1 and len(k1) > 8


def test_ensure_inventory_key_regenerar(temp_db):
    k1 = multicaja.ensure_inventory_key()
    k2 = multicaja.ensure_inventory_key(regenerate=True)
    assert k1 != k2
    k3 = multicaja.ensure_inventory_key()
    assert k3 == k2


# ---------- Pagina ----------

def test_inventario_page_sirve_html(temp_db, tmp_path, monkeypatch):
    multicaja.ensure_inventory_key()
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG, inventory_key="clave-inv"))

    app = create_app()
    client = app.test_client()

    r = client.get("/inventario")
    assert r.status_code == 200
    assert r.content_type.startswith("text/html")
    html = r.get_data(as_text=True)
    assert "mipos_inv_data" in html
    assert "Sin conexión con la Caja 1. Estás viendo la última copia" in html
    assert "No se actualiza mientras la caja esté apagada." in html
    assert "Sin conexión con la Caja 1 y todavía no hay una copia guardada" in html


# ---------- Vista de configuracion ----------

def test_config_view_bloque_inventario(temp_db, tmp_path, monkeypatch):
    if ConfigView is None:
        pytest.skip("flet no disponible")

    class FakePage:
        def __init__(self):
            self.controls = []
            self.overlay = []
            self.bgcolor = ""
            self.title = ""
            self.window = type("W", (), {"width": 1280, "height": 720})()
            self.updates = 0

        def add(self, *c):
            self.controls.extend(c)

        def update(self):
            self.updates += 1

    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    core_config.save_config(dict(core_config.DEFAULT_CONFIG))

    page = FakePage()
    colors = {"text": "#000000", "secondary": "#666666", "primary": "#6c3483",
              "primary_text": "#ffffff", "danger": "#c0392b", "surface": "#ffffff"}

    view = ConfigView(page, colors, lambda n: None, lambda c: None)

    # El bloque existe y tiene los controles esperados
    assert view.inv_box is not None
    assert view.inv_url is not None
    assert view.qr_img is not None
    assert view.txt_inv_key is not None
    assert view.btn_regenerar_inv is not None
    assert view.btn_copy_inv_key is not None

    # El bloque de inventario contiene la línea nueva sobre actualización
    texto_encontrado = False
    def _buscar_texto(control):
        nonlocal texto_encontrado
        if texto_encontrado:
            return
        if hasattr(control, 'value') and isinstance(getattr(control, 'value'), str):
            if "El teléfono solo se actualiza si esta caja está encendida" in control.value:
                texto_encontrado = True
        if hasattr(control, 'controls') and isinstance(getattr(control, 'controls'), list):
            for c in control.controls:
                _buscar_texto(c)
    _buscar_texto(view.inv_box)
    assert texto_encontrado, "No se encontró el texto sobre actualización del teléfono en ConfigView.inv_box"
