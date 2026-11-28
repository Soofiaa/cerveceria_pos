import sqlite3
from typing import List, Dict, Any
from core.db_manager import get_conn

def create_category(name: str) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre de la categoría no puede estar vacío.")
    
    with get_conn() as con:
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            con.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("Ya existe una categoría con ese nombre.")

def list_categories() -> List[Dict[str, Any]]:
    with get_conn() as con:
        cur = con.cursor()
        # count products with category_id, including NULL handling is not needed as it counts specific
        cur.execute("""
            SELECT c.id, c.name, COUNT(p.id)
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id
            GROUP BY c.id
            ORDER BY c.name
        """)
        return [{"id": r[0], "name": r[1], "product_count": r[2]} for r in cur.fetchall()]

def rename_category(category_id: int, name: str) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("El nombre de la categoría no puede estar vacío.")
    
    with get_conn() as con:
        try:
            con.execute("UPDATE categories SET name=? WHERE id=?", (name, category_id))
            con.commit()
        except sqlite3.IntegrityError:
            raise ValueError("Ya existe una categoría con ese nombre.")

def delete_category(category_id: int) -> None:
    # Explícito: no depender de que la FK tenga ON DELETE SET NULL en bases antiguas.
    with get_conn() as con:
        con.execute("UPDATE products SET category_id=NULL WHERE category_id=?", (category_id,))
        con.execute("DELETE FROM categories WHERE id=?", (category_id,))
        con.commit()
