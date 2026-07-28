# core/product_backup_service.py
import os
import csv
from core.db_manager import get_conn


def export_products_csv(path: str):
    """
    Exporta la tabla de productos a un CSV.
    Formato columnas:
        Nombre;PrecioVenta;PrecioCompra;CodigoBarra;Stock;StockMinimo
    """
    # Leemos los productos desde la BD
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT name,
                   COALESCE(sale_price, 0),
                   COALESCE(purchase_price, 0),
                   COALESCE(barcode, ''),
                   COALESCE(stock, 0),
                   COALESCE(min_stock, 0)
            FROM products
            ORDER BY name COLLATE NOCASE
        """)
        rows = cur.fetchall()

    # Escribimos CSV en codificación amigable para Excel
    with open(path, "w", newline="", encoding="latin-1") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Nombre", "PrecioVenta", "PrecioCompra", "CodigoBarra", "Stock", "StockMinimo"])
        for name, sale_price, purchase_price, barcode, stock, min_stock in rows:
            writer.writerow([
                name or "",
                int(sale_price or 0),
                int(purchase_price or 0),
                barcode or "",
                int(stock or 0),
                int(min_stock or 0),
            ])


def import_products_csv(path: str):
    """
    Importa productos desde un CSV con columnas:
        Nombre;PrecioVenta;PrecioCompra;CodigoBarra;Stock;StockMinimo

    Las columnas Stock y StockMinimo son opcionales (compatibilidad con
    archivos exportados antes de agregar inventario). Si no vienen en el
    archivo, el stock existente no se modifica al actualizar, y los
    productos nuevos se crean con stock 0.

    Regla:
      - Si tiene CódigoBarra, se busca por código. Si existe, se ACTUALIZA.
      - Si no tiene código, se intenta buscar por Nombre. Si existe, se ACTUALIZA.
      - Si no se encuentra, se CREA un nuevo producto.
    No elimina productos existentes.

    Devuelve un dict con contadores:
        {"created": n, "updated": m, "skipped": k}
    """
    created = 0
    updated = 0
    skipped = 0

    # Leemos CSV
    with open(path, "r", newline="", encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)

    if not rows:
        return {"created": 0, "updated": 0, "skipped": 0}

    # Detectar y saltar cabecera si la tiene
    start_index = 0
    header = [c.strip().lower() for c in rows[0]]
    if header and "nombre" in header[0]:
        start_index = 1

    with get_conn() as con:
        cur = con.cursor()

        for row in rows[start_index:]:
            if not row or all(not c.strip() for c in row):
                continue

            # Normalizamos columnas según lo esperado
            try:
                name = (row[0] or "").strip()
            except IndexError:
                skipped += 1
                continue

            if not name:
                skipped += 1
                continue

            sale_price = 0
            purchase_price = 0
            barcode = None
            stock = None
            min_stock = None

            try:
                if len(row) > 1:
                    sale_price = int((row[1] or "0").strip() or 0)
                if len(row) > 2:
                    purchase_price = int((row[2] or "0").strip() or 0)
                if len(row) > 3:
                    bc = (row[3] or "").strip()
                    barcode = bc if bc else None
                if len(row) > 4:
                    stock = int((row[4] or "0").strip() or 0)
                if len(row) > 5:
                    min_stock = int((row[5] or "0").strip() or 0)
            except Exception:
                # si hay valores no numéricos, se salta la fila
                skipped += 1
                continue

            # Buscar producto existente
            product_id = None

            if barcode:
                cur.execute("SELECT id FROM products WHERE barcode=?", (barcode,))
                r = cur.fetchone()
                if r:
                    product_id = r[0]

            if not product_id:
                cur.execute("SELECT id FROM products WHERE name=?", (name,))
                r = cur.fetchone()
                if r:
                    product_id = r[0]

            if product_id:
                # Actualizar (el stock solo se toca si el CSV trae esas columnas)
                sets = ["name = ?", "sale_price = ?", "purchase_price = ?", "barcode = ?"]
                values = [name, sale_price, purchase_price, barcode]
                if stock is not None:
                    sets.append("stock = ?")
                    values.append(stock)
                if min_stock is not None:
                    sets.append("min_stock = ?")
                    values.append(min_stock)
                values.append(product_id)
                cur.execute(f"UPDATE products SET {', '.join(sets)} WHERE id = ?", values)
                updated += 1
            else:
                # Crear nuevo
                cur.execute("""
                    INSERT INTO products (name, sale_price, purchase_price, barcode, stock, min_stock)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, sale_price, purchase_price, barcode, stock or 0, min_stock or 0))
                created += 1

        con.commit()

    return {"created": created, "updated": updated, "skipped": skipped}
