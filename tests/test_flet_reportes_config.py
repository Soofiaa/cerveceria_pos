"""Tests de Fase 3 de la app Flet: Reportes, Configuracion y temas.

Funciones REALES de flet_app.theme, flet_app.reportes_view,
flet_app.config_view, flet_app.main y core. Sin placeholders. La base es la
temporal (fixture temp_db) y la config se redirige a un archivo temporal.
"""

import asyncio
import json
import os
import types

import flet as ft
import pytest

from core import config as core_config
from core import sales_service as ss
from core import ticket_service as ts
from core import product_service as ps
from core import db_manager
from flet_app import main as pos_main
from flet_app import reportes_view as rv
from flet_app.config_view import ConfigView, PREFIXES
from flet_app.reportes_view import ReportesView, parse_range
from flet_app.theme import THEMES, get_theme

REQUIRED_KEYS = {
    "primary", "primary_text", "secondary", "background", "text", "accent",
    "danger", "warning", "success", "surface", "input_text",
    "surface2", "border", "icon", "warn_bg", "warn_text", "warn_badge",
    "disabled_bg", "disabled_text",
}


class RecordingWindow(types.SimpleNamespace):
    """Ventana falsa que anota cada escritura de atributo (como page.window de Flet)."""

    def __init__(self):
        object.__setattr__(self, "writes", [])
        super().__init__(
            width=1280, height=720, min_width=1000, min_height=650,
            maximized=False, minimized=False,
        )
        self.writes.clear()  # lo anterior es solo el estado inicial del doble

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


@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    """Config temporal: nunca se lee ni escribe la config real del usuario."""
    path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(path))
    return path


@pytest.fixture(autouse=True)
def _restore_palette():
    yield
    pos_main.apply_palette("lila")


def _cobrar(producto_id, qty, price):
    tid = ts.create_ticket(f"Ticket {_ticket_no()}")
    ts.add_item(tid, producto_id, qty, price)
    ts.set_pay_method(tid, "efectivo")
    sale_id, _ = ss.cobrar_ticket(tid)
    return sale_id


_TICKET_SEQ = {"n": 0}


def _ticket_no():
    _TICKET_SEQ["n"] += 1
    return _TICKET_SEQ["n"]


def _set_created_at(sale_id, stamp):
    with db_manager.get_conn() as con:
        con.execute("UPDATE sales SET created_at=? WHERE id=?", (stamp, sale_id))
        con.commit()


# ---------- 1. Temas ----------
@pytest.mark.parametrize("name", ["neutro", "cerveceria", "oscuro", "menta", "grafito", "lila"])
def test_cada_tema_tiene_todas_las_claves_de_la_app(name):
    missing = REQUIRED_KEYS - THEMES[name].keys()
    assert not missing, f"{name} sin claves: {missing}"


def test_seis_temas_exactos():
    assert set(THEMES) == {"neutro", "cerveceria", "oscuro", "menta", "grafito", "lila"}


def test_lila_conserva_los_valores_de_la_maqueta():
    t = THEMES["lila"]
    assert t["primary"] == "#6c3483"
    assert t["background"] == "#f6eff7"
    assert t["surface2"] == "#efe3f1"
    assert t["border"] == "#e2d0e6"
    assert t["danger"] == "#a93226"


def test_get_theme_fallback_a_lila():
    assert get_theme("no_existe") is THEMES["lila"]
    assert get_theme(None) is THEMES["lila"]
    assert get_theme("oscuro") is THEMES["oscuro"]


def test_flet_theme_no_importa_pyside():
    import ast
    import flet_app.theme as flet_theme
    with open(flet_theme.__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imports = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    imports += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(m.startswith("PySide6") for m in imports)


# ---------- 2. Config: prefijo Mesa y tema oscuro ----------
def test_guardar_y_cargar_config_con_mesa_y_oscuro(cfg_file):
    # Copia: sin archivo, load_config devuelve el dict compartido DEFAULT_CONFIG.
    cfg = dict(core_config.load_config())
    cfg.update(business_name="Cervecería Prueba", ticket_prefix="Mesa", theme="oscuro")
    core_config.save_config(cfg)
    back = core_config.load_config()
    assert back["business_name"] == "Cervecería Prueba"
    assert back["ticket_prefix"] == "Mesa"
    assert back["theme"] == "oscuro"
    assert json.loads(cfg_file.read_text(encoding="utf-8"))["theme"] == "oscuro"


def test_prefijos_validos():
    assert PREFIXES == ("Ticket", "Mesa")


def test_arranque_sin_theme_usa_lila(temp_db, cfg_file):
    cfg_file.write_text(json.dumps({"business_name": "X"}), encoding="utf-8")
    pos_main.main(FakePage())
    assert pos_main.PRIMARY == "#6c3483"


def test_arranque_sin_archivo_usa_lila(temp_db, cfg_file):
    assert not cfg_file.exists()
    pos_main.main(FakePage())
    assert pos_main.PRIMARY == "#6c3483"


def test_arranque_respeta_tema_guardado(temp_db, cfg_file):
    cfg_file.write_text(json.dumps({"theme": "oscuro"}), encoding="utf-8")
    pos_main.main(FakePage())
    assert pos_main.PRIMARY == THEMES["oscuro"]["primary"]
    assert pos_main.BG == THEMES["oscuro"]["background"]


# ---------- 3. Reportes: totales con ventas en la base temporal ----------
def test_reportes_totales_y_ticket_promedio(temp_db):
    p1 = ps.create_product("Rubia", 1500, stock=50)
    p2 = ps.create_product("Negra", 2000, stock=50)
    s1 = _cobrar(p1, 2, 1500)  # 3000
    s2 = _cobrar(p2, 1, 2000)  # 2000
    hoy = rv._iso(rv.date.today())
    _set_created_at(s1, f"{hoy} 10:00:00")
    _set_created_at(s2, f"{hoy} 11:00:00")

    view = ReportesView(FakePage(), get_theme("lila"))
    view.load_data()
    assert view.txt_total.value == "$5.000"
    assert view.txt_count.value == "2"
    assert view.txt_avg.value == "$2.500"
    assert len(view.sales_table.rows) == 2
    # Mas nuevas primero: la venta de las 11:00 va arriba.
    assert view.sales_table.rows[0].cells[1].content.value == f"{s2}"
    assert len(view.top_table.rows) == 2


def test_reportes_rango_sin_ventas_lo_dice(temp_db):
    view = ReportesView(FakePage(), get_theme("lila"))
    view.in_desde.value = "2020-01-01"
    view.in_hasta.value = "2020-01-01"
    view.load_data()
    assert view.txt_total.value == "$0"
    assert view.txt_count.value == "0"
    assert view.sales_table.rows == []
    assert "No hay ventas" in view.msg.value


def test_reportes_rango_invertido_no_consulta(temp_db):
    view = ReportesView(FakePage(), get_theme("lila"))
    view.in_desde.value = "2026-12-02"
    view.in_hasta.value = "2026-12-01"
    view.load_data()
    assert "posterior" in view.msg.value
    assert view.txt_total.value == "$0"


def test_parse_range_vacio_es_hoy():
    hoy = rv._iso(rv.date.today())
    assert parse_range("", "") == (hoy, hoy)


def test_parse_range_formato_invalido():
    with pytest.raises(ValueError):
        parse_range("19/11/2026", "")


def test_reportes_muestra_ganancia_y_margen():
    view = ReportesView(FakePage(), get_theme("lila"))
    textos = []

    def walk(c):
        if isinstance(c, ft.Text):
            textos.append(c.value or "")
        for attr in ("controls", "content"):
            v = getattr(c, attr, None)
            if isinstance(v, list):
                for x in v:
                    walk(x)
            elif v is not None and not isinstance(v, str):
                walk(v)

    walk(view)
    assert any("ganancia" in t.lower() for t in textos)
    assert any("margen" in t.lower() for t in textos)


def test_exportar_csv_escribe_ventas(temp_db, tmp_path):
    p1 = ps.create_product("Rubia", 1500, stock=50)
    s1 = _cobrar(p1, 1, 1500)
    hoy = rv._iso(rv.date.today())
    _set_created_at(s1, f"{hoy} 09:00:00")
    view = ReportesView(FakePage(), get_theme("lila"))
    destino = tmp_path / "ventas.csv"
    view._save_csv_to(str(destino), hoy, hoy)
    contenido = destino.read_text(encoding="utf-8-sig")
    assert "N° venta" in contenido.splitlines()[0]
    assert f"{s1}" in contenido


# ---------- 4. Navegacion ----------
def _pestanas(page):
    top_bar = page.controls[0].controls[0]
    return {c.content.controls[1].value: c for c in top_bar.content.controls
            if isinstance(c, ft.Container) and isinstance(c.content, ft.Row)}


def _area(page):
    body = page.controls[0].controls[1]
    return body.controls[1].content


def test_navegacion_a_reportes(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    tabs = _pestanas(page)
    asyncio.run(tabs["Reportes"].on_click(None))
    area = _area(page)
    assert len(area.controls) == 1
    assert isinstance(area.controls[0].content.controls[1], ReportesView)


def test_navegacion_a_configuracion(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    tabs = _pestanas(page)
    asyncio.run(tabs["Configuración"].on_click(None))
    area = _area(page)
    assert len(area.controls) == 1
    assert isinstance(area.controls[0].content, ConfigView)


def test_ir_a_reportes_no_reconstruye_el_ticket(temp_db, cfg_file):
    ps.create_product("Rubia", 1500, barcode="7801", stock=50)
    page = FakePage()
    pos_main.main(page)
    tid_before = ts.list_open_tickets()[0]["id"]
    tabs = _pestanas(page)
    asyncio.run(tabs["Reportes"].on_click(None))
    asyncio.run(tabs["POS"].on_click(None))
    assert ts.list_open_tickets()[0]["id"] == tid_before


# ---------- 5. Aplicar tema cambia la paleta de main ----------
def test_aplicar_tema_cambia_paleta_de_main(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    assert pos_main.PRIMARY == THEMES["lila"]["primary"]
    pos_main.apply_palette("menta")
    assert pos_main.PRIMARY == THEMES["menta"]["primary"]
    assert pos_main.BG == THEMES["menta"]["background"]
    assert pos_main.ERROR == THEMES["menta"]["danger"]


def test_boton_tema_repinta_y_guarda(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    asyncio.run(_pestanas(page)["Configuración"].on_click(None))
    view = _area(page).controls[0].content
    boton = next(b for b in view.theme_row.controls if b.content == "Oscuro")
    boton.on_click(None)
    assert pos_main.PRIMARY == THEMES["oscuro"]["primary"]
    assert json.loads(cfg_file.read_text(encoding="utf-8"))["theme"] == "oscuro"


def test_cambio_de_tema_conserva_busqueda_y_ticket(temp_db, cfg_file):
    ps.create_product("Rubia", 1500, barcode="7801", stock=50)
    page = FakePage()
    pos_main.main(page)
    tid = ts.list_open_tickets()[0]["id"]
    ts.add_item(tid, ps.find_product_by_exact_code_or_name("7801")["id"], 1, 1500)
    tabs = _pestanas(page)
    asyncio.run(tabs["Configuración"].on_click(None))
    view = _area(page).controls[0].content
    next(b for b in view.theme_row.controls if b.content == "Grafito").on_click(None)
    assert len(ts.list_items(tid)) == 1
    assert ts.list_open_tickets()[0]["id"] == tid


# ---------- 6. Bugs corregidos: DatePicker y Dropdown ----------
def test_datepicker_se_abre_con_show_dialog(temp_db, cfg_file):
    page = FakePage()
    shown = []
    page.show_dialog = lambda d: shown.append(d)
    view = ReportesView(page, get_theme("lila"))
    view._open_dp_desde()
    assert shown == [view.dp_desde]
    assert view.dp_desde not in page.overlay


def test_dropdowns_de_configuracion_usan_on_select(temp_db, cfg_file):
    view = ConfigView(FakePage(), get_theme("lila"), lambda n: None, lambda c: None)
    assert view.dd_prefix.on_select is not None
    assert view.dd_mode.on_select is not None


# ---------- 7. Reconstruccion por cambio de tema: estado conservado ----------
def _search_input(page):
    area = _area(page)
    return area.controls[0].controls[0].content.controls[0].controls[0]


def test_cambio_de_tema_conserva_busqueda_ticket_y_vista(temp_db, cfg_file):
    ps.create_product("Rubia", 1500, barcode="7801", stock=50)
    page = FakePage()
    pos_main.main(page)
    tid = ts.list_open_tickets()[0]["id"]
    ts.add_item(tid, ps.find_product_by_exact_code_or_name("7801")["id"], 1, 1500)
    _search_input(page).value = "rub"
    asyncio.run(_pestanas(page)["Configuración"].on_click(None))
    view = _area(page).controls[0].content
    view.in_name.value = "Escrito sin guardar"
    next(b for b in view.theme_row.controls if b.content == "Grafito").on_click(None)

    # La interfaz se reconstruyo con la paleta nueva y la misma vista.
    assert pos_main.PRIMARY == THEMES["grafito"]["primary"]
    new_view = _area(page).controls[0].content
    assert isinstance(new_view, ConfigView) and new_view is not view
    assert new_view.in_name.value == "Escrito sin guardar"
    # El ticket no se toco en la base.
    assert [t["id"] for t in ts.list_open_tickets()] == [tid]
    assert len(ts.list_items(tid)) == 1
    # La busqueda sigue escrita en el POS nuevo.
    asyncio.run(_pestanas(page)["POS"].on_click(None))
    assert _search_input(page).value == "rub"


def test_cambio_de_tema_conserva_rango_de_reportes(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    asyncio.run(_pestanas(page)["Reportes"].on_click(None))
    rep = _area(page).controls[0].content.controls[1]
    rep.in_desde.value = "2026-11-01"
    rep.in_hasta.value = "2026-11-05"
    asyncio.run(_pestanas(page)["Configuración"].on_click(None))
    next(b for b in _area(page).controls[0].content.theme_row.controls if b.content == "Menta").on_click(None)
    asyncio.run(_pestanas(page)["Reportes"].on_click(None))
    rep2 = _area(page).controls[0].content.controls[1]
    assert (rep2.in_desde.value, rep2.in_hasta.value) == ("2026-11-01", "2026-11-05")


def test_tema_oscuro_pide_modo_oscuro(temp_db, cfg_file):
    cfg_file.write_text(json.dumps({"theme": "oscuro"}), encoding="utf-8")
    page = FakePage()
    pos_main.main(page)
    assert page.theme_mode == ft.ThemeMode.DARK
    cfg_file.write_text(json.dumps({"theme": "lila"}), encoding="utf-8")
    pos_main.main(page)
    assert page.theme_mode == ft.ThemeMode.LIGHT


# ---------- 8. Prefijo de ticket ----------
def test_ticket_nuevo_usa_prefijo_mesa_con_numero_libre_mas_bajo(temp_db, cfg_file):
    cfg_file.write_text(json.dumps({"ticket_prefix": "Mesa"}), encoding="utf-8")
    ts.create_ticket("Mesa 1")
    ts.create_ticket("Mesa 3")
    ts.create_ticket("Ticket 2")  # otro prefijo: no ocupa numero de Mesa
    assert pos_main.new_ticket_name() == "Mesa 2"


def test_ticket_nuevo_prefijo_por_defecto_y_invalido(temp_db, cfg_file):
    assert pos_main.new_ticket_name() == "Ticket 1"
    cfg_file.write_text(json.dumps({"ticket_prefix": "Otro"}), encoding="utf-8")
    assert pos_main.new_ticket_name() == "Ticket 1"


def test_boton_nuevo_ticket_crea_mesa(temp_db, cfg_file):
    cfg_file.write_text(json.dumps({"ticket_prefix": "Mesa"}), encoding="utf-8")
    page = FakePage()
    pos_main.main(page)  # crea el primer ticket abierto
    tickets_box = page.controls[0].controls[1].controls[0]
    nuevo = tickets_box.content.controls[2]
    asyncio.run(nuevo.on_click(None))
    nombres = sorted(t["name"] for t in ts.list_open_tickets())
    assert "Mesa 2" in nombres


# ---------- 9. M1: el selector de prefijo tiene nombre accesible ----------
def test_selector_de_prefijo_tiene_nombre_accesible(temp_db, cfg_file):
    view = ConfigView(FakePage(), get_theme("lila"), lambda n: None, lambda c: None)
    # Flet publica `tooltip` como etiqueta de accesibilidad del desplegable:
    # sin el, el lector de pantalla ve un boton sin nombre.
    assert view.dd_prefix.tooltip == "Prefijo de ticket"
    assert view.dd_prefix.label == "Prefijo de ticket"


# ---------- 10. M2: fecha invalida = aviso amigable, sin error crudo ----------
@pytest.mark.parametrize("texto", ["19/11/2026", "hola", "2026-02-30", "2026-13-01", "2026-1-5x"])
def test_fecha_invalida_da_mensaje_amigable(texto):
    with pytest.raises(ValueError) as exc:
        parse_range(texto, "")
    msg = str(exc.value)
    assert "AAAA-MM-DD" in msg and texto in msg and "Desde" in msg
    # Nada de texto tecnico de Python en lo que ve la cajera.
    assert "unconverted" not in msg and "strptime" not in msg and "does not match" not in msg


def test_fecha_invalida_en_hasta_nombra_el_campo_hasta():
    with pytest.raises(ValueError, match="Hasta"):
        parse_range("2026-11-01", "mañana")


def test_rango_invertido_mensaje_amigable_con_las_fechas():
    with pytest.raises(ValueError) as exc:
        parse_range("2026-11-19", "2026-11-01")
    assert "2026-11-19" in str(exc.value) and "2026-11-01" in str(exc.value)


def test_fecha_invalida_avisa_en_pantalla_y_vacia_los_resultados(temp_db):
    p1 = ps.create_product("Rubia", 1500, stock=50)
    s1 = _cobrar(p1, 2, 1500)
    hoy = rv._iso(rv.date.today())
    _set_created_at(s1, f"{hoy} 10:00:00")
    page = FakePage()
    view = ReportesView(page, get_theme("lila"))
    view.load_data()
    assert view.txt_total.value == "$3.000"

    view.in_desde.value = "19/11/2026"
    view.load_data()
    assert "no es válida" in view.msg.value and "AAAA-MM-DD" in view.msg.value
    assert view.msg.color == THEMES["lila"]["danger"]
    # No queda el total anterior a la vista como si fuera de las fechas escritas.
    assert view.txt_total.value == "$0" and view.txt_count.value == "0"
    assert view.sales_table.rows == [] and view.top_table.rows == []
    assert page.updates > 0

    # Corregir la fecha vuelve a mostrar los datos y quita el aviso.
    view.in_desde.value = hoy
    view.load_data()
    assert view.txt_total.value == "$3.000" and view.msg.value == ""


def test_exportar_con_fecha_invalida_muestra_aviso_y_no_abre_selector(temp_db):
    page = FakePage()
    view = ReportesView(page, get_theme("lila"))
    view.in_desde.value = "abc"
    asyncio.run(view._export_csv())
    dialogos = [c for c in page.overlay if isinstance(c, ft.AlertDialog)]
    assert len(dialogos) == 1 and "AAAA-MM-DD" in dialogos[0].content.value


# ---------- 11. M2: el DatePicker elige fecha y actualiza el rango ----------
def test_datepicker_elegir_fecha_actualiza_el_rango(temp_db):
    p1 = ps.create_product("Rubia", 1500, stock=50)
    s1 = _cobrar(p1, 1, 1500)
    _set_created_at(s1, "2026-11-05 12:00:00")
    view = ReportesView(FakePage(), get_theme("lila"))
    view.in_hasta.value = "2026-11-30"
    view.dp_desde.value = rv.datetime(2026, 11, 5)
    view.dp_desde.on_change(None)
    assert view.in_desde.value == "2026-11-05"
    assert view.txt_total.value == "$1.500" and view.txt_count.value == "1"

    view.dp_hasta.value = rv.datetime(2026, 11, 4)
    view.dp_hasta.on_change(None)
    assert view.in_hasta.value == "2026-11-04"
    assert "posterior" in view.msg.value  # 05 > 04: rango invertido avisa


def test_boton_calendario_abre_datepicker_con_show_dialog(temp_db):
    page = FakePage()
    abiertos = []
    page.show_dialog = abiertos.append
    view = ReportesView(page, get_theme("lila"))
    fila = view.controls[0]
    botones = [c for c in fila.controls if isinstance(c, ft.IconButton)]
    assert len(botones) == 2
    botones[0].on_click(None)
    botones[1].on_click(None)
    assert abiertos == [view.dp_desde, view.dp_hasta]
    assert view.dp_desde not in page.overlay and view.dp_hasta not in page.overlay


# ---------- 12. El cambio de tema no toca el tamano ni el maximizado de la ventana ----------
SIZE_ATTRS = {"width", "height", "min_width", "min_height", "maximized", "minimized"}


def _pick_theme(page, label):
    """Va a Configuracion y pulsa el boton de tema, como lo hace la cajera."""
    asyncio.run(_pestanas(page)["Configuración"].on_click(None))
    view = _area(page).controls[0].content
    next(b for b in view.theme_row.controls if b.content == label).on_click(None)


def test_primer_arranque_fija_tamano_inicial_de_la_ventana(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    w = page.window
    assert (w.width, w.height, w.min_width, w.min_height) == (1280, 720, 1000, 650)
    assert w.maximized is False


def test_cambio_de_tema_conserva_ventana_maximizada(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    page.window.maximized = True        # la cajera maximiza
    page.window.width, page.window.height = 1920, 1040  # tamano que Flet reporta maximizado
    page.window.writes.clear()

    _pick_theme(page, "Oscuro")

    assert pos_main.PRIMARY == THEMES["oscuro"]["primary"]   # el tema si cambio
    assert page.window.maximized is True
    assert (page.window.width, page.window.height) == (1920, 1040)
    assert not [w for w in page.window.writes if w[0] in SIZE_ATTRS]


def test_cambio_de_tema_conserva_el_tamano_que_puso_la_cajera(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    page.window.width, page.window.height = 1500, 860   # redimensionada a mano
    page.window.writes.clear()

    _pick_theme(page, "Menta")

    assert pos_main.PRIMARY == THEMES["menta"]["primary"]
    assert (page.window.width, page.window.height) == (1500, 860)
    assert page.window.maximized is False
    assert (page.window.min_width, page.window.min_height) == (1000, 650)
    assert not [w for w in page.window.writes if w[0] in SIZE_ATTRS]


def test_varios_cambios_de_tema_seguidos_no_tocan_la_ventana(temp_db, cfg_file):
    page = FakePage()
    pos_main.main(page)
    page.window.maximized = True
    page.window.width, page.window.height = 1920, 1040
    page.window.writes.clear()

    for label in ("Oscuro", "Grafito", "Neutro", "Lila"):
        _pick_theme(page, label)

    assert pos_main.PRIMARY == THEMES["lila"]["primary"]
    assert page.window.maximized is True
    assert (page.window.width, page.window.height) == (1920, 1040)
    assert not [w for w in page.window.writes if w[0] in SIZE_ATTRS]


def test_cambio_de_tema_no_toca_otros_datos_al_conservar_la_ventana(temp_db, cfg_file):
    """El arreglo solo afecta a la ventana: ticket, busqueda y tema siguen igual que antes."""
    ps.create_product("Rubia", 1500, barcode="7801", stock=50)
    page = FakePage()
    pos_main.main(page)
    tid = ts.list_open_tickets()[0]["id"]
    _search_input(page).value = "rub"
    page.window.maximized = True

    _pick_theme(page, "Grafito")

    assert [t["id"] for t in ts.list_open_tickets()] == [tid]
    assert json.loads(cfg_file.read_text(encoding="utf-8"))["theme"] == "grafito"
    asyncio.run(_pestanas(page)["POS"].on_click(None))
    assert _search_input(page).value == "rub"
    assert page.window.maximized is True
