"""Mi POS - API HTTP de la Caja 1 (Fase 5.1, multi-caja).

Corre en la Caja 1 y expone las operaciones del POS usando los servicios de
core/ contra la base real de esa maquina. Las cajas cliente no tocan ninguna
base: todo pasa por aqui. Los IDs de venta y el stock los decide solo este
servidor (core.sales_service.cobrar_ticket).

Alcance: solo el flujo de POS. Autenticacion por clave compartida
(X-Caja-Token); sin TLS (shortcut: red WiFi del local, agregar TLS si deja de ser
de confianza). El servidor no se empaqueta en esta fase.
"""

import hmac
import time

from flask import Flask, jsonify, request

from core import config as core_config
from core import db_manager
from core import product_service as ps
from core import sales_service as ss
from core import ticket_service as ts
from flet_app.multicaja import ensure_api_token

API_VERSION = 1
PAY_METHODS = ("efectivo", "credito", "debito", "transferencia")
_STARTED = time.time()  # para uptime_s en /api/health


def _err(message, status):
    return jsonify({"error": message}), status


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _int(value, name, minimum=None):
    """Entero valido o ValueError con el nombre del campo (no acepta bool ni texto)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} debe ser un numero entero.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} debe ser al menos {minimum}.")
    return value


def create_app():
    app = Flask(__name__)
    app.json.ensure_ascii = False  # tildes y ñ legibles en la respuesta

    @app.before_request
    def _auth():
        """Toda ruta (salvo /api/health) exige la clave compartida de config.json.

        Sin clave configurada la API NO queda abierta: responde 401 a todo. El
        arranque (run) genera una clave si falta, asi que esto es la red de seguridad.
        """
        if request.path == "/api/health":
            return None
        token = str(core_config.load_config().get("api_token") or "").strip()
        sent = request.headers.get("X-Caja-Token", "")
        if not token or not hmac.compare_digest(sent.encode("utf-8"), token.encode("utf-8")):
            return _err("Clave de la Caja 1 incorrecta o ausente.", 401)
        return None

    @app.errorhandler(404)
    def _not_found(_e):
        return _err("Ruta no encontrada.", 404)

    @app.errorhandler(405)
    def _bad_method(_e):
        return _err("Metodo no permitido.", 405)

    @app.errorhandler(Exception)
    def _unexpected(exc):
        # Un error inesperado nunca debe devolver el traceback a la red.
        app.logger.exception("Error en la API")
        return _err("Error interno del servidor.", 500)

    # ---------- Estado ----------
    @app.get("/api/health")
    def health():
        cfg = core_config.load_config()
        return jsonify({
            "ok": True,
            "api_version": API_VERSION,
            "business_name": cfg.get("business_name") or "Mi POS",
            "uptime_s": int(time.time() - _STARTED),
        })

    @app.get("/api/config")
    def config():
        """Datos del negocio para el comprobante (cada caja imprime con los de la Caja 1)."""
        cfg = core_config.load_config()
        return jsonify({
            "business_name": str(cfg.get("business_name") or "Mi POS"),
            "rut": str(cfg.get("rut") or ""),
            "address": str(cfg.get("address") or ""),
            "phone": str(cfg.get("phone") or ""),
            "ticket_prefix": cfg.get("ticket_prefix") if cfg.get("ticket_prefix") in ("Ticket", "Mesa") else "Ticket",
        })

    # ---------- Productos ----------
    @app.get("/api/products")
    def products():
        return jsonify(ps.list_products(request.args.get("q", "")))

    @app.get("/api/products/exact")
    def product_exact():
        product = ps.find_product_by_exact_code_or_name(request.args.get("q", ""))
        return jsonify(product)  # null si no hay coincidencia exacta

    @app.get("/api/products/<int:product_id>")
    def product_get(product_id):
        product = ps.get_product(product_id)
        if product is None:
            return _err("Producto no existe.", 404)
        return jsonify(product)

    # ---------- Tickets ----------
    @app.get("/api/tickets")
    def tickets_list():
        return jsonify(ts.list_open_tickets())

    @app.post("/api/tickets")
    def tickets_create():
        name = _json_body().get("name")
        if name is not None and not isinstance(name, str):
            return _err("name debe ser texto.", 400)
        tid = ts.create_ticket(name)
        return jsonify(ts.get_ticket(tid)), 201

    @app.get("/api/tickets/<int:ticket_id>")
    def ticket_get(ticket_id):
        ticket = ts.get_ticket(ticket_id)
        if ticket is None:
            return _err("Ticket no existe.", 404)
        return jsonify(ticket)

    @app.delete("/api/tickets/<int:ticket_id>")
    def ticket_delete(ticket_id):
        if ts.get_ticket(ticket_id) is None:
            return _err("Ticket no existe.", 404)
        ts.delete_ticket(ticket_id)
        return jsonify({"ok": True})

    @app.put("/api/tickets/<int:ticket_id>/pay_method")
    def ticket_pay_method(ticket_id):
        method = _json_body().get("pay_method")
        if method not in PAY_METHODS:
            return _err("Medio de pago no valido.", 400)
        if ts.get_ticket(ticket_id) is None:
            return _err("Ticket no existe.", 404)
        ts.set_pay_method(ticket_id, method)
        return jsonify(ts.get_ticket(ticket_id))

    # ---------- Lineas del ticket ----------
    @app.get("/api/tickets/<int:ticket_id>/items")
    def items_list(ticket_id):
        if ts.get_ticket(ticket_id) is None:
            return _err("Ticket no existe.", 404)
        return jsonify(ts.list_items(ticket_id))

    @app.post("/api/tickets/<int:ticket_id>/items")
    def items_add(ticket_id):
        body = _json_body()
        try:
            product_id = _int(body.get("product_id"), "product_id", 1)
            qty = _int(body.get("qty", 1), "qty", 1)
        except ValueError as exc:
            return _err(str(exc), 400)
        if ts.get_ticket(ticket_id) is None:
            return _err("Ticket no existe.", 404)
        product = ps.get_product(product_id)
        if product is None or not product["is_active"]:
            return _err("Producto no existe o esta desactivado.", 404)
        # El precio lo fija el servidor: una caja no puede vender a otro precio.
        ts.add_item(ticket_id, product_id, qty, product["sale_price"])
        return jsonify({"items": ts.list_items(ticket_id), "product": ps.get_product(product_id),
                        "ticket": ts.get_ticket(ticket_id)}), 201

    @app.get("/api/items/<int:item_id>")
    def item_get(item_id):
        item = ts.get_item(item_id)
        if item is None:
            return _err("Linea no existe.", 404)
        return jsonify(item)

    @app.put("/api/items/<int:item_id>")
    def item_qty(item_id):
        try:
            qty = _int(_json_body().get("qty"), "qty")  # <= 0 elimina la linea (core)
        except ValueError as exc:
            return _err(str(exc), 400)
        item = ts.get_item(item_id)
        if item is None:
            return _err("Linea no existe.", 404)
        ts.update_item_qty(item_id, qty)
        return jsonify({"items": ts.list_items(item["ticket_id"]), "ticket": ts.get_ticket(item["ticket_id"])})

    @app.delete("/api/items/<int:item_id>")
    def item_delete(item_id):
        item = ts.get_item(item_id)
        if item is None:
            return _err("Linea no existe.", 404)
        ts.remove_item(item_id)
        return jsonify({"items": ts.list_items(item["ticket_id"]), "ticket": ts.get_ticket(item["ticket_id"])})

    # ---------- Cobro ----------
    @app.get("/api/tickets/<int:ticket_id>/stock_warnings")
    def stock_warnings(ticket_id):
        if ts.get_ticket(ticket_id) is None:
            return _err("Ticket no existe.", 404)
        return jsonify(ss.stock_warnings_for_ticket(ticket_id))

    @app.post("/api/tickets/<int:ticket_id>/charge")
    def charge(ticket_id):
        method = _json_body().get("pay_method")
        if method not in PAY_METHODS:
            return _err("Medio de pago no valido.", 400)
        if ts.get_ticket(ticket_id) is None:
            return _err("Ticket no existe (puede haberlo cobrado otra caja).", 404)
        ts.set_pay_method(ticket_id, method)
        try:
            sale_id, warnings = ss.cobrar_ticket(ticket_id)
        except ValueError as exc:  # ticket vacio o ya cobrado
            return _err(str(exc), 409)
        return jsonify({"sale_id": sale_id, "warnings": warnings}), 201

    @app.get("/api/sales/<int:sale_id>/receipt")
    def receipt(sale_id):
        """Datos del comprobante: los arma el servidor, la caja imprime."""
        # Import local: boletas importa fpdf solo al generar el PDF, no aqui.
        from flet_app import boletas as bol

        try:
            data = bol.build_receipt(sale_id)
        except bol.BoletaError:
            return _err("Venta no existe.", 404)
        return jsonify(data)

    return app


def run(host="0.0.0.0", port=8780, bootstrap=True):
    """Arranca la API en la Caja 1 con el servidor de desarrollo de Flask.

    shortcut: werkzeug dev server (multihilo, sin TLS), suficiente para 2-3
    cajas en el WiFi del local; usar waitress si hay mas carga o se empaqueta.
    """
    if bootstrap:
        db_manager.bootstrap()
    ensure_api_token()  # sin clave la API no arranca abierta: se genera y se guarda
    create_app().run(host=host, port=port, threaded=True, use_reloader=False)
