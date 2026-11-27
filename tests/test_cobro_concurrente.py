"""Cobros simultaneos del mismo ticket (multi-caja): solo debe quedar UNA venta.

Con dos cajas, dos personas pueden pulsar Cobrar sobre el mismo ticket abierto
casi a la vez. cobrar_ticket debe tomar el bloqueo de escritura ANTES de leer
el ticket: el segundo cobro espera, ya no encuentra el ticket y falla limpio
("Ticket no existe."), sin duplicar la venta ni descontar el stock dos veces.

Los tests usan la base temporal (temp_db) y hilos de verdad: cada hilo abre su
propia conexion con get_conn(), como dos cajas atendidas por la API de la Caja 1.
"""

import threading

import pytest

from core import db_manager
from core import product_service as ps
from core import sales_service as ss
from core import ticket_service as ts


def _contar(tabla):
    with db_manager.get_conn() as con:
        return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


def _ticket_con(pid, qty=3, precio=1500):
    tid = ts.create_ticket("Mesa")
    ts.add_item(tid, pid, qty, precio)
    return tid


def _cobrar_a_la_vez(ticket_ids, hilos_por_ticket=2):
    """Lanza `hilos_por_ticket` cobros del mismo ticket exactamente al mismo tiempo.

    Devuelve, por ticket, la lista de resultados: ("ok", sale_id) o ("error", mensaje).
    """
    jobs = [(tid, i) for tid in ticket_ids for i in range(hilos_por_ticket)]
    barrera = threading.Barrier(len(jobs))
    resultados = {tid: [] for tid in ticket_ids}
    candado = threading.Lock()

    def cobrar(tid):
        barrera.wait()
        try:
            salida = ("ok", ss.cobrar_ticket(tid)[0])
        except Exception as exc:  # el segundo debe fallar con ValueError, no con otra cosa
            salida = ("error", f"{type(exc).__name__}: {exc}")
        with candado:
            resultados[tid].append(salida)

    hilos = [threading.Thread(target=cobrar, args=(tid,)) for tid, _ in jobs]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    assert not any(h.is_alive() for h in hilos), "un cobro quedo colgado"
    return resultados


# ---------- El caso: dos cajas cobran el mismo ticket ----------
def test_dos_cobros_simultaneos_del_mismo_ticket_dejan_una_sola_venta(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = _ticket_con(pid, qty=3)

    res = _cobrar_a_la_vez([tid])[tid]

    oks = [r for r in res if r[0] == "ok"]
    errores = [r for r in res if r[0] == "error"]
    assert len(oks) == 1 and len(errores) == 1
    assert _contar("sales") == 1                       # una sola venta
    assert _contar("sale_items") == 1                  # y un solo detalle
    assert ps.get_product(pid)["stock"] == 97          # stock descontado UNA vez (100 - 3)


def test_el_segundo_cobro_falla_limpio_con_ticket_no_existe(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = _ticket_con(pid)

    errores = [r for r in _cobrar_a_la_vez([tid])[tid] if r[0] == "error"]

    assert errores == [("error", "ValueError: Ticket no existe.")]   # no 'database is locked'


def test_muchos_cobros_a_la_vez_del_mismo_ticket_dejan_una_venta(temp_db):
    """Mas presion que dos: 6 cajas pulsan Cobrar a la vez sobre el mismo ticket."""
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    tid = _ticket_con(pid, qty=2)

    res = _cobrar_a_la_vez([tid], hilos_por_ticket=6)[tid]

    assert sum(1 for r in res if r[0] == "ok") == 1
    assert all(r == ("error", "ValueError: Ticket no existe.") for r in res if r[0] == "error")
    assert _contar("sales") == 1
    assert ps.get_product(pid)["stock"] == 98


@pytest.mark.parametrize("ronda", range(15))
def test_la_carrera_no_aparece_en_ninguna_de_varias_rondas(temp_db, ronda):
    """El defecto original era una carrera: pasaba en casi todas las rondas, no en una."""
    pid = ps.create_product("Rubia", 1500, stock=50, barcode="R1")
    tid = _ticket_con(pid, qty=1)
    _cobrar_a_la_vez([tid])
    assert _contar("sales") == 1
    assert ps.get_product(pid)["stock"] == 49


# ---------- No se rompe el cobro normal ----------
def test_cobros_simultaneos_de_tickets_distintos_se_hacen_todos(temp_db):
    """El bloqueo serializa, pero no debe perder ni rechazar cobros legitimos."""
    pid = ps.create_product("Rubia", 1500, stock=1000, barcode="R1")
    tickets = [_ticket_con(pid, qty=2) for _ in range(8)]

    res = _cobrar_a_la_vez(tickets, hilos_por_ticket=1)

    assert all(r[0][0] == "ok" for r in res.values())
    ids = sorted(r[0][1] for r in res.values())
    assert ids == list(range(1, 9))                    # ids de venta distintos y consecutivos
    assert _contar("sales") == 8
    assert ps.get_product(pid)["stock"] == 1000 - 16


def test_ticket_con_dos_cobros_en_paralelo_y_otro_independiente(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=100, barcode="R1")
    repetido, aparte = _ticket_con(pid, qty=1), _ticket_con(pid, qty=4)
    jobs = [repetido, repetido, aparte]
    barrera = threading.Barrier(len(jobs))
    out = []

    def cobrar(tid):
        barrera.wait()
        try:
            out.append((tid, "ok", ss.cobrar_ticket(tid)[0]))
        except ValueError as exc:
            out.append((tid, "error", str(exc)))

    hilos = [threading.Thread(target=cobrar, args=(t,)) for t in jobs]
    [h.start() for h in hilos]
    [h.join(timeout=30) for h in hilos]

    assert sorted((t, k) for t, k, _ in out) == sorted([(repetido, "ok"), (repetido, "error"), (aparte, "ok")])
    assert _contar("sales") == 2
    assert ps.get_product(pid)["stock"] == 100 - 1 - 4


def test_cobro_de_un_solo_hilo_sigue_igual(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=10, barcode="R1")
    tid = _ticket_con(pid, qty=2)
    sale_id, warnings = ss.cobrar_ticket(tid)
    assert sale_id == 1 and warnings == []
    assert ps.get_product(pid)["stock"] == 8
    assert ts.get_ticket(tid) is None                  # el ticket abierto se borro


def test_cobrar_un_ticket_que_ya_no_existe_sigue_siendo_valueerror(temp_db):
    with pytest.raises(ValueError, match="Ticket no existe"):
        ss.cobrar_ticket(9999)


def test_cobrar_un_ticket_vacio_sigue_siendo_valueerror_y_no_deja_la_base_bloqueada(temp_db):
    tid = ts.create_ticket("Vacio")
    with pytest.raises(ValueError, match="no tiene"):
        ss.cobrar_ticket(tid)
    # si el rechazo dejara la transaccion abierta, esta escritura (otra conexion) esperaria y fallaria
    assert ts.create_ticket("Despues") > tid
    assert _contar("sales") == 0


def test_el_stock_negativo_sigue_avisando_y_vendiendo(temp_db):
    pid = ps.create_product("Rubia", 1500, stock=1, barcode="R1")
    tid = _ticket_con(pid, qty=3)
    sale_id, warnings = ss.cobrar_ticket(tid)
    assert sale_id == 1 and warnings[0]["stock_resultante"] == -2
    assert ps.get_product(pid)["stock"] == -2


def test_si_el_cobro_falla_a_mitad_no_queda_venta_a_medias(temp_db, monkeypatch):
    """Atomicidad: un error despues de insertar la venta no deja ni venta ni stock cambiado."""
    pid = ps.create_product("Rubia", 1500, stock=10, barcode="R1")
    tid = _ticket_con(pid, qty=2)
    real = ss._stock_warnings_for_ticket

    def con_falla(cur, ticket_id):
        real(cur, ticket_id)
        raise RuntimeError("falla simulada")

    # Solo se deshace ESTE parche: monkeypatch.undo() tambien revertiria el DB_PATH
    # temporal de la fixture temp_db y el resto del test tocaria la base real.
    with monkeypatch.context() as parche:
        parche.setattr(ss, "_stock_warnings_for_ticket", con_falla)
        with pytest.raises(RuntimeError):
            ss.cobrar_ticket(tid)
    assert db_manager.DB_PATH == temp_db
    assert _contar("sales") == 0 and _contar("sale_items") == 0
    assert ps.get_product(pid)["stock"] == 10
    assert ts.get_ticket(tid) is not None              # el ticket sigue abierto y cobrable
    assert ss.cobrar_ticket(tid)[0] == 1               # y la base no quedo bloqueada
