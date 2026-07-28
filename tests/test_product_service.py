# tests/test_product_service.py
import pytest

from core import product_service as ps
from core import ticket_service as ts
from core import sales_service as ss


def test_delete_product_sin_uso_se_borra_fisicamente(temp_db):
    pid = ps.create_product("Producto sin uso", 1000)
    ps.delete_product(pid)
    assert ps.get_product(pid) is None


def test_delete_product_con_ventas_lanza_value_error(temp_db):
    pid = ps.create_product("IPA", 2500, 1200, stock=10)
    tid = ts.create_ticket()
    ts.add_item(tid, pid, qty=1, unit_price=2500)
    ts.set_pay_method(tid, "efectivo")
    ss.cobrar_ticket(tid)

    with pytest.raises(ValueError):
        ps.delete_product(pid)

    # El producto debe seguir existiendo: el ValueError no debe haber
    # borrado nada a medias.
    assert ps.get_product(pid) is not None


def test_delete_product_en_ticket_abierto_lanza_value_error(temp_db):
    pid = ps.create_product("Stout", 3000, 1500, stock=10)
    tid = ts.create_ticket()
    ts.add_item(tid, pid, qty=1, unit_price=3000)
    # Sin cobrar: el ticket queda abierto.

    with pytest.raises(ValueError):
        ps.delete_product(pid)

    assert ps.get_product(pid) is not None


def test_desactivar_producto_marca_is_active_en_cero(temp_db):
    pid = ps.create_product("Porter", 2300, 1000)

    ps.desactivar_producto(pid)

    prod = ps.get_product(pid)
    assert prod is not None
    assert prod["is_active"] == 0


def test_list_products_no_devuelve_inactivos_por_defecto(temp_db):
    pid_activo = ps.create_product("Pilsner", 2100, 950)
    pid_inactivo = ps.create_product("Amber Ale", 2400, 1100)

    ps.desactivar_producto(pid_inactivo)

    activos = ps.list_products()
    ids_activos = {p["id"] for p in activos}

    assert pid_activo in ids_activos
    assert pid_inactivo not in ids_activos


def test_list_products_incluir_inactivos_true_si_los_devuelve(temp_db):
    pid_inactivo = ps.create_product("Amber Ale", 2400, 1100)
    ps.desactivar_producto(pid_inactivo)

    todos = ps.list_products(incluir_inactivos=True)
    ids_todos = {p["id"] for p in todos}

    assert pid_inactivo in ids_todos


def test_desactivar_producto_inexistente_lanza_value_error(temp_db):
    with pytest.raises(ValueError):
        ps.desactivar_producto(999999)


def test_desactivar_producto_conserva_historial_de_ventas(temp_db):
    """
    El motivo original de la Fase 3: desactivar (a diferencia del viejo
    force_delete_product) no debe tocar sale_items de ventas ya cobradas.
    """
    pid = ps.create_product("IPA", 2500, 1200, stock=10)
    tid = ts.create_ticket()
    ts.add_item(tid, pid, qty=2, unit_price=2500)
    ts.set_pay_method(tid, "efectivo")
    sale_id, _ = ss.cobrar_ticket(tid)

    # Ya no se puede borrar físicamente (tiene ventas), pero sí desactivar.
    with pytest.raises(ValueError):
        ps.delete_product(pid)
    ps.desactivar_producto(pid)

    items = ss.items_de_venta(sale_id)
    assert len(items) == 1
    assert items[0]["product_name"] == "IPA"
    assert items[0]["qty"] == 2
