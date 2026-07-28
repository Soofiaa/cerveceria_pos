# tests/test_report_service.py
import datetime

import pytest

from core import product_service as ps
from core import ticket_service as ts
from core import sales_service as ss
from core import report_service as rs


def _hoy() -> str:
    return datetime.date.today().isoformat()


def test_summary_calcula_ingresos_ganancia_tickets_y_promedio(temp_db):
    """
    Datos sintéticos verificables a mano:
      Producto A: precio venta 2500, costo 1200 (ganancia unitaria 1300)
      Producto B: precio venta 3000, costo 1500 (ganancia unitaria 1500)

      Venta 1: 2xA + 1xB -> ingreso 8000, ganancia 4100
      Venta 2: 3xA       -> ingreso 7500, ganancia 3900

      Total ingreso  = 15500
      Total ganancia = 8000
      Tickets        = 2
      Ticket promedio = 15500 / 2 = 7750
    """
    pid_a = ps.create_product("Producto A", 2500, 1200)
    pid_b = ps.create_product("Producto B", 3000, 1500)

    t1 = ts.create_ticket()
    ts.add_item(t1, pid_a, qty=2, unit_price=2500)
    ts.add_item(t1, pid_b, qty=1, unit_price=3000)
    ts.set_pay_method(t1, "efectivo")
    ss.cobrar_ticket(t1)

    t2 = ts.create_ticket()
    ts.add_item(t2, pid_a, qty=3, unit_price=2500)
    ts.set_pay_method(t2, "tarjeta")
    ss.cobrar_ticket(t2)

    hoy = _hoy()
    resumen = rs.summary(hoy, hoy)

    assert resumen["total"] == 15500
    assert resumen["profit"] == 8000
    assert resumen["tickets"] == 2
    assert resumen["avg_ticket"] == 7750

    # Margen promedio: promedio simple de margen por línea de venta
    # (no ponderado por ingreso), tal como calcula summary():
    #   línea A@venta1 (qty2): 2600/5000 = 0.52
    #   línea B@venta1 (qty1): 1500/3000 = 0.50
    #   línea A@venta2 (qty3): 3900/7500 = 0.52
    esperado = (0.52 + 0.50 + 0.52) / 3
    assert resumen["avg_margin"] == pytest.approx(esperado)


def test_summary_sin_ventas_en_rango_no_divide_por_cero(temp_db):
    resumen = rs.summary("2000-01-01", "2000-01-02")

    assert resumen["total"] == 0
    assert resumen["profit"] == 0
    assert resumen["tickets"] == 0
    assert resumen["avg_ticket"] == 0
    assert resumen["avg_margin"] == 0.0


def test_summary_tickets_coincide_con_ventas_del_dia(temp_db):
    """Validación cruzada pedida explícitamente: mismo conteo y mismo total
    que ventas_del_dia() para el mismo rango de fechas."""
    pid = ps.create_product("Producto A", 2500, 1200)

    for _ in range(3):
        tid = ts.create_ticket()
        ts.add_item(tid, pid, qty=1, unit_price=2500)
        ts.set_pay_method(tid, "efectivo")
        ss.cobrar_ticket(tid)

    hoy = _hoy()
    resumen = rs.summary(hoy, hoy)
    ventas_hoy = ss.ventas_del_dia()

    assert resumen["tickets"] == len(ventas_hoy) == 3
    assert resumen["total"] == sum(v["total"] for v in ventas_hoy) == 7500


def test_summary_usa_gain_per_unit_para_producto_comun(temp_db):
    """
    Para 'Producto común' la ganancia no sale de purchase_price (que es 0),
    sino de gain_per_unit definido al agregar el ítem al ticket.
    """
    tid = ts.create_ticket()
    ts.add_common_item(tid, "Servicio especial", qty=2, unit_price=1000, gain_per_unit=400)
    ts.set_pay_method(tid, "efectivo")
    ss.cobrar_ticket(tid)

    hoy = _hoy()
    resumen = rs.summary(hoy, hoy)

    assert resumen["total"] == 2000
    assert resumen["profit"] == 800  # 2 * 400
    assert resumen["tickets"] == 1
    assert resumen["avg_ticket"] == 2000
