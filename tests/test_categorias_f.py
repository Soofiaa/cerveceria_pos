import pytest
import sqlite3
import flet as ft
from core import db_manager
from core import category_service as cs
from core import product_service as ps
from flet_app.productos_view import ProductosView

class RecordingWindow:
    def __init__(self):
        self.writes = []

class FakePage:
    def __init__(self):
        self.controls = []
        self.overlay = []
        self.bgcolor = ""
        self.title = ""
        self.window = RecordingWindow()
        self.updates = 0

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        self.updates += 1

    def show_dialog(self, dlg):
        self.overlay.append(dlg)
        dlg.open = True
        self.update()

def test_category_service_crud_and_validation(temp_db):
    # 1. Crear vacio / espacios
    with pytest.raises(ValueError, match="no puede estar vacío"):
        cs.create_category("   ")

    # 2. Crear normal
    cid1 = cs.create_category("Bebidas")
    cid2 = cs.create_category("Cervezas")

    # 3. Duplicado case-insensitive
    with pytest.raises(ValueError, match="Ya existe una categoría"):
        cs.create_category("bebidas")

    # 4. Listar ordenado con conteo
    prods = ps.list_products()
    p1 = ps.create_product("Agua", 1000, category_id=cid1)
    
    cats = cs.list_categories()
    assert len(cats) == 2
    assert cats[0]["name"] == "Bebidas"
    assert cats[0]["product_count"] == 1
    assert cats[1]["name"] == "Cervezas"
    assert cats[1]["product_count"] == 0

    # 5. Renombrar OK y duplicado
    cs.rename_category(cid2, "Artesanales")
    with pytest.raises(ValueError, match="Ya existe una categoría"):
        cs.rename_category(cid2, "Bebidas")

    # 6. Borrar categoría no borra productos, deja category_id NULL
    cs.delete_category(cid1)
    cats_after = cs.list_categories()
    assert len(cats_after) == 1
    
    prod_updated = ps.get_product(p1)
    assert prod_updated["category_id"] is None
    assert prod_updated["category_name"] is None

def test_migration_and_db_schema(temp_db):
    db_manager.bootstrap()
    # Correr segunda vez (idempotente)
    db_manager.bootstrap()

    with db_manager.get_conn() as con:
        cur = con.cursor()
        cur.execute("PRAGMA table_info(products);")
        cols = [r[1] for r in cur.fetchall()]
        assert "category_id" in cols

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories';")
        assert cur.fetchone() is not None

def test_product_service_category_integration(temp_db):
    cid = cs.create_category("Promos")
    
    # Con categoria
    pid1 = ps.create_product("Combo 1", 5000, category_id=cid)
    # Sin categoria (compatibilidad)
    pid2 = ps.create_product("Suelto", 1000)

    p1 = ps.get_product(pid1)
    assert p1["category_id"] == cid
    assert p1["category_name"] == "Promos"

    p2 = ps.get_product(pid2)
    assert p2["category_id"] is None
    assert p2["category_name"] is None

    # update_product
    ps.update_product(pid2, category_id=cid)
    p2_updated = ps.get_product(pid2)
    assert p2_updated["category_id"] == cid

def test_productos_view_filter_and_dropdown(temp_db):
    cid = cs.create_category("Lager")
    pid = ps.create_product("Rubia", 2500, category_id=cid)

    page = FakePage()
    view = ProductosView(page)
    view.load_data()

    # Verificar que el filtro tiene la categoria
    opt_keys = [o.key for o in view.filter_category.options]
    assert str(cid) in opt_keys

    # Filtrar por categoría
    view.filter_category.value = str(cid)
    view.load_data()
    # Comprobar filas cargadas
    assert len(view.table.rows) == 1

def _new_product_dialog(page, view):
    import asyncio
    asyncio.run(view._open_dialog())
    return page.overlay[-1]


def test_dialogo_nuevo_muestra_selector_con_categorias(temp_db):
    cs.create_category("Lager")
    cs.create_category("IPA")
    page = FakePage()
    view = ProductosView(page)
    dlg = _new_product_dialog(page, view)
    row = dlg.content.controls[6]
    dropdown = row.controls[0]
    assert [o.text for o in dropdown.options] == ["Sin categoría", "IPA", "Lager"]
    assert dropdown.value == ""


def test_guardar_con_categoria_elegida_persiste_category_id(temp_db):
    cid = cs.create_category("Lager")
    page = FakePage()
    view = ProductosView(page)
    dlg = _new_product_dialog(page, view)
    fields = dlg.content.controls
    fields[0].value = "Rubia"
    fields[1].value = "2500"
    fields[6].controls[0].value = str(cid)
    dlg.actions[0].on_click(None)
    prod = next(p for p in ps.list_products("") if p["name"] == "Rubia")
    assert prod["category_id"] == cid
    assert prod["category_name"] == "Lager"


def test_filtro_por_categoria_deja_solo_los_de_esa_categoria(temp_db):
    cid = cs.create_category("Lager")
    ps.create_product("Rubia", 2500, category_id=cid)
    ps.create_product("Suelta", 1000)
    page = FakePage()
    view = ProductosView(page)

    def names():
        view.load_data()
        return {r.cells[0].content.value for r in view.table.rows}

    assert {"Rubia", "Suelta"} <= names()
    view.filter_category.value = str(cid)
    assert names() == {"Rubia"}
    view.filter_category.value = ""
    got = names()
    assert "Suelta" in got and "Rubia" not in got


def test_nueva_categoria_desde_formulario_queda_seleccionada(temp_db):
    import asyncio
    page = FakePage()
    view = ProductosView(page)
    dlg = _new_product_dialog(page, view)
    row = dlg.content.controls[6]
    asyncio.run(row.controls[1].on_click(None))
    sub = page.overlay[-1]
    sub.content.controls[0].value = "Stout"
    sub.actions[0].on_click(None)
    cats = cs.list_categories()
    assert [c["name"] for c in cats] == ["Stout"]
    assert row.controls[0].value == str(cats[0]["id"])
    assert "Stout" in [o.text for o in row.controls[0].options]


def test_nueva_categoria_duplicada_muestra_error_y_no_cierra(temp_db):
    import asyncio
    cs.create_category("Stout")
    page = FakePage()
    view = ProductosView(page)
    dlg = _new_product_dialog(page, view)
    asyncio.run(dlg.content.controls[6].controls[1].on_click(None))
    sub = page.overlay[-1]
    sub.content.controls[0].value = "stout"
    sub.actions[0].on_click(None)
    assert "Ya existe" in sub.content.controls[1].value
    assert sub.open is True
