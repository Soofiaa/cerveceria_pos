"""Mi POS - Acceso a datos del POS, local o por API (Fase 5.1, multi-caja).

main.py llama siempre a este objeto (`backend`) en vez de a core/ directo:
- LocalBackend (standalone y server): usa los servicios de core/ con la base
  de esta maquina, exactamente como antes de esta fase.
- RemoteBackend (client): usa la API de la Caja 1 y NUNCA abre ni crea una
  base local (no llama a bootstrap ni a get_conn).

Mismos nombres que core: ts.list_open_tickets -> backend.list_open_tickets,
etc. Las diferencias estan en cobrar() y receipt(), que cubren las dos formas.
"""

from core import db_manager
from core import product_service as ps
from core import report_service as rs
from core import sales_service as ss
from core import ticket_service as ts
from flet_app import boletas as bol
from flet_app.api_client import ApiClient, ApiError, SinConexion  # noqa: F401  (re-export)
from flet_app.multicaja import get_caja_settings


class LocalBackend:
    """Base local: standalone y Caja 1 (server)."""

    is_remote = False

    def start(self):
        db_manager.bootstrap()

    # productos
    list_products = staticmethod(ps.list_products)
    find_product_by_exact_code_or_name = staticmethod(ps.find_product_by_exact_code_or_name)
    get_product = staticmethod(ps.get_product)
    shopping_list = staticmethod(ps.shopping_list)

    # tickets y lineas
    list_open_tickets = staticmethod(ts.list_open_tickets)
    get_ticket = staticmethod(ts.get_ticket)
    create_ticket = staticmethod(ts.create_ticket)
    delete_ticket = staticmethod(ts.delete_ticket)
    set_pay_method = staticmethod(ts.set_pay_method)
    list_items = staticmethod(ts.list_items)
    get_item = staticmethod(ts.get_item)
    add_item = staticmethod(ts.add_item)
    update_item_qty = staticmethod(ts.update_item_qty)
    adjust_item_qty = staticmethod(ts.adjust_item_qty)
    remove_item = staticmethod(ts.remove_item)
    stock_warnings_for_ticket = staticmethod(ss.stock_warnings_for_ticket)
    report_summary = staticmethod(rs.summary)
    report_sales = staticmethod(rs.list_sales)
    report_top_products = staticmethod(rs.top_products)

    def cobrar(self, ticket_id, method, expected_total=None):
        return ss.cobrar_ticket(ticket_id, pay_method=method, expected_total=expected_total)

    def receipt(self, sale_id, received=None):
        return bol.build_receipt(sale_id, received=received)

    def ping(self):
        return True


class RemoteBackend(ApiClient):
    """Caja cliente: todo por la API de la Caja 1. Sin base local."""

    is_remote = True

    def start(self):
        """No hay nada que preparar: ni bootstrap ni base local."""

    def ping(self):
        return self.is_alive()

    def receipt(self, sale_id, received=None):
        """Datos de la venta que devuelve el servidor; el recibido y vuelto se calculan aqui
        (no se guardan en la base) y la impresion sigue siendo local a esta caja."""
        data = super().receipt(sale_id)
        if data.get("pay_method") == "efectivo" and received is not None and int(received) >= int(data["total"]):
            data["received"] = int(received)
            data["change"] = int(received) - int(data["total"])
        return data


def make_backend(settings=None, session=None):
    """Backend segun el modo de config.json."""
    settings = settings or get_caja_settings()
    if settings["mode"] == "client":
        return RemoteBackend(settings["server_url"], session, settings.get("api_token", ""))
    return LocalBackend()
