"""Mi POS - Fase 1.1 en Flet: POS con base de datos real.

Reutiliza core/ sin modificarlo (product_service, ticket_service,
sales_service, config, db_manager). No toca la app Qt (main.py, ui/).

Reglas que este archivo cumple:
- Busqueda: exacto primero (find_product_by_exact_code_or_name); sin
  exacto, 1 candidato -> se agrega; mas de 1 -> lista para elegir (nunca
  el primero automatico); 0 -> "No encontrado: <texto>". "Producto comun"
  nunca se agrega por busqueda ni aparece en la grilla.
- Limpiar ticket, borrar una linea (X o "-" con cantidad 1) y eliminar
  ticket siempre piden confirmacion.
- Medios de pago con los mismos valores que Qt (ui/charge_dialog.py):
  efectivo, credito, debito, transferencia. Solo efectivo pide monto y
  calcula vuelto.
- Foco: tras agregar (busqueda, candidato o grilla) y al cerrarse
  cualquier dialogo, el foco vuelve al buscador (await focus()).
- Flet 1.1.2: ft.run(main), ft.FilledButton, ft.Icons, ft.Colors. No
  existen page.dialog ni page.snack_bar: los dialogos van en page.overlay
  y se quitan de ahi en on_dismiss (Flutter lo avisa al terminar de
  cerrarse). focus() es asincrono: se usa con await en handlers async.
  border_color esta deprecado: se usa border=OutlineInputBorder(...).
"""

import os
import sys

import flet as ft

# Reutilizar core/ del repo (el padre de flet_app/).
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as core_config  # noqa: E402
from core import db_manager  # noqa: E402
from core import product_service as ps  # noqa: E402
from core import sales_service as ss  # noqa: E402
from core import ticket_service as ts  # noqa: E402

TEXT = "#1c2833"
PRIMARY = "#6c3483"
BG = "#f8f2fb"
WHITE = "#ffffff"
MUTED = "#5d6d7e"
ICON = "#34495e"
ERROR = "#a93226"
WARN_BG = "#fff4d6"
WARN_TEXT = "#6e4500"
DISABLED_BG = "#d6d1db"
DISABLED_TEXT = "#5f5966"

COMMON_PRODUCT_NAME = "Producto común"
GRID_LIMIT = 12

# Mismos valores internos que la app Qt (ui/charge_dialog.py).
PAY_METHODS = [
    ("efectivo", "Efectivo"),
    ("credito", "Tarjeta de crédito"),
    ("debito", "Tarjeta de débito"),
    ("transferencia", "Transferencia"),
]


# ---------- Logica pura (sin UI, se prueba en tests/test_flet_logic.py) ----------
def fmt_money(value):
    """Formato chileno: 1500 -> $1.500."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    sign = "-" if n < 0 else ""
    return sign + "$" + f"{abs(n):,}".replace(",", ".")


def parse_price(txt):
    """'$10.500', '10.500', '10,500' -> 10500. Igual que Qt: solo digitos."""
    digits = "".join(ch for ch in (txt or "") if ch.isdigit())
    return int(digits) if digits else 0


def get_next_ticket_number():
    """Numero libre mas bajo entre los tickets abiertos (1, 2, 3...).

    Si existen "Ticket 1" y "Ticket 3", devuelve 2. Si no hay tickets,
    devuelve 1.
    """
    taken = set()
    for t in ts.list_open_tickets():
        name = (t.get("name") or "").strip()
        if name.startswith("Ticket "):
            try:
                taken.add(int(name.replace("Ticket ", "", 1)))
            except ValueError:
                continue
    n = 1
    while n in taken:
        n += 1
    return n


def is_common_product(product):
    return (product.get("name") or "").strip().lower() == COMMON_PRODUCT_NAME.lower()


def find_product(query):
    """Resuelve el texto del buscador.

    Devuelve ("empty", None), ("one", producto), ("many", [productos]) o
    ("none", None). "Producto comun" se trata como no encontrado.
    """
    q = (query or "").strip()
    if not q:
        return "empty", None
    exact = ps.find_product_by_exact_code_or_name(q)
    if exact is not None and not is_common_product(exact):
        return "one", exact
    cand = [p for p in ps.list_products(q) if not is_common_product(p)]
    if len(cand) == 1:
        return "one", cand[0]
    if len(cand) > 1:
        return "many", cand
    return "none", None


def items_total(items):
    """Total del ticket calculado en memoria (no toca updated_at)."""
    return sum(int(i["line_total"]) for i in items)


def low_stock_remaining(product, items):
    """Stock que quedaria tras vender lo que hay en el ticket, si queda en
    o bajo el minimo (como Qt _maybe_alert_low_stock). Si no, None."""
    if is_common_product(product):
        return None
    stock = int(product.get("stock") or 0)
    min_stock = int(product.get("min_stock") or 0)
    in_ticket = sum(int(i["qty"]) for i in items if i["product_id"] == product["id"])
    remaining = stock - in_ticket
    return remaining if remaining <= min_stock else None


def find_empty_ticket(exclude_id=None):
    """Id del ticket abierto vacio mas reciente, o None."""
    for t in ts.list_open_tickets():
        if t["id"] != exclude_id and not ts.list_items(t["id"]):
            return t["id"]
    return None


def cash_status(total, text):
    """Estado del pago en efectivo: (puede_confirmar, mensaje)."""
    if not (text or "").strip():
        return False, ""
    received = parse_price(text)
    if received >= total:
        return True, f"Vuelto: {fmt_money(received - total)}"
    return False, f"Faltan {fmt_money(total - received)}."


def charge_summary(sale_id, method, change, warnings):
    """Aviso final: 'Venta N cobrada. Vuelto: $800. Stock negativo: P1'."""
    parts = [f"Venta {sale_id} cobrada."]
    if method == "efectivo":
        parts.append(f"Vuelto: {fmt_money(change)}.")
    if warnings:
        parts.append("Stock negativo: " + ", ".join(w["product_name"] for w in warnings))
    return " ".join(parts)


def _state_style(bg, fg, radius=12):
    """Boton con colores distintos cuando esta deshabilitado."""
    return ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=radius),
        bgcolor={ft.ControlState.DISABLED: DISABLED_BG, ft.ControlState.DEFAULT: bg},
        color={ft.ControlState.DISABLED: DISABLED_TEXT, ft.ControlState.DEFAULT: fg},
    )


def _outline(color=PRIMARY):
    return ft.OutlineInputBorder(side=ft.BorderSide(width=1, color=color))


# ---------- UI ----------
def main(page: ft.Page):
    page.title = "Mi POS - Flet"
    page.bgcolor = BG
    page.window.width = 1280
    page.window.height = 720
    page.window.min_width = 1000
    page.window.min_height = 650
    db_manager.bootstrap()

    cfg = core_config.load_config()
    business_name = (cfg.get("business_name") or "Mi POS").strip() or "Mi POS"

    current_ticket_id = None

    # ---------- Componentes ----------
    search_input = ft.TextField(
        hint_text="Código o nombre (Enter)",
        autofocus=True,
        color=TEXT,
        hint_style=ft.TextStyle(color=MUTED),
        bgcolor=WHITE,
        border=_outline(),
    )
    ticket_list = ft.ListView(expand=True, spacing=5)
    grid = ft.GridView(
        expand=True, max_extent=190, child_aspect_ratio=2.0, spacing=10, run_spacing=10
    )
    grid_info = ft.Text("", color=MUTED, size=12, visible=False)
    grid_empty = ft.Text(
        "No hay productos para mostrar. Agrégalos en la pestaña Productos de la app principal.",
        color=MUTED,
        visible=False,
    )
    table = ft.DataTable(
        column_spacing=24,
        horizontal_margin=12,
        columns=[
            ft.DataColumn(ft.Text("Producto", color=TEXT, weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Cant", color=TEXT, weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Precio", color=TEXT, weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Total", color=TEXT, weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Acción", color=TEXT, weight=ft.FontWeight.BOLD)),
        ],
    )
    ticket_empty = ft.Text(
        "Ticket sin productos. Escanea o busca un producto, o tócalo en la grilla.",
        color=MUTED,
        visible=False,
    )
    stock_text = ft.Text("", color=WARN_TEXT)
    stock_bar = ft.Container(
        content=stock_text, bgcolor=WARN_BG, padding=8, border_radius=8, visible=False
    )
    total_lbl = ft.Text("$0", size=32, weight=ft.FontWeight.BOLD, color=TEXT)

    # ---------- Dialogos (page.overlay) ----------
    def any_dialog_open():
        return any(isinstance(c, ft.AlertDialog) and c.open for c in page.overlay)

    async def focus_search():
        if any_dialog_open():
            return
        await search_input.focus()

    def open_dialog(dlg):
        # on_dismiss llega cuando Flutter termina de cerrar el dialogo (por
        # boton, Escape o clic fuera): ahi se quita del overlay y el foco
        # vuelve al buscador.
        async def on_dismiss(e):
            if dlg in page.overlay:
                page.overlay.remove(dlg)
            page.update()
            await focus_search()

        dlg.on_dismiss = on_dismiss
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def close_dialog(dlg):
        dlg.open = False
        page.update()

    def show_message(text):
        dlg = ft.AlertDialog(
            title=ft.Text("Mi POS", color=TEXT),
            content=ft.Text(text, color=TEXT),
            bgcolor=WHITE,
            actions=[
                ft.TextButton(
                    "Aceptar",
                    autofocus=True,
                    on_click=lambda e: close_dialog(dlg),
                    style=ft.ButtonStyle(color=PRIMARY),
                )
            ],
        )
        open_dialog(dlg)

    def ask_confirm(title, text, on_yes):
        dlg = ft.AlertDialog(
            title=ft.Text(title, color=TEXT),
            content=ft.Text(text, color=TEXT),
            bgcolor=WHITE,
        )

        def yes(e):
            close_dialog(dlg)
            on_yes()

        dlg.actions = [
            ft.TextButton("Sí", on_click=yes, style=ft.ButtonStyle(color=ERROR)),
            ft.TextButton(
                "No",
                autofocus=True,
                on_click=lambda e: close_dialog(dlg),
                style=ft.ButtonStyle(color=PRIMARY),
            ),
        ]
        open_dialog(dlg)

    # ---------- Tickets ----------
    def make_load_handler(tid):
        async def handler(e):
            load_ticket(tid)
            await focus_search()

        return handler

    def refresh_ticket_list():
        ticket_list.controls = []
        for t in ts.list_open_tickets():
            tid = t["id"]
            label = f'{t["name"]} - {fmt_money(t["pending_total"])}'
            is_current = tid == current_ticket_id
            ticket_list.controls.append(
                ft.FilledButton(
                    label,
                    on_click=make_load_handler(tid),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=12),
                        bgcolor=PRIMARY if is_current else WHITE,
                        color=WHITE if is_current else TEXT,
                    ),
                )
            )

    def load_ticket(tid):
        nonlocal current_ticket_id
        if ts.get_ticket(tid) is None:
            return
        current_ticket_id = tid
        stock_bar.visible = False
        refresh_ui()

    def ensure_ticket():
        nonlocal current_ticket_id
        if current_ticket_id is not None and ts.get_ticket(current_ticket_id) is not None:
            return current_ticket_id
        # Si ya hay tickets abiertos se sigue con el mas reciente en vez de
        # crear uno vacio nuevo en cada lanzamiento.
        open_tickets = ts.list_open_tickets()
        if open_tickets:
            current_ticket_id = open_tickets[0]["id"]
            return current_ticket_id
        current_ticket_id = ts.create_ticket(f"Ticket {get_next_ticket_number()}")
        return current_ticket_id

    async def new_ticket(e):
        nonlocal current_ticket_id
        current_ticket_id = ts.create_ticket(f"Ticket {get_next_ticket_number()}")
        stock_bar.visible = False
        refresh_ui()
        await focus_search()

    def ask_delete_ticket():
        ensure_ticket()

        def do_delete():
            nonlocal current_ticket_id
            ts.delete_ticket(current_ticket_id)
            remaining = ts.list_open_tickets()
            if remaining:
                current_ticket_id = remaining[0]["id"]
            else:
                current_ticket_id = ts.create_ticket(f"Ticket {get_next_ticket_number()}")
            stock_bar.visible = False
            refresh_ui()

        ask_confirm("Eliminar ticket", "¿Eliminar este ticket sin cobrar?", do_delete)

    # ---------- Tabla y total ----------
    def make_qty_handler(item_id, delta):
        async def handler(e):
            item = ts.get_item(item_id)
            if item is None:
                return
            if delta < 0 and item["qty"] <= 1:
                ask_delete_item(item_id)
                return
            ts.update_item_qty(item_id, item["qty"] + delta)
            refresh_ui()
            await focus_search()

        return handler

    def refresh_ui():
        ensure_ticket()
        items = ts.list_items(current_ticket_id)
        rows = []
        for item in items:
            item_id = item["id"]
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item["product_name"], color=TEXT)),
                        ft.DataCell(ft.Text(str(item["qty"]), color=TEXT)),
                        ft.DataCell(ft.Text(fmt_money(item["unit_price"]), color=TEXT)),
                        ft.DataCell(ft.Text(fmt_money(item["line_total"]), color=TEXT)),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(
                                        ft.Icons.REMOVE,
                                        icon_color=ICON,
                                        tooltip="Quitar uno",
                                        on_click=make_qty_handler(item_id, -1),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.ADD,
                                        icon_color=ICON,
                                        tooltip="Agregar uno",
                                        on_click=make_qty_handler(item_id, 1),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.CLOSE,
                                        icon_color=ERROR,
                                        tooltip="Quitar línea",
                                        on_click=lambda e, item_id=item_id: ask_delete_item(item_id),
                                    ),
                                ],
                                spacing=0,
                            )
                        ),
                    ]
                )
            )
        table.rows = rows
        ticket_empty.visible = not items
        total_lbl.value = fmt_money(items_total(items))
        refresh_ticket_list()
        page.update()

    def ask_delete_item(item_id):
        item = ts.get_item(item_id)
        if item is None:
            return

        def do_delete():
            ts.remove_item(item_id)
            refresh_ui()

        ask_confirm("Quitar línea", f'¿Quitar "{item["product_name"]}" del ticket?', do_delete)

    def ask_clear_ticket():
        ensure_ticket()
        items = ts.list_items(current_ticket_id)
        if not items:
            show_message("El ticket ya está vacío.")
            return

        def do_clear():
            for item in ts.list_items(current_ticket_id):
                ts.remove_item(item["id"])
            stock_bar.visible = False
            refresh_ui()

        ask_confirm(
            "Limpiar ticket",
            f"¿Vaciar todo el ticket (Total: {fmt_money(items_total(items))})?",
            do_clear,
        )

    # ---------- Grilla de productos ----------
    def make_grid_handler(product):
        async def handler(e):
            add_product(product)
            await focus_search()

        return handler

    def refresh_grid():
        # "Producto comun" es un producto especial de precio 0, no va en la grilla.
        products = [p for p in ps.list_products("") if not is_common_product(p)]
        shown = products[:GRID_LIMIT]
        grid.controls = [
            ft.FilledButton(
                content=ft.Column(
                    [
                        ft.Text(p["name"], color=TEXT, weight=ft.FontWeight.BOLD, size=13),
                        ft.Text(fmt_money(p["sale_price"]), color=PRIMARY, weight=ft.FontWeight.BOLD, size=13),
                    ],
                    spacing=2,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                on_click=make_grid_handler(p),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    bgcolor=WHITE,
                    color=TEXT,
                ),
            )
            for p in shown
        ]
        grid_empty.visible = not products
        grid_info.visible = len(products) > GRID_LIMIT
        grid_info.value = f"Mostrando {GRID_LIMIT} de {len(products)} productos. Busca por nombre o código para ver el resto."

    def add_product(product):
        ensure_ticket()
        ts.add_item(current_ticket_id, product["id"], 1, product["sale_price"])
        prod = ps.get_product(product["id"]) or product
        remaining = low_stock_remaining(prod, ts.list_items(current_ticket_id))
        if remaining is not None:
            stock_text.value = (
                f'Stock bajo: "{prod["name"]}" quedaría con {remaining} '
                f'(mínimo {int(prod.get("min_stock") or 0)}). La venta sigue normal.'
            )
            stock_bar.visible = True
        else:
            stock_bar.visible = False
        refresh_ui()

    # ---------- Busqueda ----------
    async def add_item_by_search(e):
        q = (search_input.value or "").strip()
        kind, result = find_product(q)
        if kind == "empty":
            show_message("Escribe nombre o código para buscar.")
            return
        if kind == "none":
            # No se borra el texto: la cajera ve que escribio y lo corrige.
            show_message(f"No encontrado: {q}")
            return
        search_input.value = ""
        if kind == "one":
            add_product(result)
            await focus_search()
        else:
            page.update()
            show_candidates(result)

    def show_candidates(cand):
        dlg = ft.AlertDialog(title=ft.Text("Elegir producto", color=TEXT), bgcolor=WHITE)

        def choose(p):
            close_dialog(dlg)
            add_product(p)

        buttons = [
            ft.FilledButton(
                f'{p["name"]} - {fmt_money(p["sale_price"])}',
                on_click=lambda e, p=p: choose(p),
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    bgcolor=WHITE,
                    color=TEXT,
                ),
            )
            for p in cand
        ]
        dlg.content = ft.Column(
            buttons, tight=True, scroll=ft.ScrollMode.AUTO, height=min(52 * len(buttons), 360)
        )
        dlg.actions = [
            ft.TextButton("Cancelar", on_click=lambda e: close_dialog(dlg), style=ft.ButtonStyle(color=PRIMARY))
        ]
        open_dialog(dlg)

    search_input.on_submit = add_item_by_search

    # ---------- Cobro ----------
    def after_charge():
        """Tras cobrar: reutiliza un ticket vacio si existe, si no crea uno."""
        nonlocal current_ticket_id
        empty = find_empty_ticket()
        if empty is not None:
            current_ticket_id = empty
        else:
            current_ticket_id = ts.create_ticket(f"Ticket {get_next_ticket_number()}")
        stock_bar.visible = False
        refresh_ui()

    def open_charge_dialog(e):
        try:
            tid = ensure_ticket()
            items = ts.list_items(tid)
            total = items_total(items)
            if not items or total <= 0:
                show_message("El ticket está vacío.")
                return
            warnings = ss.stock_warnings_for_ticket(tid)
            state = {"charging": False}

            metodo = ft.RadioGroup(
                value="efectivo",
                content=ft.Column(
                    [
                        ft.Radio(value=v, label=label, label_style=ft.TextStyle(color=TEXT))
                        for v, label in PAY_METHODS
                    ]
                ),
            )
            recibido = ft.TextField(
                label="Monto recibido",
                autofocus=True,
                color=TEXT,
                label_style=ft.TextStyle(color=MUTED),
                hint_text="Ej: 1.000",
                hint_style=ft.TextStyle(color=MUTED),
                bgcolor=WHITE,
                border=_outline(),
                keyboard_type=ft.KeyboardType.NUMBER,
            )
            status_lbl = ft.Text("", size=18, weight=ft.FontWeight.BOLD, color=PRIMARY)
            confirmar_btn = ft.FilledButton("Confirmar", style=_state_style(PRIMARY, WHITE))

            content = [
                ft.Text(f"Total: {fmt_money(total)}", color=TEXT, size=22, weight=ft.FontWeight.BOLD),
            ]
            if warnings:
                detail = ", ".join(
                    f'{w["product_name"]} (quedaría en {w["stock_resultante"]})' for w in warnings
                )
                content.append(
                    ft.Container(
                        content=ft.Text(
                            f"Atención, stock negativo tras cobrar: {detail}. La venta se puede confirmar igual.",
                            color=WARN_TEXT,
                        ),
                        bgcolor=WARN_BG,
                        padding=8,
                        border_radius=8,
                    )
                )
            content += [metodo, recibido, status_lbl]

            def update_charge_state():
                if metodo.value != "efectivo":
                    recibido.visible = False
                    status_lbl.value = ""
                    confirmar_btn.disabled = state["charging"]
                else:
                    recibido.visible = True
                    ok, msg = cash_status(total, recibido.value)
                    status_lbl.value = msg
                    status_lbl.color = PRIMARY if ok else ERROR
                    confirmar_btn.disabled = state["charging"] or not ok
                page.update()

            async def on_method_change(e):
                update_charge_state()
                if metodo.value == "efectivo":
                    await recibido.focus()

            dlg = ft.AlertDialog(
                title=ft.Text("Cobrar", color=TEXT),
                content=ft.Column(content, tight=True, width=380),
                bgcolor=WHITE,
            )

            async def confirmar(e):
                # Flag + boton deshabilitado: un doble clic (o Enter + clic)
                # nunca cobra dos veces ni muestra errores del ticket nuevo.
                if state["charging"]:
                    return
                method = metodo.value
                received = parse_price(recibido.value)
                if confirmar_btn.disabled or (method == "efectivo" and received < total):
                    # Enter con monto insuficiente: Flutter saca el foco del
                    # campo al enviar; se devuelve para que siga escribiendo.
                    if method == "efectivo":
                        await recibido.focus()
                    return
                state["charging"] = True
                confirmar_btn.disabled = True
                page.update()
                try:
                    ts.set_pay_method(tid, method)
                    sale_id, sale_warnings = ss.cobrar_ticket(tid)
                except ValueError as exc:
                    state["charging"] = False
                    update_charge_state()
                    show_message(str(exc))
                    return
                close_dialog(dlg)
                after_charge()
                show_message(charge_summary(sale_id, method, received - total, sale_warnings))

            metodo.on_change = on_method_change
            recibido.on_change = lambda e: update_charge_state()
            recibido.on_submit = confirmar
            confirmar_btn.on_click = confirmar
            dlg.actions = [
                confirmar_btn,
                ft.TextButton("Cancelar", on_click=lambda e: close_dialog(dlg), style=ft.ButtonStyle(color=PRIMARY)),
            ]
            update_charge_state()
            open_dialog(dlg)
        except Exception as exc:
            show_message(f"Error al cobrar: {exc}")

    # ---------- Layout ----------
    sidebar = ft.Container(
        width=200,
        bgcolor=WHITE,
        padding=10,
        content=ft.Column(
            [
                ft.Text(business_name, size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text("Tickets", color=TEXT, weight=ft.FontWeight.BOLD),
                ticket_list,
                ft.FilledButton("Nuevo ticket", on_click=new_ticket, style=_state_style(PRIMARY, WHITE)),
                ft.TextButton(
                    "Limpiar ticket",
                    on_click=lambda e: ask_clear_ticket(),
                    style=ft.ButtonStyle(color=PRIMARY),
                ),
                ft.TextButton(
                    "Eliminar ticket",
                    on_click=lambda e: ask_delete_ticket(),
                    style=ft.ButtonStyle(color=ERROR),
                ),
            ],
            expand=True,
        ),
    )

    cobrar_btn = ft.FilledButton(
        "COBRAR",
        on_click=open_charge_dialog,
        style=_state_style(PRIMARY, WHITE),
        height=60,
    )

    main_col = ft.Column(
        [
            search_input,
            grid_info,
            grid_empty,
            ft.Container(content=grid, height=170),
            stock_bar,
            ft.Column(
                [
                    # Scroll horizontal: la columna Accion nunca queda cortada.
                    ft.Row([table], scroll=ft.ScrollMode.AUTO),
                    ticket_empty,
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ],
        expand=True,
        spacing=10,
    )

    right_card = ft.Container(
        width=250,
        bgcolor=WHITE,
        padding=16,
        content=ft.Column(
            [
                ft.Text("Total", color=TEXT, weight=ft.FontWeight.BOLD),
                total_lbl,
                cobrar_btn,
                ft.Text("El medio de pago se elige al cobrar.", color=MUTED, size=12),
            ],
            spacing=12,
        ),
    )

    page.add(ft.Row([sidebar, main_col, right_card], expand=True, spacing=10))

    ensure_ticket()
    refresh_grid()
    refresh_ui()


if __name__ == "__main__":
    ft.run(main)
