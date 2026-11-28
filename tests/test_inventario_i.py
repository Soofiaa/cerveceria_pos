import pytest
import flet as ft
from flet_app.productos_view import ProductosView
from flet_app.inventario_page import INVENTARIO_HTML

class FakePage:
    def __init__(self):
        self.overlay = []
    def update(self):
        pass

def _productos_view(page):
    return ProductosView(page)

def _reportes_view(page):
    from flet_app.reportes_view import ReportesView
    return ReportesView(page, {
        "text": "#000", "secondary": "#000", "primary": "#000",
        "accent": "#000", "surface": "#000", "danger": "#000", "primary_text": "#fff",
    })

def test_productos_view_ver_en_telefono():
    page = FakePage()
    view = _productos_view(page)

    btns = [
        btn for row in view.controls if isinstance(row, ft.Row)
        for btn in row.controls
        if isinstance(btn, ft.TextButton) and str(btn.content) == "Ver en el teléfono"
    ]
    assert len(btns) == 1, "El botón 'Ver en el teléfono' no aparece en ProductosView"

    # El botón NO debe estar en ReportesView (se movió a Productos)
    rv = _reportes_view(page)
    assert not hasattr(rv, "btn_ver_telefono")

    # Dialogo del QR al hacer clic
    view._open_telefono_dialog()
    assert len(page.overlay) == 1
    dlg = page.overlay[0]
    assert isinstance(dlg, ft.AlertDialog)
    assert dlg.open is True

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
