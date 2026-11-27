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


def cobrar_ticket(
    ticket_id: int, 
    pay_method: Optional[str] = None, 
    expected_total: Optional[int] = None
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Convierte un ticket abierto en una venta:
    - Valida opcionalmente total y método de pago.
    - Crea cabecera en sales (subtotal=SUM, total=subtotal, pay_method, status=pagada, created_at local)
    - Crea sale_items con qty, unit_price, line_total y gain_per_unit
    - Descuenta stock de cada producto (excepto 'Producto común')
    - Borra ticket e ítems abiertos
    """
    if pay_method and pay_method not in ["efectivo", "credito", "debito", "transferencia"]:
        raise ValueError("Método de pago inválido.")

    with get_conn() as con:
        cur = con.cursor()
        cur.execute("BEGIN IMMEDIATE")

        # Obtener ticket
        cur.execute("""
            SELECT id, COALESCE(pay_method,''), COALESCE(pending_total,0)
            FROM open_tickets WHERE id=?
        """, (ticket_id,))
        t = cur.fetchone()
        if not t:
            raise ValueError("Ticket no existe.")
        _, ticket_pay_method, ticket_pending_total = t

        # Ítems del ticket
        cur.execute("""
            SELECT i.product_id, i.qty, i.unit_price, i.gain_per_unit, i.display_name
            FROM open_ticket_items i
            WHERE i.ticket_id=?
        """, (ticket_id,))
        items = cur.fetchall()
        if not items:
            raise ValueError("El ticket no tiene ítems.")

        # Recalcular subtotal
        cur.execute("""
            SELECT IFNULL(SUM(qty * unit_price), 0)
            FROM open_ticket_items
            WHERE ticket_id=?
        """, (ticket_id,))
        subtotal = cur.fetchone()[0] or 0
        total = subtotal

        if expected_total is not None and subtotal != expected_total:
            raise ValueError("El ticket cambió, revisa el total.")

        # Usar método de pago provisto o el del ticket
        final_pay_method = pay_method if pay_method is not None else ticket_pay_method
        if not final_pay_method:
             final_pay_method = "efectivo"

        # Insertar venta
        created_at = now_local_str()
        cur.execute("""
            INSERT INTO sales (subtotal, total, pay_method, status, created_at)
            VALUES (?, ?, ?, 'pagada', ?)
        """, (subtotal, total, final_pay_method, created_at))
        sale_id = cur.lastrowid

        # Producto común
        cur.execute("SELECT id FROM products WHERE name='Producto común' LIMIT 1")
        common_row = cur.fetchone()
        common_product_id = common_row[0] if common_row else None

        # Insertar detalle y descontar stock
        stock_warnings = _stock_warnings_for_ticket(cur, ticket_id)

        for (product_id, qty, unit_price, gain_per_unit, display_name) in items:
            qty = int(qty)
            unit_price = int(unit_price)
            gain_per_unit = int(gain_per_unit or 0)
            line_total = qty * unit_price

            if product_id != common_product_id:
                # Ganancia congelada al cobrar: el costo de hoy, leido en esta misma
                # transaccion. El gain_per_unit del ticket es 0 en productos regulares.
                cur.execute("SELECT COALESCE(purchase_price, 0) FROM products WHERE id=?", (product_id,))
                row = cur.fetchone()
                gain_per_unit = unit_price - int(row[0] if row else 0)

            cur.execute("""
                INSERT INTO sale_items (sale_id, product_id, qty, unit_price, line_total, gain_per_unit, display_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sale_id, product_id, qty, unit_price, line_total, gain_per_unit, display_name))

            if product_id != common_product_id:
                cur.execute(
                    "UPDATE products SET stock = stock - ? WHERE id=?",
                    (qty, product_id),
                )

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
            SELECT si.id, COALESCE(si.display_name, p.name), si.qty, si.unit_price, si.line_total
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
