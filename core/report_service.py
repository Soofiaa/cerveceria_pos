from typing import List, Dict, Any
from core.db_manager import get_conn

def _to_date_str(d) -> str:
    """Acepta QDate o str y devuelve 'YYYY-MM-DD'."""
    if hasattr(d, "toString"):
        return d.toString("yyyy-MM-dd")
    return str(d)

def list_sales(date_from, date_to) -> List[Dict[str, Any]]:
    d1, d2 = _to_date_str(date_from), _to_date_str(date_to)
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, created_at, IFNULL(total,0)
            FROM sales
            WHERE date(created_at) BETWEEN ? AND ?
            ORDER BY datetime(created_at) DESC, id DESC   -- más nuevas primero
        """, (d1, d2))
        return [
            {"id": r[0], "created_at": r[1], "total": int(r[2] or 0)}
            for r in cur.fetchall()
        ]

def summary(date_from, date_to) -> Dict[str, Any]:
    """
    Resumen de ventas y ganancias en el rango.
    Usa gain_per_unit si está disponible; si es 0, usa unit_price - purchase_price.
    """
    d1, d2 = _to_date_str(date_from), _to_date_str(date_to)

    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT
                si.qty,
                si.unit_price,
                COALESCE(p.purchase_price, 0) AS purchase_price,
                COALESCE(si.gain_per_unit, 0) AS gain_per_unit
            FROM sales s
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON p.id = si.product_id
            WHERE date(s.created_at) BETWEEN ? AND ?
        """, (d1, d2))

        total_revenue = 0
        total_profit = 0
        margins_sum = 0.0
        margin_count = 0

        for qty, unit_price, purchase_price, gain_per_unit in cur.fetchall():
            qty = int(qty or 0)
            unit_price = int(unit_price or 0)
            purchase_price = int(purchase_price or 0)
            gain_per_unit = int(gain_per_unit or 0)

            line_revenue = qty * unit_price
            total_revenue += line_revenue

            if gain_per_unit != 0:
                # Caso producto común con ganancia definida en la UI
                line_profit = qty * gain_per_unit
            else:
                # Caso producto normal: ganancia por diferencia precio - costo
                line_profit = qty * (unit_price - purchase_price)

            total_profit += line_profit

            if line_revenue > 0:
                margin = line_profit / line_revenue
                margins_sum += margin
                margin_count += 1

        avg_ticket = 0
        tickets = 0

        # Si ya tienes lógica para tickets/avg_ticket aparte, puedes mantenerla;
        # aquí lo dejo en 0 por simplicidad o puedes combinarlo con tu código actual.

        avg_margin = (margins_sum / margin_count) if margin_count > 0 else 0.0

        return {
            "total": total_revenue,
            "tickets": tickets,
            "avg_ticket": avg_ticket,
            "profit": total_profit,
            "avg_margin": avg_margin,
        }


def top_products(date_from, date_to, limit:int=10) -> List[Dict[str, Any]]:
    d1, d2 = _to_date_str(date_from), _to_date_str(date_to)
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT p.name,
                   SUM(si.qty)               AS total_qty,
                   SUM(si.qty*si.unit_price) AS revenue
            FROM sale_items si
            JOIN sales    s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE date(s.created_at) BETWEEN ? AND ?
            GROUP BY p.id, p.name
            ORDER BY revenue DESC
            LIMIT ?
        """, (d1, d2, limit))
        return [
            {"name": r[0] or "", "qty": int(r[1] or 0), "revenue": int(r[2] or 0)}
            for r in cur.fetchall()
        ]
        
def daily_totals(date_from, date_to) -> List[Dict[str, Any]]:
    """Devuelve totales por día en el rango (orden cronológico asc)."""
    def _to_date_str(d) -> str:
        if hasattr(d, "toString"):
            return d.toString("yyyy-MM-dd")
        return str(d)

    d1, d2 = _to_date_str(date_from), _to_date_str(date_to)
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT date(created_at) AS d, IFNULL(SUM(total),0) AS t
            FROM sales
            WHERE date(created_at) BETWEEN ? AND ?
            GROUP BY date(created_at)
            ORDER BY d ASC
        """, (d1, d2))
        return [{"date": r[0], "total": int(r[1] or 0)} for r in cur.fetchall()]

def hourly_totals(day) -> List[Dict[str, Any]]:
    """Totales por hora para un día (YYYY-MM-DD). Devuelve 0..23 con huecos en 0 si no hay ventas."""
    d = day.toString("yyyy-MM-dd") if hasattr(day, "toString") else str(day)
    # base vacía 0..23
    base = {f"{h:02d}": 0 for h in range(24)}
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT strftime('%H', created_at) AS hh, IFNULL(SUM(total),0)
            FROM sales
            WHERE date(created_at)=?
            GROUP BY hh
            ORDER BY hh
        """, (d,))
        for hh, tot in cur.fetchall():
            base[hh] = int(tot or 0)
    return [{"label": k, "total": v} for k, v in base.items()]

def monthly_totals(date_from, date_to) -> List[Dict[str, Any]]:
    """Totales por mes (AAAA-MM) para el rango."""
    def _to(d): return d.toString("yyyy-MM-dd") if hasattr(d, "toString") else str(d)
    d1, d2 = _to(date_from), _to(date_to)
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT strftime('%Y-%m', created_at) AS ym, IFNULL(SUM(total),0)
            FROM sales
            WHERE date(created_at) BETWEEN ? AND ?
            GROUP BY ym
            ORDER BY ym ASC
        """, (d1, d2))
        return [{"label": r[0], "total": int(r[1] or 0)} for r in cur.fetchall()]
