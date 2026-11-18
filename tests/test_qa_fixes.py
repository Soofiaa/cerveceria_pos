import pytest
from core import product_service as ps
from core import ticket_service as ts
from core.db_manager import get_conn

def test_g1_exact_search_first():
    # G1 (QA777 con QA7771 existente agrega el exacto)
    # Limpiar
    with get_conn() as conn:
        conn.execute("DELETE FROM products")
        conn.commit()
    
    id_exact = ps.create_product(name="QA Test Cerveza", sale_price=100, barcode="QA777")
    id_longer = ps.create_product(name="Agua QA", sale_price=50, barcode="QA7771")
    
    # Simular lógica de búsqueda sugerida por QA
    # En product_service.py actual, list_products usa LIKE '%q%'
    # Queremos que una función nos dé el exacto si existe.
    
    # Verificamos comportamiento actual (que falla según QA)
    results = ps.list_products("QA777")
    # Si devuelve ambos y el primero por orden alfabético es "Agua QA", falla el actual.
    # "Agua QA" < "QA Test Cerveza" -> True
    assert results[0]["name"] == "Agua QA" # Esto confirma el bug G1
    
def test_m5_date_order_warning():
    # M5 (Desde > Hasta avisa) - Probamos la lógica del servicio o mixin si es posible
    # Por ahora solo placeholder para recordar implementarlo en la UI
    pass

def test_m7_barcode_duplicate_spanish():
    # M7 (barcode duplicado da mensaje en español)
    with get_conn() as conn:
        conn.execute("DELETE FROM products")
        conn.commit()
    
    ps.create_product(name="P1", sale_price=100, barcode="123")
    with pytest.raises(Exception) as excinfo:
        ps.create_product(name="P2", sale_price=200, barcode="123")
    
    # Actualmente tira "UNIQUE constraint failed: products.barcode"
    # Queremos algo que contenga "Ya existe un producto con ese código de barras"
    # Pero el service suele tirar el error de la DB, la traducción suele ser en UI o capturada.
    # El requerimiento dice "al crear o editar... muestra... en español"
