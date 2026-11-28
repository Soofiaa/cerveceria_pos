import pytest
from core.utils_format import fmt_money
import flet_app.main as main
import flet_app.boletas as boletas
import flet_app.reportes_view as reportes_view
import flet_app.productos_view as productos_view

def test_fmt_money_behavior():
    assert fmt_money(0) == "$0"
    assert fmt_money(999) == "$999"
    assert fmt_money(1500) == "$1.500"
    assert fmt_money(1000000) == "$1.000.000"
    assert fmt_money(-1500) == "-$1.500"
    assert fmt_money(None) == "$0"

def test_fmt_money_identity():
    assert main.fmt_money is fmt_money
    assert boletas.fmt_money is fmt_money
    assert reportes_view._fmt_money is fmt_money
    assert productos_view._fmt_money is fmt_money
