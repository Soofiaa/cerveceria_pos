# core/product_backup_service.py
import os
import csv
from core.db_manager import get_conn


def export_products_csv(path: str):
    """
    Exporta la tabla de productos a un CSV.
    Formato columnas:
        Nombre;PrecioVenta;PrecioCompra;CodigoBarra
    """
    # Leemos los productos desde la BD
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT name,
                   COALESCE(sale_price, 0),
                   COALESCE(purchase_price, 0),
                   COALESCE(barcode, '')
            FROM products
            ORDER BY name COLLATE NOCASE
        """)
        rows = cur.fetchall()

    # Escribimos CSV en codificación amigable para Excel
    with open(path, "w", newline="", encoding="latin-1") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Nombre", "PrecioVenta", "PrecioCompra", "CodigoBarra"])
        for name, sale_price, purchase_price, barcode in rows:
            writer.writerow([
                name or "",
                int(sale_price or 0),
                int(purchase_price or 0),
                barcode or ""
            ])


def import_products_csv(path: str):
    """
    Importa productos desde un CSV con columnas:
        Nombre;PrecioVenta;PrecioCompra;CodigoBarra

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

            try:
                if len(row) > 1:
                    sale_price = int((row[1] or "0").strip() or 0)
                if len(row) > 2:
                    purchase_price = int((row[2] or "0").strip() or 0)
                if len(row) > 3:
                    bc = (row[3] or "").strip()
                    barcode = bc if bc else None
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
                # Actualizar
                cur.execute("""
                    UPDATE products
                    SET name = ?, sale_price = ?, purchase_price = ?, barcode = ?
                    WHERE id = ?
                """, (name, sale_price, purchase_price, barcode, product_id))
                updated += 1
            else:
                # Crear nuevo
                cur.execute("""
                    INSERT INTO products (name, sale_price, purchase_price, barcode)
                    VALUES (?, ?, ?, ?)
                """, (name, sale_price, purchase_price, barcode))
                created += 1

        con.commit()

    return {"created": created, "updated": updated, "skipped": skipped}
