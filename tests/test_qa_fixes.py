# tests/test_qa_fixes.py
# Tests de regresión para las correcciones de la Fase 4 (QA-informe.md).
# Lógica a nivel de servicio: no dependen de Qt ni de la ventana.
import inspect
import sqlite3

import pytest

from core import product_service as ps
from core import ticket_service as ts
from core import sales_service as ss


# ---------- G1: búsqueda exacta antes que LIKE ----------

def test_g1_codigo_exacto_gana_a_codigo_que_lo_contiene(temp_db):
    # QA777 es el código exacto de "QA Test Cerveza"; "QA7771" lo contiene.
    exacto = ps.create_product("QA Test Cerveza", 1000, barcode="QA777")
    ps.create_product("Agua QA", 500, barcode="QA7771")

    found = ps.find_product_by_exact_code_or_name("QA777")

    assert found is not None
    assert found["id"] == exacto
    assert found["name"] == "QA Test Cerveza"


def test_g1_sin_coincidencia_exacta_devuelve_none(temp_db):
    ps.create_product("Agua QA", 500, barcode="QA7771")

    # "QA777" no es ni código ni nombre exacto: no debe adivinar.
    assert ps.find_product_by_exact_code_or_name("QA777") is None


def test_g1_add_item_by_search_no_usa_cand0_ciegamente():
    # Guarda estructural: la rama de LIKE no debe tomar cand[0] sin mirar
    # si hay varios candidatos. Debe haber una comprobación len(cand) > 1.
    from ui.pos.pos_search import POSSearchMixin

    src = inspect.getsource(POSSearchMixin.add_item_by_search)
    assert "find_product_by_exact_code_or_name" in src
    assert "len(cand) > 1" in src
    assert "cand[0]" in src  # solo tras la comprobación de un único candidato
    assert src.index("len(cand) > 1") < src.index("cand[0]")


# ---------- M7: barcode repetido da mensaje en español, crear Y editar ----------

MSG_BARCODE = "Ya existe un producto con ese código de barras."


def test_m7_crear_con_barcode_repetido_lanza_valueerror_en_espanol(temp_db):
    ps.create_product("Uno", 100, barcode="123")

    with pytest.raises(ValueError) as exc:
        ps.create_product("Dos", 200, barcode="123")

    assert str(exc.value) == MSG_BARCODE


def test_m7_editar_con_barcode_repetido_lanza_valueerror_en_espanol(temp_db):
    ps.create_product("Uno", 100, barcode="111")
    dos = ps.create_product("Dos", 200, barcode="222")

    with pytest.raises(ValueError) as exc:
        ps.update_product(dos, barcode="111")

    assert str(exc.value) == MSG_BARCODE
    # El fallo no debe haber cambiado el producto.
    assert ps.get_product(dos)["barcode"] == "222"


def test_m7_no_lanza_error_al_editar_conservando_su_propio_barcode(temp_db):
    pid = ps.create_product("Uno", 100, barcode="555")
    # Reenviar el mismo código no es un duplicado.
    ps.update_product(pid, name="Uno editado", barcode="555")
    assert ps.get_product(pid)["name"] == "Uno editado"


# ---------- M5: Desde > Hasta se rechaza ----------

def test_m5_load_data_avisa_si_desde_mayor_que_hasta():
    # Se valida antes de calcular summary(): el aviso es la rama de guardia.
    from ui.reports.actions import ReportActionsMixin

    src = inspect.getsource(ReportActionsMixin.load_data)
    assert "d1 > d2" in src
    assert "La fecha Desde debe ser anterior a Hasta" in src
    assert src.index("d1 > d2") < src.index("summary(d1, d2)")


# ---------- G3 / G4: a nivel de servicio ----------

def test_g3_add_item_devuelve_linea_que_luego_se_puede_editar(temp_db):
    # La selección de G3 se apoya en que el line_id devuelto por add_item
    # identifique la línea real del ticket.
    tid = ts.create_ticket()
    a = ts.add_item(tid, ps.create_product("A", 100), qty=1, unit_price=100)
    b = ts.add_item(tid, ps.create_product("B", 200), qty=1, unit_price=200)

    assert a != b
    ts.update_item_qty(b, 3)
    qtys = {it["id"]: it["qty"] for it in ts.list_items(tid)}
    assert qtys[b] == 3
    assert qtys[a] == 1


def test_g4_remove_item_borra_solo_la_linea_pedida(temp_db):
    # Guarda de servicio para la ✕ y Supr: borrar una línea no toca las demás.
    tid = ts.create_ticket()
    a = ts.add_item(tid, ps.create_product("A", 100), qty=1, unit_price=100)
    b = ts.add_item(tid, ps.create_product("B", 200), qty=1, unit_price=200)

    ts.remove_item(a)

    ids = [it["id"] for it in ts.list_items(tid)]
    assert ids == [b]


def test_g4_pos_actions_no_vacia_sin_confirmacion():
    # La confirmación vive en la capa de UI: se comprueba que clear_ticket_items
    # pregunta antes de llamar a remove_item.
    from ui.pos.pos_actions import POSActionsMixin

    src = inspect.getsource(POSActionsMixin.clear_ticket_items)
    assert "QMessageBox.question" in src
    assert src.index("QMessageBox.question") < src.index("remove_item")


def test_g4_columna_x_usa_el_camino_con_confirmacion():
    # La ✕ no debe llamar a ts.remove_item directo: debe pasar por _delete_current_row.
    from ui.pos.pos_view import POSView

    src = inspect.getsource(POSView._on_table_cell_clicked)
    assert "_delete_current_row" in src
    assert "ts.remove_item" not in src


def test_g2_supr_solo_actua_con_foco_en_tabla():
    # Supr en el buscador debe escribir/borrar texto, no quitar líneas.
    from ui.pos.pos_view import POSView

    src = inspect.getsource(POSView._on_delete_shortcut)
    assert "self.table.hasFocus()" in src
    assert src.index("self.table.hasFocus()") < src.index("_delete_current_row()")


# ---------- Grafito: contraste de primario y texto ----------

def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_grafito_primario_se_distingue_del_fondo_y_texto_legible():
    from ui.theme import THEMES

    g = THEMES["grafito"]
    # COBRAR / fila seleccionada: el primario debe contrastar con el fondo
    # (antes era 1.8:1, casi invisible).
    assert _contrast(g["primary"], g["background"]) >= 3.0
    # Y el texto sobre el primario debe seguir legible (WCAG AA).
    assert _contrast(g["primary_text"], g["primary"]) >= 4.5


# ---------- M6: ModernDateEdit usa tokens del tema, no #ffffff fijo ----------

def test_m6_modern_date_edit_no_tiene_blanco_fijo():
    from ui import reports_view
    from ui.theme import build_stylesheet

    src = inspect.getsource(reports_view.ModernDateEdit.__init__)
    assert "#ffffff" not in src
    assert "#d1d5db" not in src
    assert "QDateEdit" in build_stylesheet("neutro")
