# core/sales_service.py
from typing import List, Dict, Any, Optional, Tuple
from core.db_manager import get_conn
from core.time_utils import now_local_str


def _stock_warnings_for_ticket(cur, ticket_id: int) -> List[Dict[str, Any]]:
    """
    Revisa, usando un cursor ya abierto, qué ítems del ticket dejarían el
    stock del producto en negativo. No modifica nada ni bloquea la venta;
    'Producto común' queda excluido porque no tiene control de stock.
    """
    cur.execute("""
        SELECT p.name, p.stock, i.qty, (p.stock - i.qty) AS resultante
        FROM open_ticket_items i
        JOIN products p ON p.id = i.product_id
        WHERE i.ticket_id=? AND p.name != 'Producto común' AND (p.stock - i.qty) < 0
    """, (ticket_id,))
    return [
        {
            "product_name": r[0],
            "stock_actual": r[1],
            "qty": r[2],
            "stock_resultante": r[3],
        }
        for r in cur.fetchall()
    ]


def stock_warnings_for_ticket(ticket_id: int) -> List[Dict[str, Any]]:
    """
    Versión pública de _stock_warnings_for_ticket, con su propia conexión.
    Pensada para que la UI de cobro (ChargeDialog) la consulte ANTES de que
    el usuario confirme el pago, y así mostrar el aviso de antemano en vez
    de después de haber cobrado. No bloquea la venta en ningún caso.
    """
    with get_conn() as con:
        cur = con.cursor()
        return _stock_warnings_for_ticket(cur, ticket_id)


def cobrar_ticket(ticket_id: int) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Convierte un ticket abierto en una venta:
    - Crea cabecera en sales (subtotal=SUM, total=subtotal, pay_method del ticket, status=pagada, created_at local)
    - Crea sale_items con qty, unit_price, line_total y gain_per_unit
    - Descuenta stock de cada producto (excepto 'Producto común'); se permite
      que el stock quede negativo, no se bloquea la venta.
    - Borra ticket e ítems abiertos
    Devuelve (sale_id, stock_warnings), donde stock_warnings es la lista de
    ítems que quedaron con stock negativo tras el cobro (ver
    _stock_warnings_for_ticket). Se calcula ANTES de descontar stock, dentro
    de la misma transacción, así que 'stock_resultante' coincide con el
    valor final si el cobro se confirma.
    """
    with get_conn() as con:
        cur = con.cursor()

        # Obtener ticket
        cur.execute("""
            SELECT id, COALESCE(pay_method,''), COALESCE(pending_total,0)
            FROM open_tickets WHERE id=?
        """, (ticket_id,))
        t = cur.fetchone()
        if not t:
            raise ValueError("Ticket no existe.")
        _, pay_method, _ = t

        # Ítems del ticket (incluyendo gain_per_unit)
        cur.execute("""
            SELECT i.product_id, i.qty, i.unit_price, i.gain_per_unit
            FROM open_ticket_items i
            WHERE i.ticket_id=?
        """, (ticket_id,))
        items = cur.fetchall()
        if not items:
            raise ValueError("El ticket no tiene ítems.")

        # Calculado ANTES de descontar stock, para que refleje el stock
        # resultante real de este cobro (no bloquea la venta).
        stock_warnings = _stock_warnings_for_ticket(cur, ticket_id)

        # Calcular subtotal/total (sin descuentos)
        cur.execute("""
            SELECT IFNULL(SUM(qty * unit_price), 0)
            FROM open_ticket_items
            WHERE ticket_id=?
        """, (ticket_id,))
        subtotal = cur.fetchone()[0] or 0
        total = subtotal

        # Insertar venta (incluye created_at en hora local)
        created_at = now_local_str()
        cur.execute("""
            INSERT INTO sales (subtotal, total, pay_method, status, created_at)
            VALUES (?, ?, ?, 'pagada', ?)
        """, (subtotal, total, (pay_method or "efectivo"), created_at))
        sale_id = cur.lastrowid

        # Producto común: no descuenta inventario (no representa un producto real del catálogo)
        cur.execute("SELECT id FROM products WHERE name='Producto común' LIMIT 1")
        common_row = cur.fetchone()
        common_product_id = common_row[0] if common_row else None

        # Insertar detalle (incluyendo gain_per_unit) y descontar stock
        for (product_id, qty, unit_price, gain_per_unit) in items:
            qty = int(qty)
            unit_price = int(unit_price)
            gain_per_unit = int(gain_per_unit or 0)
            line_total = qty * unit_price

            cur.execute("""
                INSERT INTO sale_items (sale_id, product_id, qty, unit_price, line_total, gain_per_unit)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sale_id, product_id, qty, unit_price, line_total, gain_per_unit))

            if product_id != common_product_id:
                cur.execute(
                    "UPDATE products SET stock = stock - ? WHERE id=?",
                    (qty, product_id),
                )

        # Borrar ticket abierto (ON DELETE CASCADE borra líneas de open_ticket_items)
        cur.execute("DELETE FROM open_tickets WHERE id=?", (ticket_id,))

        con.commit()
        return sale_id, stock_warnings


# --------- Consultas de ventas (útil para vistas rápidas o utilidades) ---------

def ventas_del_dia(fecha_iso: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lista ventas del día por 'created_at' (local). Si se pasa fecha_iso ('YYYY-MM-DD'),
    filtra por ese día; si no, usa la fecha local actual.
    """
    with get_conn() as con:
        cur = con.cursor()
        if fecha_iso:
            cur.execute("""
                SELECT id, created_at, subtotal, total, pay_method, status
                FROM sales
                WHERE DATE(created_at) = DATE(?)
                ORDER BY created_at DESC
            """, (fecha_iso,))
        else:
            cur.execute("""
                SELECT id, created_at, subtotal, total, pay_method, status
                FROM sales
                WHERE DATE(created_at) = DATE('now','localtime')
                ORDER BY created_at DESC
            """)
        rows = cur.fetchall()
        return [{
            "id": r[0],
            "created_at": r[1],
            "subtotal": r[2],
            "total": r[3],
            "pay_method": r[4],
            "status": r[5],
        } for r in rows]


def items_de_venta(sale_id: int) -> List[Dict[str, Any]]:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT si.id, p.name, si.qty, si.unit_price, si.line_total
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            WHERE si.sale_id=?
            ORDER BY si.id ASC
        """, (sale_id,))
        rows = cur.fetchall()
        return [{
            "id": r[0],
            "product_name": r[1],
            "qty": r[2],
            "unit_price": r[3],
            "line_total": r[4],
        } for r in rows]


def ventas_por_rango(desde_iso: str, hasta_iso: str) -> List[Dict[str, Any]]:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, created_at, subtotal, total, pay_method, status
            FROM sales
            WHERE DATE(created_at) BETWEEN DATE(?) AND DATE(?)
            ORDER BY created_at DESC
        """, (desde_iso, hasta_iso))
        rows = cur.fetchall()
        return [{
            "id": r[0],
            "created_at": r[1],
            "subtotal": r[2],
            "total": r[3],
            "pay_method": r[4],
            "status": r[5],
        } for r in rows]
