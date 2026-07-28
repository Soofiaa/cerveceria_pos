# core/product_service.py
from typing import List, Dict, Optional, Any
from core.db_manager import get_conn


def create_product(
    name: str,
    sale_price: int,
    purchase_price: int = 0,
    barcode: Optional[str] = None,
    stock: int = 0,
    min_stock: int = 0,
) -> int:
    if not name or sale_price is None:
        raise ValueError("Nombre y precio de venta son obligatorios.")
    if sale_price < 0 or purchase_price < 0:
        raise ValueError("Los precios no pueden ser negativos.")
    if stock < 0 or min_stock < 0:
        raise ValueError("El stock y la alerta de stock no pueden ser negativos.")

    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO products (name, sale_price, purchase_price, barcode, stock, min_stock)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name.strip(), int(sale_price), int(purchase_price), barcode, int(stock), int(min_stock)))
        con.commit()
        return cur.lastrowid


def update_product(product_id: int, **fields) -> int:
    if not fields:
        return 0

    allowed = {"name", "sale_price", "purchase_price", "barcode", "stock", "min_stock"}
    sets, values = [], []

    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("sale_price", "purchase_price", "stock", "min_stock") and v is not None:
            v = int(v)
            if v < 0:
                raise ValueError("Los precios y el stock no pueden ser negativos.")
        sets.append(f"{k}=?")
        values.append(v)

    if not sets:
        return 0

    values.append(product_id)
    with get_conn() as con:
        cur = con.cursor()
        cur.execute(f"UPDATE products SET {', '.join(sets)} WHERE id=?", values)
        con.commit()
        return cur.rowcount


def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, sale_price, purchase_price, barcode, stock, min_stock, is_active
            FROM products WHERE id=?
        """, (product_id,))
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "name": r[1],
            "sale_price": r[2],
            "purchase_price": r[3],
            "barcode": r[4],
            "stock": r[5],
            "min_stock": r[6],
            "is_active": r[7],
        }


def list_products(q: str = "", incluir_inactivos: bool = False) -> List[Dict[str, Any]]:
    """
    Lista productos, ordenados por nombre.
    Por defecto solo devuelve productos activos (is_active=1); usa
    incluir_inactivos=True para verlos todos (por ejemplo en reportes
    históricos, donde un producto dado de baja igual debe poder consultarse).
    """
    q = (q or "").strip()
    with get_conn() as con:
        cur = con.cursor()

        where_clauses = []
        params: list = []

        if not incluir_inactivos:
            where_clauses.append("is_active=1")

        if q:
            where_clauses.append("(name LIKE '%'||?||'%' OR IFNULL(barcode,'') LIKE '%'||?||'%')")
            params.extend([q, q])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cur.execute(f"""
            SELECT id, name, sale_price, purchase_price, barcode, stock, min_stock, is_active
            FROM products
            {where_sql}
            ORDER BY name
        """, params)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "sale_price": r[2],
                "purchase_price": r[3],
                "barcode": r[4],
                "stock": r[5],
                "min_stock": r[6],
                "is_active": r[7],
            }
            for r in rows
        ]


def adjust_stock(product_id: int, delta: int) -> None:
    """Suma 'delta' (puede ser negativo) al stock del producto."""
    with get_conn() as con:
        con.execute(
            "UPDATE products SET stock = stock + ? WHERE id=?",
            (int(delta), product_id),
        )
        con.commit()


def list_low_stock_products() -> List[Dict[str, Any]]:
    """
    Productos activos cuyo stock actual está en o por debajo de su alerta
    mínima. Excluye productos inactivos (dados de baja: no tiene sentido
    alertar por stock de algo que ya no se vende) y 'Producto común'.
    """
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, sale_price, purchase_price, barcode, stock, min_stock, is_active
            FROM products
            WHERE stock <= min_stock AND name != 'Producto común' AND is_active=1
            ORDER BY name
        """)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "sale_price": r[2],
                "purchase_price": r[3],
                "barcode": r[4],
                "stock": r[5],
                "min_stock": r[6],
                "is_active": r[7],
            }
            for r in rows
        ]


def ensure_demo_products():
    """Crea productos demo solo si la tabla está vacía."""
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        (count,) = cur.fetchone()
        if count == 0:
            cur.executemany("""
                INSERT INTO products (name, sale_price, purchase_price, barcode)
                VALUES (?, ?, ?, ?)
            """, [
                ("IPA Lata 473ml",      2500, 1200, "780000000001"),
                ("APA Botella 330ml",   2200, 1000, "780000000002"),
                ("Stout Lata 473ml",    2800, 1500, "780000000003"),
                ("Amber Ale Lata 473ml",2400, 1100, "780000000004"),
                ("Porter Botella 330ml",2300, 1000, "780000000005"),
                ("Pilsner Lata 473ml",  2100, 950,  "780000000006"),
            ])
            con.commit()


def delete_product(product_id: int):
    """
    Elimina un producto si no está siendo usado.
    - No permite eliminar si tiene ventas registradas.
    - No permite eliminar si está en tickets abiertos.
    """
    with get_conn() as con:
        cur = con.cursor()

        # ¿Está en tickets abiertos?
        cur.execute("SELECT COUNT(*) FROM open_ticket_items WHERE product_id=?", (product_id,))
        open_count = cur.fetchone()[0] or 0

        # ¿Está en ventas históricas?
        cur.execute("SELECT COUNT(*) FROM sale_items WHERE product_id=?", (product_id,))
        sales_count = cur.fetchone()[0] or 0

        if open_count > 0:
            raise ValueError(
                "El producto está usado en tickets abiertos. "
                "Primero quítalo de esos tickets antes de eliminarlo."
            )

        if sales_count > 0:
            raise ValueError(
                "El producto tiene ventas registradas y no se puede eliminar.\n"
                "Puedes dejar de usarlo o renombrarlo, pero no borrarlo."
            )

        # Intentar eliminar
        cur.execute("DELETE FROM products WHERE id=?", (product_id,))
        if cur.rowcount == 0:
            raise ValueError("El producto no existe o ya fue eliminado.")

        con.commit()


def desactivar_producto(product_id: int) -> None:
    """
    Baja lógica de un producto: marca is_active=0 en vez de borrarlo.
    - El producto deja de aparecer en list_products() por defecto (búsqueda,
      catálogo del POS), pero su fila sigue existiendo, así que se conserva
      intacta la trazabilidad de sale_items y open_ticket_items que lo
      referencian.
    - Reemplaza a force_delete_product(), que borraba físicamente esas
      líneas y rompía el historial de ventas ya cobradas.
    """
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("UPDATE products SET is_active=0 WHERE id=?", (int(product_id),))
        if cur.rowcount == 0:
            raise ValueError("El producto no existe o ya fue eliminado.")
        con.commit()


def force_delete_product(product_id: int):
    """
    @deprecated: NO USAR. Reemplazada por desactivar_producto().

    Motivo de la baja: esta función borraba físicamente las líneas de
    sale_items asociadas al producto para poder eliminarlo, lo que rompía
    la trazabilidad de ventas ya cobradas (un reporte histórico podía
    quedar con montos totales que ya no coincidían con su detalle línea a
    línea). Se conserva el código, sin usarse desde la UI, únicamente como
    referencia del problema que motivó el cambio a baja lógica.

    Elimina el producto incluso si tiene ventas o está en tickets.
    ATENCIÓN:
    - Borra las líneas de ese producto en tickets abiertos.
    - Borra las líneas de detalle en sale_items.
    - Los totales de 'sales' se mantienen, pero sin ese detalle.
    """
    pid = int(product_id)

    with get_conn() as con:
        cur = con.cursor()
        try:
            # Borrar de tickets abiertos
            cur.execute("DELETE FROM open_ticket_items WHERE product_id=?", (pid,))
            # Borrar de líneas de venta
            cur.execute("DELETE FROM sale_items WHERE product_id=?", (pid,))
            # Borrar el producto
            cur.execute("DELETE FROM products WHERE id=?", (pid,))

            if cur.rowcount == 0:
                raise ValueError("El producto no existe o ya fue eliminado.")

            con.commit()
        except Exception:
            con.rollback()
            raise
