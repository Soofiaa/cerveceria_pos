# tests/test_ticket_service.py
import pytest

from core import product_service as ps
from core import ticket_service as ts


def test_add_item_acumula_cantidad_en_una_sola_linea(temp_db):
    """
    Agregar el mismo product_id (mismo unit_price) dos veces no debe crear
    dos líneas: debe acumular la cantidad en la línea existente.
    """
    pid = ps.create_product("IPA", 2500, 1200, stock=20)
    tid = ts.create_ticket()

    ts.add_item(tid, pid, qty=2, unit_price=2500)
    ts.add_item(tid, pid, qty=3, unit_price=2500)

    items = ts.list_items(tid)
    assert len(items) == 1
    assert items[0]["qty"] == 5
    assert items[0]["product_id"] == pid

    ticket = ts.get_ticket(tid)
    assert ticket["pending_total"] == 5 * 2500


def test_update_item_qty_a_cero_elimina_la_linea(temp_db):
    pid = ps.create_product("Stout", 3000, 1500, stock=10)
    tid = ts.create_ticket()
    line_id = ts.add_item(tid, pid, qty=2, unit_price=3000)

    ts.update_item_qty(line_id, 0)

    assert ts.list_items(tid) == []
    ticket = ts.get_ticket(tid)
    assert ticket["pending_total"] == 0


def test_update_item_qty_negativa_tambien_elimina_la_linea(temp_db):
    """
    El código actual no trata la cantidad negativa como un caso aparte:
    'if new_qty <= 0' cubre 0 y negativos con la misma rama (borra la
    línea). Se verifica explícitamente en vez de asumir que se comporta
    igual que con 0.
    """
    pid = ps.create_product("Stout", 3000, 1500, stock=10)
    tid = ts.create_ticket()
    line_id = ts.add_item(tid, pid, qty=2, unit_price=3000)

    ts.update_item_qty(line_id, -5)

    assert ts.list_items(tid) == []
    ticket = ts.get_ticket(tid)
    assert ticket["pending_total"] == 0


def test_add_item_cantidad_invalida_lanza_value_error(temp_db):
    pid = ps.create_product("IPA", 2500, 1200)
    tid = ts.create_ticket()

    with pytest.raises(ValueError):
        ts.add_item(tid, pid, qty=0, unit_price=2500)


def test_add_item_precio_negativo_lanza_value_error(temp_db):
    pid = ps.create_product("IPA", 2500, 1200)
    tid = ts.create_ticket()

    with pytest.raises(ValueError):
        ts.add_item(tid, pid, qty=1, unit_price=-100)


def test_add_common_item_cantidad_invalida_lanza_value_error(temp_db):
    tid = ts.create_ticket()

    with pytest.raises(ValueError):
        ts.add_common_item(tid, "Item libre", qty=0, unit_price=1000)


def test_add_common_item_precio_cero_lanza_value_error(temp_db):
    """
    A diferencia de add_item() (que permite unit_price == 0), add_common_item()
    exige unit_price > 0 estricto: 'if qty <= 0 or unit_price <= 0'. Es una
    asimetría real entre ambas funciones, no un error de este test.
    """
    tid = ts.create_ticket()

    with pytest.raises(ValueError):
        ts.add_common_item(tid, "Item libre", qty=1, unit_price=0)
