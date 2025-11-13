# core/ticket_service.py
from typing import List, Dict, Optional, Any, Tuple
from core.db_manager import get_conn
from core.time_utils import now_local_str

# -------- Helpers internos --------
def _line_total(qty: int, unit_price: int) -> int:
    return int(qty) * int(unit_price)

def _recalc_ticket_totals(con, ticket_id: int) -> Tuple[int, int]:
    """Recalcula subtotal y total (son iguales porque no hay descuentos) y actualiza pending_total/updated_at."""
    cur = con.cursor()
    cur.execute("""
        SELECT IFNULL(SUM(qty * unit_price), 0)
        FROM open_ticket_items
        WHERE ticket_id=?
    """, (ticket_id,))
    subtotal = cur.fetchone()[0] or 0
    total = subtotal
    cur.execute("""
        UPDATE open_tickets
           SET pending_total=?,
               updated_at=?
         WHERE id=?
    """, (total, now_local_str(), ticket_id))
    return subtotal, total

# -------- Tickets (cabecera) --------
def create_ticket(name: Optional[str] = None) -> int:
    with get_conn() as con:
        cur = con.cursor()
        ts_now = now_local_str()
        cur.execute("""
            INSERT INTO open_tickets (name, created_at, updated_at, pay_method, pending_total)
            VALUES (?, ?, ?, NULL, 0)
        """, (name, ts_now, ts_now))
        con.commit()
        return cur.lastrowid

def rename_ticket(ticket_id: int, name: Optional[str]) -> None:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE open_tickets
               SET name=?,
                   updated_at=?
             WHERE id=?
        """, (name, now_local_str(), ticket_id))
        con.commit()

def set_pay_method(ticket_id: int, pay_method: Optional[str]) -> None:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE open_tickets
               SET pay_method=?,
                   updated_at=?
             WHERE id=?
        """, (pay_method, now_local_str(), ticket_id))
        con.commit()

def delete_ticket(ticket_id: int) -> None:
    with get_conn() as con:
        con.execute("DELETE FROM open_tickets WHERE id=?", (ticket_id,))
        con.commit()

def get_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, created_at, updated_at, pay_method, pending_total
              FROM open_tickets
             WHERE id=?
        """, (ticket_id,))
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "name": r[1],
            "created_at": r[2],
            "updated_at": r[3],
            "pay_method": r[4],
            "pending_total": r[5],
        }

def list_open_tickets() -> List[Dict[str, Any]]:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, created_at, updated_at, pay_method, pending_total
              FROM open_tickets
          ORDER BY updated_at DESC, id DESC
        """)
        rows = cur.fetchall()
        return [{
            "id": r[0],
            "name": r[1],
            "created_at": r[2],
            "updated_at": r[3],
            "pay_method": r[4],
            "pending_total": r[5],
        } for r in rows]

# -------- Ítems de ticket --------
def list_items(ticket_id: int) -> List[Dict[str, Any]]:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT i.id, i.product_id, p.name, i.qty, i.unit_price
              FROM open_ticket_items i
              JOIN products p ON p.id = i.product_id
             WHERE i.ticket_id=?
          ORDER BY i.id ASC
        """, (ticket_id,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            pid = r[1]
            name = r[2]
            qty = r[3]
            unit = r[4]
            result.append({
                "id": r[0],
                "ticket_id": ticket_id,
                "product_id": pid,
                "product_name": name,
                "qty": qty,
                "unit_price": unit,
                "line_total": _line_total(qty, unit),
            })
        return result

def add_item(ticket_id: int, product_id: int, qty: int, unit_price: int) -> int:
    """Si existe línea del mismo producto y mismo precio, acumula cantidad; si no, crea línea nueva."""
    qty = int(qty)
    unit_price = int(unit_price)
    if qty <= 0 or unit_price < 0:
        raise ValueError("Cantidad y precio deben ser positivos.")

    with get_conn() as con:
        cur = con.cursor()
        # ¿Ya existe línea de ese producto y precio?
        cur.execute("""
            SELECT id, qty
              FROM open_ticket_items
             WHERE ticket_id=? AND product_id=? AND unit_price=?
          ORDER BY id ASC LIMIT 1
        """, (ticket_id, product_id, unit_price))
        row = cur.fetchone()
        if row:
            line_id, old_qty = row
            new_qty = int(old_qty) + qty
            cur.execute("""
                UPDATE open_ticket_items
                   SET qty=?
                 WHERE id=?
            """, (new_qty, line_id))
            result_id = line_id
        else:
            cur.execute("""
                INSERT INTO open_ticket_items (ticket_id, product_id, qty, unit_price)
                VALUES (?, ?, ?, ?)
            """, (ticket_id, product_id, qty, unit_price))
            result_id = cur.lastrowid

        _recalc_ticket_totals(con, ticket_id)
        con.commit()
        return result_id

def remove_item(item_id: int) -> None:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("SELECT ticket_id FROM open_ticket_items WHERE id=?", (item_id,))
        r = cur.fetchone()
        if not r:
            return
        ticket_id = r[0]
        cur.execute("DELETE FROM open_ticket_items WHERE id=?", (item_id,))
        _recalc_ticket_totals(con, ticket_id)
        con.commit()

def update_item_qty(item_id: int, new_qty: int) -> None:
    """Actualiza la cantidad de una línea. Si new_qty <= 0, elimina la línea."""
    new_qty = int(new_qty)
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("SELECT ticket_id FROM open_ticket_items WHERE id=?", (item_id,))
        r = cur.fetchone()
        if not r:
            return
        ticket_id = r[0]

        if new_qty <= 0:
            cur.execute("DELETE FROM open_ticket_items WHERE id=?", (item_id,))
        else:
            cur.execute("UPDATE open_ticket_items SET qty=? WHERE id=?", (new_qty, item_id))

        _recalc_ticket_totals(con, ticket_id)
        con.commit()

def calc_ticket_totals(ticket_id: int) -> Tuple[int, int, int]:
    """Devuelve (subtotal, 0, total). Segundo valor queda 0 por compatibilidad con UI previa."""
    with get_conn() as con:
        subtotal, total = _recalc_ticket_totals(con, ticket_id)
        con.commit()
        return subtotal, 0, total
