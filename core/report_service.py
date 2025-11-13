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
    d1, d2 = _to_date_str(date_from), _to_date_str(date_to)
    with get_conn() as con:
        cur = con.cursor()

        # --- Total vendido y número de tickets ---
        cur.execute("""
            SELECT IFNULL(SUM(total),0), COUNT(*)
            FROM sales
            WHERE date(created_at) BETWEEN ? AND ?
        """, (d1, d2))
        total, count = cur.fetchone()
        total = int(total or 0)
        count = int(count or 0)
        avg_ticket = int(round(total / count)) if count else 0

        # --- Ganancias ---
        # Usamos purchase_price de products
        cur.execute("""
            SELECT si.qty,
                   si.unit_price,
                   p.purchase_price
            FROM sale_items si
            JOIN sales    s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE date(s.created_at) BETWEEN ? AND ?
        """, (d1, d2))

        total_profit = 0
        total_margin = 0.0      # suma de márgenes por línea
        margin_count = 0

        for qty, unit_price, purchase_price in cur.fetchall():
            qty          = int(qty or 0)
            unit_price   = int(unit_price or 0)
            purchase_prc = int(purchase_price or 0)

            # Producto común: purchase_price = 0 => 100% ganancia
            if purchase_prc == 0:
                gain = qty * unit_price
            else:
                gain = qty * (unit_price - purchase_prc)

            total_profit += gain

            revenue = qty * unit_price
            if revenue > 0:
                margin = gain / revenue      # fracción: 0.25 => 25 %
                total_margin += margin
                margin_count += 1

        avg_margin = (total_margin / margin_count) if margin_count else 0.0

        return {
            "total": total,
            "tickets": count,
            "avg_ticket": avg_ticket,
            "profit": int(total_profit),
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
