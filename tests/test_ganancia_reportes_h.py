import pytest
from core import report_service as rs

class FakePage:
    def update(self):
        pass
    overlay = []

def test_ganancia_y_margen(monkeypatch):
    def fake_summary(d1, d2):
        return {"total": 10000, "tickets": 10, "avg_ticket": 1000, "profit": 3000, "avg_margin": 0.3}

    class FakeBackend:
        def report_summary(self, d1, d2): return fake_summary(d1, d2)
        def report_sales(self, d1, d2): return []
        def report_top_products(self, d1, d2): return []
        def shopping_list(self): return []

    from flet_app.reportes_view import ReportesView
    page = FakePage()
    view = ReportesView(page, {"text":"#000", "secondary":"#000", "primary":"#000", "accent":"#000", "surface":"#000", "danger":"#000", "primary_text":"#fff"})
    view.backend = FakeBackend()
    view.load_data()
    
    assert view.txt_profit.value == "$3.000"
    assert view.txt_margin.value == "30.0%"

def test_margen_con_total_cero():
    def fake_summary_zero(d1, d2):
        return {"total": 0, "tickets": 0, "avg_ticket": 0, "profit": 0, "avg_margin": 0.0}

    class FakeBackend:
        def report_summary(self, d1, d2): return fake_summary_zero(d1, d2)
        def report_sales(self, d1, d2): return []
        def report_top_products(self, d1, d2): return []
        def shopping_list(self): return []

    from flet_app.reportes_view import ReportesView
    page = FakePage()
    view = ReportesView(page, {"text":"#000", "secondary":"#000", "primary":"#000", "accent":"#000", "surface":"#000", "danger":"#000", "primary_text":"#fff"})
    view.backend = FakeBackend()
    view.load_data()
    
    assert view.txt_margin.value == "0%"
