"""Tests de la vista Productos (Fase 2).

Funciones REALES de flet_app.productos_view y de core/product_service, y
navegacion POS/Productos de flet_app.main. Nada de copias: todo se importa
del codigo real. La vista se prueba con una pagina falsa (sin abrir
ventana); importar flet_app.main no abre ventana porque ft.run esta bajo
if __name__ == "__main__".
"""

import asyncio
import inspect
import types

import flet as ft
import pytest

from core import product_backup_service as pbs
from core import product_service as ps
from flet_app import main as pos_main
from flet_app.productos_view import (
    ERROR,
    TEXT,
    ProductosView,
    _parse_money,
    _parse_money_or_none,
    is_common_product,
)


class FakePage:
    def __init__(self):
        self.title = ""
        self.bgcolor = ""
        self.controls = []
        self.overlay = []
        self.window = types.SimpleNamespace(
            width=1280, height=720, min_width=1000, min_height=650
        )

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass


def _cell_text(row, index):
    return row.cells[index].content


def test_parse_money():
    assert _parse_money("$10.500") == 10500
    assert _parse_money("1.000") == 1000
    assert _parse_money("10,500") == 10500
    assert _parse_money("") == 0
    assert _parse_money("abc") == 0
    assert _parse_money(None) == 0
    assert _parse_money_or_none("$1.000") == 1000
    assert _parse_money_or_none("") is None
    assert _parse_money_or_none("abc") is None


def test_reactivar_producto(temp_db):
    pid = ps.create_product("Reactivable", 1000, barcode="R1")
    ps.desactivar_producto(pid)
    assert all(p["id"] != pid for p in ps.list_products(""))
    assert any(p["id"] == pid for p in ps.list_products("", incluir_inactivos=True))
    ps.reactivar_producto(pid)
    assert any(p["id"] == pid and p["is_active"] for p in ps.list_products(""))


def test_create_duplicate_barcode(temp_db):
    ps.create_product("Primero", 1000, barcode="DUP1")
    with pytest.raises(ValueError, match="código de barras"):
        ps.create_product("Segundo", 2000, barcode="DUP1")


def _make_view(temp_db):
    ps.create_product("Normal", 1000, stock=10, min_stock=2)
    ps.create_product("Bajo", 500, stock=1, min_stock=5)
    page = FakePage()
    view = ProductosView(page)
    view.load_data()
    return page, view


def test_view_lists_products_and_marks_low_stock(temp_db):
    page, view = _make_view(temp_db)
    rows = view.table.rows
    # Producto comun (lo crea bootstrap) + Normal + Bajo.
    assert len(rows) == 3
    assert "Mostrando 3 producto(s)." in view.count_lbl.value
    by_name = {r.cells[0].content.value: r for r in rows}
    assert _cell_text(by_name["Bajo"], 4).value == "1"
    assert _cell_text(by_name["Bajo"], 4).color == ERROR
    assert "Stock bajo" in _cell_text(by_name["Bajo"], 6).value
    assert _cell_text(by_name["Normal"], 4).color == TEXT
    assert "Activo" in _cell_text(by_name["Normal"], 6).value


def test_view_toggle_inactivos(temp_db):
    page, view = _make_view(temp_db)
    pid = ps.create_product("Borrable", 700)
    ps.desactivar_producto(pid)
    view.load_data()
    names = [r.cells[0].content.value for r in view.table.rows]
    assert "Borrable" not in names
    view.chk_inactivos.value = True
    view.load_data()
    rows = {r.cells[0].content.value: r for r in view.table.rows}
    assert "Borrable" in rows
    labels = [c.content for c in rows["Borrable"].cells[7].content.controls]
    assert "Reactivar" in labels
    assert "Inactivo" in rows["Borrable"].cells[6].content.value


def test_view_search_filters(temp_db):
    page, view = _make_view(temp_db)
    ps.create_product("Cerveza Negra", 1800)
    view.search.value = "Negra"
    view.load_data()
    names = [r.cells[0].content.value for r in view.table.rows]
    assert names == ["Cerveza Negra"]


def test_view_common_product_has_no_quitar(temp_db):
    page, view = _make_view(temp_db)
    rows = {r.cells[0].content.value: r for r in view.table.rows}
    common = rows["Producto común"]
    quitar = [c for c in common.cells[7].content.controls if c.content == "Quitar"]
    assert len(quitar) == 1
    assert quitar[0].disabled is True
    assert is_common_product({"name": "Producto común"})
    assert not is_common_product({"name": "Normal"})


def test_dialog_create_product_saves(temp_db):
    page = FakePage()
    view = ProductosView(page)
    asyncio.run(view._open_dialog())
    dlg = page.overlay[-1]
    assert isinstance(dlg, ft.AlertDialog)
    fields = dlg.content.controls
    fields[0].value = "DialogoTest"
    fields[1].value = "1.000"
    fields[2].value = "500"
    fields[4].value = "3"
    dlg.actions[0].on_click(None)
    assert any(p["name"] == "DialogoTest" for p in ps.list_products(""))
    assert dlg.open is False


def test_dialog_duplicate_barcode_keeps_dialog_open(temp_db):
    ps.create_product("YaExiste", 1000, barcode="DUP2")
    page = FakePage()
    view = ProductosView(page)
    asyncio.run(view._open_dialog())
    dlg = page.overlay[-1]
    fields = dlg.content.controls
    fields[0].value = "Otro"
    fields[1].value = "2000"
    fields[3].value = "DUP2"
    dlg.actions[0].on_click(None)
    assert "código de barras" in fields[6].value
    assert dlg.open is True
    assert len(ps.list_products("Otro")) == 0


def test_nav_switches_views(temp_db):
    page = FakePage()
    pos_main.main(page)
    # Layout: barra superior con pestanas; debajo, tickets a la izquierda y
    # el area central (POS o Productos).
    root = page.controls[0]
    top_bar, body = root.controls
    tickets_box = body.controls[0]
    content_area = body.controls[1].content
    _brand, _gap, pos_btn, prod_btn = top_bar.content.controls[:4]
    # Al inicio: el POS (columna principal + tarjeta del total).
    assert len(content_area.controls) == 2
    assert tickets_box.visible is not False
    # Ir a Productos: el area central es la vista y los tickets se ocultan.
    asyncio.run(prod_btn.on_click(None))
    assert len(content_area.controls) == 1
    productos_card = content_area.controls[0]
    assert any(isinstance(c, ProductosView) for c in productos_card.content.controls)
    assert tickets_box.visible is False
    # Volver al POS: vuelven la columna principal y el total, y los tickets.
    asyncio.run(pos_btn.on_click(None))
    assert len(content_area.controls) == 2
    assert tickets_box.visible is True


def test_view_does_not_add_picker_at_startup(temp_db):
    page = FakePage()
    view = ProductosView(page)
    assert page.overlay == []
    assert isinstance(view.picker, ft.FilePicker)


# ---------- Botones reales (como los despacha Flet) ----------
def _click(button):
    """Pulsa un boton igual que Flet 1.1.2 (base_control.py): solo hace
    await si el handler es async def. Si un handler sincrono (por ejemplo
    un lambda) devuelve una corrutina, Flet la descarta sin ejecutarla:
    eso es el bug "coroutine ... was never awaited" y aqui falla el test."""
    handler = button.on_click
    assert handler is not None, f"El botón {button.content!r} no tiene on_click"
    if inspect.iscoroutinefunction(handler):
        asyncio.run(handler(None))
        return
    result = handler(None)
    assert not inspect.iscoroutine(result), (
        f"El botón {button.content!r} devuelve una corrutina que Flet no ejecuta"
    )


def _open_dialogs(page):
    return [c for c in page.overlay if isinstance(c, ft.AlertDialog) and c.open]


def _row_button(view, product_name, label):
    for row in view.table.rows:
        if row.cells[0].content.value == product_name:
            for btn in row.cells[7].content.controls:
                if btn.content == label:
                    return btn
    raise AssertionError(f'No hay botón "{label}" para "{product_name}"')


def _dialog_button(dlg, label):
    for btn in dlg.actions:
        if btn.content == label:
            return btn
    raise AssertionError(f'El diálogo no tiene botón "{label}"')


def test_boton_agregar_producto_abre_dialogo(temp_db):
    page = FakePage()
    view = ProductosView(page)
    agregar = view.controls[1].controls[0]
    assert agregar.content == "Agregar producto"
    _click(agregar)
    dialogs = _open_dialogs(page)
    assert len(dialogs) == 1
    assert dialogs[0].title.value == "Nuevo producto"


def test_boton_editar_abre_dialogo_con_datos(temp_db):
    page, view = _make_view(temp_db)
    _click(_row_button(view, "Normal", "Editar"))
    dlg = _open_dialogs(page)[-1]
    assert dlg.title.value == "Editar producto"
    assert dlg.content.controls[0].value == "Normal"
    dlg.content.controls[1].value = "2.000"
    _click(_dialog_button(dlg, "Guardar"))
    assert ps.find_product_by_exact_code_or_name("Normal")["sale_price"] == 2000


def test_boton_quitar_sin_ventas_pide_confirmacion_y_borra(temp_db):
    page, view = _make_view(temp_db)
    _click(_row_button(view, "Normal", "Quitar"))
    confirm = _open_dialogs(page)[-1]
    assert confirm.title.value == "Quitar producto"
    assert ps.find_product_by_exact_code_or_name("Normal") is not None
    _click(_dialog_button(confirm, "Sí"))
    assert all(p["name"] != "Normal" for p in ps.list_products("", incluir_inactivos=True))


def test_boton_quitar_con_ventas_ofrece_desactivar(temp_db):
    from core import sales_service as ss
    from core import ticket_service as ts

    page, view = _make_view(temp_db)
    prod = ps.find_product_by_exact_code_or_name("Normal")
    tid = ts.create_ticket("Ticket 1")
    ts.add_item(tid, prod["id"], 1, prod["sale_price"])
    ss.cobrar_ticket(tid)

    _click(_row_button(view, "Normal", "Quitar"))
    _click(_dialog_button(_open_dialogs(page)[-1], "Sí"))
    offer = _open_dialogs(page)[-1]
    assert "ventas registradas" in offer.content.value
    _click(_dialog_button(offer, "Sí, desactivar"))
    inactive = [p for p in ps.list_products("", incluir_inactivos=True) if p["name"] == "Normal"]
    assert len(inactive) == 1 and not inactive[0]["is_active"]


def test_boton_reactivar_vuelve_a_activar(temp_db):
    page, view = _make_view(temp_db)
    pid = ps.create_product("Dormido", 700)
    ps.desactivar_producto(pid)
    view.chk_inactivos.value = True
    view.load_data()
    _click(_row_button(view, "Dormido", "Reactivar"))
    _click(_dialog_button(_open_dialogs(page)[-1], "Sí"))
    assert any(p["id"] == pid for p in ps.list_products(""))


def test_boton_guardar_lista_es_async(temp_db):
    page = FakePage()
    view = ProductosView(page)
    guardar = view.controls[1].controls[1]
    assert guardar.content == "Guardar lista..."
    assert inspect.iscoroutinefunction(guardar.on_click)


def test_export_saves_to_chosen_path(temp_db, monkeypatch):
    page = FakePage()
    view = ProductosView(page)

    async def fake_save(self, **kwargs):
        assert kwargs.get("file_name") == "productos.csv"
        return "C:/Users/Usuario/Desktop/productos.csv"

    saved = {}
    monkeypatch.setattr(ft.FilePicker, "save_file", fake_save)
    monkeypatch.setattr(
        pbs, "export_products_csv", lambda path: saved.setdefault("path", path)
    )
    asyncio.run(view._export_csv())
    assert saved.get("path") == "C:/Users/Usuario/Desktop/productos.csv"
    assert any(
        isinstance(c, ft.AlertDialog) and "guardada" in c.content.value
        for c in page.overlay
    )


def test_pos_grilla_solo_aparece_al_buscar(temp_db):
    ps.create_product("Cerveza Rubia", 1500, barcode="7801", stock=50)
    ps.create_product("Cerveza Negra", 1800, barcode="7802", stock=50)
    page = FakePage()
    pos_main.main(page)
    root = page.controls[0]
    content_area = root.controls[1].controls[1].content
    main_col = content_area.controls[0]
    search_col = main_col.controls[0].content
    search_input = search_col.controls[0].controls[0]
    grid_box = search_col.controls[3]
    grid = grid_box.content

    # Al abrir, con el buscador vacio, no se muestra ningun producto.
    assert grid_box.visible is False
    assert grid.controls == []

    # Al escribir aparecen solo las coincidencias.
    search_input.value = "cerveza"
    search_input.on_change(None)
    assert grid_box.visible is True
    assert len(grid.controls) == 2

    # Sin coincidencias: grilla oculta y aviso de "Sin resultados".
    search_input.value = "xyzzy"
    search_input.on_change(None)
    assert grid_box.visible is False
    assert search_col.controls[2].visible is True
    assert "xyzzy" in search_col.controls[2].value

    # Tocar un resultado lo agrega, limpia el buscador y esconde la grilla.
    search_input.value = "negra"
    search_input.on_change(None)
    _click(grid.controls[0])
    assert search_input.value == ""
    assert grid_box.visible is False
    from core import ticket_service as ts
    names = [i["product_name"] for t in ts.list_open_tickets() for i in ts.list_items(t["id"])]
    assert names == ["Cerveza Negra"]


def _cobrar_una_venta(tmp_path, monkeypatch, email_enabled, with_page=False):
    """Escanea, cobra con 5.000 y devuelve (aviso de venta, boton Ultimo)."""
    from core import config as core_config
    from flet_app import boletas as bol

    # Config temporal: nunca se lee ni se escribe la config real del usuario.
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    bol.save_settings(smtp={"enabled": email_enabled})
    ps.create_product("Cerveza Rubia", 1500, barcode="7801", stock=50)
    page = FakePage()
    pos_main.main(page)
    root = page.controls[0]
    content_area = root.controls[1].controls[1].content
    search_input = content_area.controls[0].controls[0].content.controls[0].controls[0]
    summary_col = content_area.controls[1].controls[0].content
    cobrar = summary_col.controls[5]
    ultimo = summary_col.controls[7]
    assert ultimo.visible is False

    search_input.value = "7801"
    asyncio.run(search_input.on_submit(None))
    _click(cobrar)
    charge = _open_dialogs(page)[-1]
    recibido = next(
        c for c in charge.content.controls
        if isinstance(c, ft.TextField) and c.label == "Monto recibido"
    )
    recibido.value = "5000"
    recibido.on_change(None)
    asyncio.run(recibido.on_submit(None))

    if with_page:
        return _open_dialogs(page)[-1], ultimo, page
    return _open_dialogs(page)[-1], ultimo


def test_cobro_ofrece_imprimir_comprobante_sin_correo_por_defecto(temp_db, tmp_path, monkeypatch):
    done, ultimo = _cobrar_una_venta(tmp_path, monkeypatch, email_enabled=False)
    assert done.title.value == "Venta cobrada"
    assert "Vuelto: $3.500" in done.content.value
    assert [b.content for b in done.actions] == ["Guardar comprobante", "Imprimir", "Aceptar"]
    assert ultimo.visible is True


def test_cobro_ofrece_correo_si_esta_activado(temp_db, tmp_path, monkeypatch):
    done, _ultimo = _cobrar_una_venta(tmp_path, monkeypatch, email_enabled=True)
    assert [b.content for b in done.actions] == [
        "Guardar comprobante",
        "Imprimir",
        "Enviar por correo",
        "Aceptar",
    ]


def _avisos(page):
    return [c.content.value for c in _open_dialogs(page)]


def _cobrar_con_pagina(tmp_path, monkeypatch):
    """Como _cobrar_una_venta, pero devuelve (aviso de venta, pagina)."""
    done, _ultimo, page = _cobrar_una_venta(tmp_path, monkeypatch, email_enabled=False, with_page=True)
    return done, page


def test_venta_cobrada_no_tiene_boton_unico_imprimir_comprobante(temp_db, tmp_path, monkeypatch):
    done, _page = _cobrar_con_pagina(tmp_path, monkeypatch)
    labels = [b.content for b in done.actions]
    assert "Imprimir comprobante" not in labels
    assert "Guardar comprobante" in labels and "Imprimir" in labels
    assert inspect.iscoroutinefunction(_dialog_button(done, "Guardar comprobante").on_click)
    assert inspect.iscoroutinefunction(_dialog_button(done, "Imprimir").on_click)


def test_guardar_comprobante_en_ruta_elegida(temp_db, tmp_path, monkeypatch):
    from flet_app import boletas as bol

    done, page = _cobrar_con_pagina(tmp_path, monkeypatch)
    destino = str(tmp_path / "otra carpeta" / "mi_comprobante.pdf")
    (tmp_path / "otra carpeta").mkdir()
    pedido = {}

    async def fake_save(self, **kwargs):
        pedido.update(kwargs)
        return destino

    calls = []
    real_build = bol.build_pdf
    monkeypatch.setattr(ft.FilePicker, "save_file", fake_save)
    monkeypatch.setattr(bol, "build_pdf", lambda data, **kw: calls.append((data, kw)) or real_build(data, **kw))
    _click(_dialog_button(done, "Guardar comprobante"))

    assert pedido["file_name"].startswith("comprobante_") and pedido["file_name"].endswith(".pdf")
    assert len(calls) == 1 and calls[0][1]["path"] == destino
    assert (tmp_path / "otra carpeta" / "mi_comprobante.pdf").read_bytes().startswith(b"%PDF")
    assert f"Comprobante guardado en {destino}" in _avisos(page)


def test_guardar_comprobante_cancelado_no_genera_pdf(temp_db, tmp_path, monkeypatch):
    from flet_app import boletas as bol

    done, page = _cobrar_con_pagina(tmp_path, monkeypatch)

    async def fake_save(self, **kwargs):
        return None

    calls = []
    monkeypatch.setattr(ft.FilePicker, "save_file", fake_save)
    monkeypatch.setattr(bol, "build_pdf", lambda *a, **kw: calls.append(1))
    _click(_dialog_button(done, "Guardar comprobante"))

    assert calls == []
    assert not any("guardado" in t for t in _avisos(page))


def test_imprimir_con_exito_avisa_enviado(temp_db, tmp_path, monkeypatch):
    from flet_app import boletas as bol

    done, page = _cobrar_con_pagina(tmp_path, monkeypatch)
    impresos = []
    monkeypatch.setattr(bol, "print_receipt", lambda data, cfg: impresos.append(data))
    _click(_dialog_button(done, "Imprimir"))

    assert len(impresos) == 1 and impresos[0]["received"] == 5000
    assert any("enviado a imprimir." in t for t in _avisos(page))


@pytest.mark.parametrize("error", ["boleta", "otro"])
def test_imprimir_con_error_no_avisa_exito(temp_db, tmp_path, monkeypatch, error):
    from flet_app import boletas as bol

    done, page = _cobrar_con_pagina(tmp_path, monkeypatch)

    def falla(data, cfg):
        raise bol.BoletaError("sin papel") if error == "boleta" else OSError("cola caída")

    monkeypatch.setattr(bol, "print_receipt", falla)
    _click(_dialog_button(done, "Imprimir"))

    avisos = _avisos(page)
    assert any(t.startswith("No se pudo imprimir:") for t in avisos)
    assert not any("enviado a imprimir" in t for t in avisos)


def test_pdf_guardado_e_impreso_usan_los_mismos_datos(temp_db, tmp_path, monkeypatch):
    from flet_app import boletas as bol

    done, _page = _cobrar_con_pagina(tmp_path, monkeypatch)
    vistos = []

    async def fake_save(self, **kwargs):
        return str(tmp_path / "c.pdf")

    monkeypatch.setattr(ft.FilePicker, "save_file", fake_save)
    monkeypatch.setattr(bol, "print_receipt", lambda data, cfg: vistos.append(data))
    real_build = bol.build_pdf
    monkeypatch.setattr(bol, "build_pdf", lambda data, **kw: vistos.append(data) or real_build(data, **kw))
    _click(_dialog_button(done, "Guardar comprobante"))
    _click(_dialog_button(done, "Imprimir"))

    assert len(vistos) == 2 and vistos[0] == vistos[1]
