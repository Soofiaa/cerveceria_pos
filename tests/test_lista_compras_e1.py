import os
import types
import pytest
from core import product_service as ps
from flet_app.lista_compras_pdf import build_lista_compras_pdf
from flet_app.reportes_view import ReportesView
from core import db_manager
import flet as ft

class RecordingWindow(types.SimpleNamespace):
    """Ventana falsa que anota cada escritura de atributo."""
    def __init__(self):
        object.__setattr__(self, "writes", [])
        super().__init__(
            width=1280, height=720, min_width=1000, min_height=650,
            maximized=False, minimized=False,
        )
        self.writes.clear()

    def __setattr__(self, name, value):
        if name != "writes":
            self.writes.append((name, value))
        super().__setattr__(name, value)

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

# Mock backend for testing reportes_view
class MockBackend:
    def __init__(self, is_remote=False, items=None):
        self.is_remote = is_remote
        self.items = items or []
    def shopping_list(self):
        return self.items
    def report_summary(self, d1, d2): return {"total": 0, "tickets": 0, "avg_ticket": 0}
    def report_sales(self, d1, d2): return []
    def report_top_products(self, d1, d2): return []

def test_shopping_list_logic(temp_db):
    ps.create_product("Agotado", sale_price=100, stock=0, min_stock=5)
    ps.create_product("Bajo", sale_price=100, stock=2, min_stock=6)
    ps.create_product("Al limite", sale_price=100, stock=5, min_stock=5)
    ps.create_product("Normal", sale_price=100, stock=10, min_stock=5)
    ps.create_product("Min 0", sale_price=100, stock=0, min_stock=0)
    
    ps.create_product("Producto común", sale_price=100, stock=0, min_stock=5)
    p_inact = ps.create_product("Inactivo", sale_price=100, stock=0, min_stock=5)
    ps.desactivar_producto(p_inact)
    
    items = ps.shopping_list()
    
    names = [i['name'] for i in items]
    assert "Agotado" in names
    assert "Bajo" in names
    assert "Al limite" in names
    assert "Normal" not in names
    assert "Min 0" in names
    assert "Producto común" not in names
    assert "Inactivo" not in names
    
    assert items[0]['name'] == "Agotado"
    assert items[1]['name'] == "Min 0"
    assert items[2]['name'] == "Bajo"
    assert items[3]['name'] == "Al limite"

def test_build_lista_compras_pdf_robustness(tmp_path):
    items = [
        {"name": "Cerveza 🍺", "stock": 0, "agotado": True, "sugerido": 5},
        {"name": "Normal", "stock": 2, "agotado": False, "sugerido": 10}
    ]
    path = tmp_path / "lista.pdf"
    build_lista_compras_pdf(items, "Negocio", "01-01-2026 10:00", str(path))
    assert os.path.exists(path)
    with open(path, "rb") as f:
        content = f.read()
        assert content.startswith(b"%PDF")
        assert len(content) > 500

def test_reportes_view_lista_compras(temp_db):
    page = FakePage()
    backend = MockBackend(is_remote=False, items=[
        {"name": "Agotado", "stock": 0, "agotado": True, "sugerido": 10},
        {"name": "Bajo", "stock": 2, "agotado": False, "sugerido": 10}
    ])
    colors = {
        "text": "black", "primary": "blue", "secondary": "gray", "danger": "red",
        "accent": "green", "surface": "white", "primary_text": "white"
    }
    view = ReportesView(page, colors, backend=backend)
    view.load_data()
    
    found_agotado = False
    for c in view.lista_compras_container.controls:
        if isinstance(c, ft.Container):
            row = c.content
            if isinstance(row, ft.Row):
                if "Agotado" in row.controls[0].controls[0].value:
                    found_agotado = True
                    assert row.controls[1].content.value == "AGOTADO"
    assert found_agotado

def test_reportes_view_remote(temp_db):
    page = FakePage()
    backend = MockBackend(is_remote=True)
    colors = {
        "text": "black", "primary": "blue", "secondary": "gray", "danger": "red",
        "accent": "green", "surface": "white", "primary_text": "white"
    }
    view = ReportesView(page, colors, backend=backend)
    view.load_data()
    
    assert "La lista de compras se genera en la Caja 1." in view.lista_compras_container.controls[0].value
    assert view.btn_pdf.visible is False
