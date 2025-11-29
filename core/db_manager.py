# core/db_manager.py
import sqlite3
import os

# === Carpeta del usuario donde se guardarán los datos ===
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "CerveceriaPOS")
os.makedirs(USER_DATA_DIR, exist_ok=True)

# Ruta absoluta a la base de datos:
DB_PATH = os.path.join(USER_DATA_DIR, "cerveceria.db")

DDL = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  sale_price INTEGER NOT NULL,
  purchase_price INTEGER NOT NULL DEFAULT 0,
  barcode TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS open_tickets (
  id INTEGER PRIMARY KEY,
  name TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  pay_method TEXT,
  pending_total INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS open_ticket_items (
  id INTEGER PRIMARY KEY,
  ticket_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  qty INTEGER NOT NULL,
  unit_price INTEGER NOT NULL,
  display_name TEXT,
  FOREIGN KEY(ticket_id) REFERENCES open_tickets(id) ON DELETE CASCADE,
  FOREIGN KEY(product_id) REFERENCES products(id)
);

-- Nota: el esquema histórico tenía 'datetime'. Lo conservamos para compatibilidad,
-- y añadimos 'created_at' vía migración.
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY,
  datetime DATETIME DEFAULT CURRENT_TIMESTAMP,
  subtotal INTEGER NOT NULL,
  total INTEGER NOT NULL,
  pay_method TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pagada'
);

CREATE TABLE IF NOT EXISTS sale_items (
  id INTEGER PRIMARY KEY,
  sale_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  qty INTEGER NOT NULL,
  unit_price INTEGER NOT NULL,
  line_total INTEGER NOT NULL,
  FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
  FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_sales_datetime ON sales(datetime);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_open_ticket_items_ticket ON open_ticket_items(ticket_id);
"""

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con

def _table_has_column(con, table, column) -> bool:
    cur = con.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())

def migrate_products_strip_format_active():
    """Elimina columnas antiguas 'format' y 'active' de products si existieran."""
    with get_conn() as con:
        has_format = _table_has_column(con, "products", "format")
        has_active = _table_has_column(con, "products", "active")
        if not (has_format or has_active):
            return
        con.execute("PRAGMA foreign_keys=OFF;")
        con.executescript("""
        BEGIN TRANSACTION;
        CREATE TABLE IF NOT EXISTS products_new (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          sale_price INTEGER NOT NULL,
          purchase_price INTEGER NOT NULL DEFAULT 0,
          barcode TEXT UNIQUE
        );
        INSERT INTO products_new (id, name, sale_price, purchase_price, barcode)
          SELECT id, name,
                 COALESCE(sale_price,0),
                 COALESCE(purchase_price,0),
                 barcode
          FROM products;
        DROP TABLE products;
        ALTER TABLE products_new RENAME TO products;
        COMMIT;
        """)
        con.execute("PRAGMA foreign_keys=ON;")
        con.commit()

def _column_exists(con, table: str, col: str) -> bool:
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1].lower() == col.lower() for r in cur.fetchall())

def migrate_sales_add_created_at_if_missing():
    """
    Añade 'created_at' a 'sales' sin default no-constante, rellena datos existentes
    desde 'datetime' (si existe) o datetime('now'), crea trigger para futuras inserciones
    y un índice para mejorar filtros por fecha.
    """
    with get_conn() as con:
        if _column_exists(con, "sales", "created_at"):
            # Asegura índice y trigger aunque la columna ya exista.
            _ensure_sales_created_at_trigger_and_index(con)
            con.commit()
            return

        con.executescript("""
        BEGIN IMMEDIATE;

        -- 1) Agregar columna sin default no-constante
        ALTER TABLE sales ADD COLUMN created_at TEXT;

        -- 2) Rellenar existentes desde 'datetime' si existe; si no, now()
        UPDATE sales
        SET created_at = COALESCE(created_at,
                                   (CASE
                                      WHEN (SELECT COUNT(*) FROM pragma_table_info('sales') WHERE name='datetime') > 0
                                      THEN datetime
                                      ELSE datetime('now')
                                    END))
        WHERE created_at IS NULL;

        COMMIT;
        """)
        # 3) Trigger e índice
        _ensure_sales_created_at_trigger_and_index(con)
        con.commit()
        
        
def ensure_common_product_exists() -> int:
    """
    Crea un producto 'Producto común' si no existe y devuelve su ID.
    Se usa para los ítems de producto común en los tickets.
    """
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("SELECT id FROM products WHERE name='Producto común' LIMIT 1;")
        row = cur.fetchone()
        if row:
            return row[0]
        
        # Si no existe, lo creamos con precios 0 (el unit_price real se guarda en el ticket)
        cur.execute("""
            INSERT INTO products (name, sale_price, purchase_price, barcode)
            VALUES ('Producto común', 0, 0, NULL)
        """)
        con.commit()
        return cur.lastrowid

def migrate_open_ticket_items_add_display_name_if_missing():
    """
    Añade la columna display_name a open_ticket_items si no existe.
    No toca nada más (ni constraints ni datos).
    """
    with get_conn() as con:
        if _column_exists(con, "open_ticket_items", "display_name"):
            return

        con.execute("ALTER TABLE open_ticket_items ADD COLUMN display_name TEXT;")
        con.commit()

def _ensure_sales_created_at_trigger_and_index(con):
    cur = con.cursor()
    # Trigger: si INSERT no provee created_at, lo completa con datetime('now')
    cur.executescript("""
    CREATE TRIGGER IF NOT EXISTS trg_sales_created_at
    AFTER INSERT ON sales
    FOR EACH ROW
    WHEN NEW.created_at IS NULL
    BEGIN
        UPDATE sales SET created_at = datetime('now') WHERE id = NEW.id;
    END;
    """)
    # Índice para consultas por created_at
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at);")


def migrate_open_ticket_items_add_gain_per_unit_if_missing():
    """Añade gain_per_unit a open_ticket_items si no existe."""
    with get_conn() as con:
        if _column_exists(con, "open_ticket_items", "gain_per_unit"):
            return
        con.execute("ALTER TABLE open_ticket_items ADD COLUMN gain_per_unit INTEGER NOT NULL DEFAULT 0;")
        con.commit()


def migrate_sale_items_add_gain_per_unit_if_missing():
    """Añade gain_per_unit a sale_items si no existe."""
    with get_conn() as con:
        if _column_exists(con, "sale_items", "gain_per_unit"):
            return
        con.execute("ALTER TABLE sale_items ADD COLUMN gain_per_unit INTEGER NOT NULL DEFAULT 0;")
        con.commit()


def bootstrap():
    # Crear estructura base
    with get_conn() as con:
        con.executescript(DDL)
        con.commit()
    # Migraciones idempotentes
    migrate_products_strip_format_active()
    migrate_sales_add_created_at_if_missing()
    migrate_open_ticket_items_add_display_name_if_missing()
    migrate_open_ticket_items_add_gain_per_unit_if_missing()
    migrate_sale_items_add_gain_per_unit_if_missing()
    ensure_common_product_exists()
