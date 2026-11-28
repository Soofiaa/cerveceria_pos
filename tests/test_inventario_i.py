import pytest
import flet as ft
from flet_app.reportes_view import ReportesView
from flet_app.inventario_page import INVENTARIO_HTML

class FakePage:
    def __init__(self):
        self.overlay = []
    def update(self):
        pass

class FakeBackendLocal:
    is_remote = False
    def report_summary(self, d1, d2): return {"total": 0, "tickets": 0, "avg_ticket": 0, "profit": 0}
    def report_sales(self, d1, d2): return []
    def report_top_products(self, d1, d2): return []
    def shopping_list(self): return []

def test_reportes_view_ver_en_telefono():
    page = FakePage()
    colors = {
        "text": "#000", "secondary": "#666", "primary": "#6c3483",
        "accent": "#ccc", "surface": "#fff", "danger": "#c0392b", "primary_text": "#fff"
    }
    view = ReportesView(page, colors, backend=FakeBackendLocal())
    view.load_data()

    # Verificar que el botón "Ver en el teléfono" existe y está visible en modo local
    assert view.btn_ver_telefono.visible is True
    # TextButton content can be ft.Text or string depending on Flet version
    content_val = view.btn_ver_telefono.content
    if isinstance(content_val, ft.Text):
        assert content_val.value == "Ver en el teléfono"
    else:
        assert str(content_val) == "Ver en el teléfono"

    # Simular clic en el botón para abrir el diálogo
    view._open_telefono_dialog()
    
    assert len(page.overlay) == 1
    dlg = page.overlay[0]
    assert isinstance(dlg, ft.AlertDialog)
    assert dlg.open is True

    # Verificar contenido del diálogo (imagen QR y campo URL)
    content = dlg.content
    assert isinstance(content, ft.Column)
    qr_img = content.controls[0]
    assert isinstance(qr_img, ft.Image)
    assert qr_img.src.startswith("data:image/svg+xml")

def test_inventario_html_markers():
    assert "Tip: agrega esta página" in INVENTARIO_HTML
    assert "btn-todo" in INVENTARIO_HTML
    assert "mipos_inv_checked" in INVENTARIO_HTML
    assert "Comprados" in INVENTARIO_HTML
    assert "Solo lo que falta" in INVENTARIO_HTML
    assert "Todo" in INVENTARIO_HTML
