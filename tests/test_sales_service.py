# tests/test_sales_service.py
import pytest

from core import product_service as ps
from core import ticket_service as ts
from core import sales_service as ss


def test_cobrar_ticket_convierte_ticket_en_venta_coherente(temp_db):
    pid1 = ps.create_product("IPA", 2500, 1200, stock=10)
    pid2 = ps.create_product("Stout", 3000, 1500, stock=10)

    tid = ts.create_ticket("Mesa 1")
    ts.add_item(tid, pid1, qty=2, unit_price=2500)
    ts.add_item(tid, pid2, qty=1, unit_price=3000)
    ts.set_pay_method(tid, "efectivo")

    sale_id, stock_warnings = ss.cobrar_ticket(tid)

    assert stock_warnings == []

    # El ticket abierto ya no debe existir
    assert ts.get_ticket(tid) is None

    # sale_items debe reflejar exactamente lo que había en el ticket
    items = ss.items_de_venta(sale_id)
    items_by_name = {it["product_name"]: it for it in items}

    assert set(items_by_name.keys()) == {"IPA", "Stout"}

    assert items_by_name["IPA"]["qty"] == 2
    assert items_by_name["IPA"]["unit_price"] == 2500
    assert items_by_name["IPA"]["line_total"] == 5000

    assert items_by_name["Stout"]["qty"] == 1
    assert items_by_name["Stout"]["unit_price"] == 3000
    assert items_by_name["Stout"]["line_total"] == 3000

    # El total de la venta debe coincidir con la suma de sale_items
    ventas_hoy = ss.ventas_del_dia()
    venta = next(v for v in ventas_hoy if v["id"] == sale_id)
    assert venta["total"] == 5000 + 3000
    assert venta["pay_method"] == "efectivo"
    assert venta["status"] == "pagada"

    # El stock debe haberse descontado
    assert ps.get_product(pid1)["stock"] == 10 - 2
    assert ps.get_product(pid2)["stock"] == 10 - 1


def test_cobrar_ticket_ticket_inexistente_lanza_value_error(temp_db):
    with pytest.raises(ValueError):
        ss.cobrar_ticket(999999)


def test_cobrar_ticket_sin_items_lanza_value_error(temp_db):
    tid = ts.create_ticket("Vacío")
    with pytest.raises(ValueError):
        ss.cobrar_ticket(tid)


def test_cobrar_ticket_permite_stock_negativo_y_avisa(temp_db):
    """
    Vender más de lo que hay en stock no debe bloquear la venta (decisión
    de diseño de la Fase 5): el stock queda negativo y cobrar_ticket()
    devuelve el detalle en su segundo valor de retorno.
    """
    pid = ps.create_product("IPA", 2500, 1200, stock=3)
    tid = ts.create_ticket()
    ts.add_item(tid, pid, qty=5, unit_price=2500)
    ts.set_pay_method(tid, "efectivo")

    sale_id, stock_warnings = ss.cobrar_ticket(tid)

    assert sale_id is not None
    assert len(stock_warnings) == 1
    assert stock_warnings[0]["product_name"] == "IPA"
    assert stock_warnings[0]["stock_resultante"] == -2
    assert ps.get_product(pid)["stock"] == -2


def test_cobrar_ticket_producto_comun_no_descuenta_stock(temp_db):
    tid = ts.create_ticket()
    ts.add_common_item(tid, "Servicio", qty=1, unit_price=1000)
    ts.set_pay_method(tid, "efectivo")

    sale_id, stock_warnings = ss.cobrar_ticket(tid)

    assert stock_warnings == []
    common = next(p for p in ps.list_products("Producto común") if p["name"] == "Producto común")
    assert common["stock"] == 0
