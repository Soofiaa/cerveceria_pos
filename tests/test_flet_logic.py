"""Pruebas de la logica pura de flet_app/main.py (funciones REALES, no copias).

Importar flet_app.main no abre ventana: ft.run(main) esta bajo
if __name__ == "__main__".
"""
from core import product_service as ps
from core import ticket_service as ts
from flet_app.main import (
    PAY_METHODS,
    cash_status,
    charge_summary,
    find_empty_ticket,
    find_product,
    fmt_money,
    get_next_ticket_number,
    items_total,
    low_stock_remaining,
    parse_price,
    search_grid_products,
)


def test_get_next_ticket_number(temp_db):
    assert get_next_ticket_number() == 1
    ts.create_ticket("Ticket 1")
    assert get_next_ticket_number() == 2
    ts.create_ticket("Ticket 3")
    assert get_next_ticket_number() == 2
    ts.create_ticket("Ticket 2")
    assert get_next_ticket_number() == 4


def test_get_next_ticket_number_ignora_nombres_libres(temp_db):
    ts.create_ticket("Mesa 5")
    ts.create_ticket("Ticket x")
    assert get_next_ticket_number() == 1


def test_parse_price_como_qt():
    assert parse_price("1.000") == 1000
    assert parse_price("$1.000") == 1000
    assert parse_price("1,000") == 1000
    assert parse_price("") == 0
    assert parse_price(None) == 0
    assert parse_price("abc") == 0


def test_fmt_money():
    assert fmt_money(1500) == "$1.500"
    assert fmt_money(0) == "$0"
    assert fmt_money(-800) == "-$800"


def test_cash_status():
    assert cash_status(200, "") == (False, "")
    assert cash_status(200, "1000") == (True, "Vuelto: $800")
    assert cash_status(200, "$1.000") == (True, "Vuelto: $800")
    assert cash_status(1000, "200") == (False, "Faltan $800.")
    assert cash_status(200, "200") == (True, "Vuelto: $0")


def test_charge_summary_incluye_vuelto_y_stock():
    warns = [{"product_name": "P1"}]
    assert charge_summary(4, "efectivo", 800, warns) == "Venta 4 cobrada. Vuelto: $800. Stock negativo: P1"
    assert charge_summary(5, "credito", 0, []) == "Venta 5 cobrada."


def test_medios_de_pago_iguales_a_qt():
    assert [v for v, _ in PAY_METHODS] == ["efectivo", "credito", "debito", "transferencia"]


def _productos():
    ps.create_product(name="Cerveza Rubia", sale_price=1500, barcode="7801", stock=50, min_stock=5)
    ps.create_product(name="Cerveza Negra", sale_price=1800, barcode="7802", stock=50, min_stock=5)
    ps.create_product(name="Producto común", sale_price=0)


def test_find_product_casos(temp_db):
    _productos()
    kind, p = find_product("7801")
    assert kind == "one" and p["name"] == "Cerveza Rubia"
    kind, p = find_product("Cerveza Negra")
    assert kind == "one" and p["name"] == "Cerveza Negra"
    kind, cand = find_product("cerveza")
    assert kind == "many" and len(cand) == 2
    assert find_product("xyzzy") == ("none", None)
    assert find_product("   ") == ("empty", None)


def test_find_product_excluye_producto_comun(temp_db):
    _productos()
    assert find_product("Producto común") == ("none", None)
    # "com" solo coincide con Producto común: no se agrega solo.
    assert find_product("com") == ("none", None)


def test_items_total_y_find_empty_ticket(temp_db):
    _productos()
    rubia = ps.find_product_by_exact_code_or_name("7801")
    t1 = ts.create_ticket("Ticket 1")
    t2 = ts.create_ticket("Ticket 2")
    ts.add_item(t1, rubia["id"], 2, rubia["sale_price"])
    assert items_total(ts.list_items(t1)) == 3000
    assert find_empty_ticket() == t2
    assert find_empty_ticket(exclude_id=t2) is None


def test_low_stock_remaining(temp_db):
    ps.create_product(name="Poca", sale_price=100, stock=3, min_stock=2)
    prod = ps.find_product_by_exact_code_or_name("Poca")
    tid = ts.create_ticket("Ticket 1")
    ts.add_item(tid, prod["id"], 1, 100)
    assert low_stock_remaining(prod, ts.list_items(tid)) == 2
    ps.create_product(name="Mucha", sale_price=100, stock=50, min_stock=2)
    mucha = ps.find_product_by_exact_code_or_name("Mucha")
    ts.add_item(tid, mucha["id"], 1, 100)
    assert low_stock_remaining(mucha, ts.list_items(tid)) is None


def test_search_grid_products_vacio_no_muestra_nada(temp_db):
    _productos()
    assert search_grid_products("") == ([], 0)
    assert search_grid_products("   ") == ([], 0)
    assert search_grid_products(None) == ([], 0)


def test_search_grid_products_filtra_y_excluye_comun(temp_db):
    _productos()
    shown, total = search_grid_products("cerveza")
    assert total == 2
    assert sorted(p["name"] for p in shown) == ["Cerveza Negra", "Cerveza Rubia"]
    assert search_grid_products("7802")[1] == 1
    assert search_grid_products("común") == ([], 0)
    assert search_grid_products("xyzzy") == ([], 0)


def test_search_grid_products_limita_resultados(temp_db):
    for i in range(15):
        ps.create_product(name=f"Relleno {i:02d}", sale_price=1000 + i)
    shown, total = search_grid_products("Relleno", limit=12)
    assert total == 15
    assert len(shown) == 12
