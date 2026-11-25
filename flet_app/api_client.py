"""Mi POS - Cliente de la API de la Caja 1 (Fase 5.1, multi-caja).

Expone los mismos metodos que usa el POS de core/ (productos, tickets,
lineas, cobro), pero llamando a la API en vez de abrir una base local. En
modo cliente la app no usa ni crea ninguna base: todo pasa por aqui.

Sin conexion: cualquier fallo de red lanza SinConexion. No hay cola de
ventas offline en esta fase: quien llama debe avisar y no seguir (en
particular, nunca cobrar).
"""

import requests

CONNECT_TIMEOUT = 2.0   # s: detectar rapido que la Caja 1 no esta
READ_TIMEOUT = 6.0      # s: una venta no debe quedar colgada


class SinConexion(Exception):
    """La Caja 1 no responde (apagada, fuera de la red o sin servicio)."""


class ApiError(Exception):
    """La Caja 1 respondio, pero rechazo la operacion (datos invalidos, no existe...)."""

    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


class ApiClient:
    def __init__(self, base_url, session=None, token=""):
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._headers = {"X-Caja-Token": token} if token else {}

    # ---------- transporte ----------
    def _request(self, method, path, **kwargs):
        try:
            r = self._session.request(
                method, self.base_url + path, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                headers=self._headers, **kwargs
            )
        except requests.RequestException as exc:  # sin red, timeout, rechazo, DNS
            raise SinConexion(f"sin conexión con la Caja 1 ({self.base_url})") from exc
        try:
            body = r.json()
        except ValueError:
            # No es JSON: no es nuestro servidor (otro programa en ese puerto, proxy...).
            raise SinConexion(f"la dirección {self.base_url} no responde como la Caja 1") from None
        if r.status_code >= 500:
            raise SinConexion(f"la Caja 1 tuvo un error interno ({r.status_code})")
        if r.status_code >= 400:
            raise ApiError((body or {}).get("error") or f"Error {r.status_code}", r.status_code)
        return body

    # ---------- estado ----------
    def health(self):
        return self._request("GET", "/api/health")

    def is_alive(self):
        try:
            return bool(self.health().get("ok"))
        except (SinConexion, ApiError):
            return False

    def config(self):
        return self._request("GET", "/api/config")

    # ---------- productos ----------
    def list_products(self, q=""):
        return self._request("GET", "/api/products", params={"q": q or ""})

    def find_product_by_exact_code_or_name(self, q):
        return self._request("GET", "/api/products/exact", params={"q": q or ""})

    def get_product(self, product_id):
        try:
            return self._request("GET", f"/api/products/{int(product_id)}")
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise

    # ---------- tickets ----------
    def list_open_tickets(self):
        return self._request("GET", "/api/tickets")

    def get_ticket(self, ticket_id):
        try:
            return self._request("GET", f"/api/tickets/{int(ticket_id)}")
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise

    def create_ticket(self, name=None):
        return self._request("POST", "/api/tickets", json={"name": name})["id"]

    def delete_ticket(self, ticket_id):
        try:
            self._request("DELETE", f"/api/tickets/{int(ticket_id)}")
        except ApiError as exc:
            if exc.status != 404:  # ya no existe: el resultado buscado
                raise

    def set_pay_method(self, ticket_id, method):
        self._request("PUT", f"/api/tickets/{int(ticket_id)}/pay_method", json={"pay_method": method})

    # ---------- lineas ----------
    def list_items(self, ticket_id):
        try:
            return self._request("GET", f"/api/tickets/{int(ticket_id)}/items")
        except ApiError as exc:
            if exc.status == 404:
                return []
            raise

    def get_item(self, item_id):
        try:
            return self._request("GET", f"/api/items/{int(item_id)}")
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise

    def add_product(self, ticket_id, product_id, qty=1):
        """Agrega una linea. El servidor fija el precio. Devuelve el cuerpo completo."""
        return self._request(
            "POST", f"/api/tickets/{int(ticket_id)}/items", json={"product_id": int(product_id), "qty": int(qty)}
        )

    def add_item(self, ticket_id, product_id, qty, unit_price):
        """Misma firma que core.ticket_service.add_item. unit_price se ignora: manda el servidor."""
        return self.add_product(ticket_id, product_id, qty)["items"][-1]["id"]

    def update_item_qty(self, item_id, new_qty):
        try:
            self._request("PUT", f"/api/items/{int(item_id)}", json={"qty": int(new_qty)})
        except ApiError as exc:
            if exc.status != 404:
                raise

    def remove_item(self, item_id):
        try:
            self._request("DELETE", f"/api/items/{int(item_id)}")
        except ApiError as exc:
            if exc.status != 404:
                raise

    # ---------- cobro ----------
    def stock_warnings_for_ticket(self, ticket_id):
        return self._request("GET", f"/api/tickets/{int(ticket_id)}/stock_warnings")

    def cobrar(self, ticket_id, method):
        """Cobra en la Caja 1. Devuelve (sale_id, warnings). Lanza ApiError si la rechaza."""
        body = self._request("POST", f"/api/tickets/{int(ticket_id)}/charge", json={"pay_method": method})
        return body["sale_id"], body["warnings"]

    def receipt(self, sale_id):
        """Datos del comprobante tal como los arma el servidor (se imprime en esta caja)."""
        return self._request("GET", f"/api/sales/{int(sale_id)}/receipt")
