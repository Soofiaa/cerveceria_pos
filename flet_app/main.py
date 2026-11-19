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
- Fase 2: la barra lateral cambia entre POS y Productos
  (flet_app/productos_view.py); al volver al POS la grilla se actualiza.
- La grilla de productos solo aparece al escribir en el buscador (con
  muchos productos llenaria la pantalla) y se esconde al agregar.
"""

import asyncio
import os
import sys
import webbrowser

import flet as ft

# Reutilizar core/ del repo (el padre de flet_app/).
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config as core_config  # noqa: E402
from core import db_manager  # noqa: E402
from core import product_service as ps  # noqa: E402
from core import sales_service as ss  # noqa: E402
from core import ticket_service as ts  # noqa: E402
from flet_app import boletas as bol  # noqa: E402
from flet_app.productos_view import ProductosView  # noqa: E402

# Paleta "lila" de la maqueta moderna (Mi Pos Maqueta Interfaz Moderna).
# TEXT y MUTED se mantienen mas oscuros que en la maqueta para que el
# texto secundario cumpla contraste >= 4.5:1 sobre blanco.
TEXT = "#1c2833"
PRIMARY = "#6c3483"
BG = "#f6eff7"
WHITE = "#ffffff"
SURFACE2 = "#efe3f1"
BORDER = "#e2d0e6"
MUTED = "#5d6d7e"
ICON = "#34495e"
ERROR = "#a93226"
WARN_BG = "#fff4d6"
WARN_TEXT = "#6e4500"
WARN_BADGE = "#f1c40f"
DISABLED_BG = "#d6d1db"
DISABLED_TEXT = "#5f5966"
# Montos en monoespaciada, como la maqueta (Consolas viene con Windows).
MONO = "Consolas"

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


def search_grid_products(query, limit=GRID_LIMIT):
    """Productos que la grilla muestra para el texto del buscador.

    Con el buscador vacio no muestra nada: con muchos productos la grilla
    llenaria la pantalla, asi que solo aparece al buscar. Devuelve
    (productos_a_mostrar, total_de_coincidencias). "Producto comun" nunca
    aparece.
    """
    q = (query or "").strip()
    if not q:
        return [], 0
    matches = [p for p in ps.list_products(q) if not is_common_product(p)]
    return matches[:limit], len(matches)


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


def _card(content, padding=16, **kwargs):
    """Tarjeta de la maqueta: blanca, borde de 1px, radio 14, sombra suave."""
    return ft.Container(
        content=content,
        bgcolor=WHITE,
        border=ft.Border.all(1, BORDER),
        border_radius=14,
        padding=padding,
        shadow=ft.BoxShadow(blur_radius=10, spread_radius=0, color="#140f1e2d", offset=ft.Offset(0, 2)),
        **kwargs,
    )


def _qty_style():
    """Botones - / + chicos con borde, como la maqueta."""
    return ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=8),
        side=ft.BorderSide(width=1, color=BORDER),
        bgcolor=SURFACE2,
        padding=4,
    )


def _caps(text):
    """Etiqueta chica en mayusculas atenuada ("TOTAL A COBRAR")."""
    return ft.Text(text.upper(), size=11, weight=ft.FontWeight.W_800, color=MUTED)


# ---------- UI ----------
def main(page: ft.Page):
    page.title = "Mi POS - Flet"
    page.bgcolor = BG
    page.padding = 0
    # Semilla lila: radios, switches y focos toman el primario del tema.
    page.theme = ft.Theme(color_scheme_seed=PRIMARY, font_family="Segoe UI")
    # Siempre claro: con Windows en modo oscuro los controles sin color
    # propio (desplegables, menus) salian con texto casi blanco.
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1280
    page.window.height = 720
    page.window.min_width = 1000
    page.window.min_height = 650
    db_manager.bootstrap()

    cfg = core_config.load_config()
    business_name = (cfg.get("business_name") or "Mi POS").strip() or "Mi POS"

    current_ticket_id = None
    # Ultima venta cobrada en esta sesion (para reimprimir o reenviar).
    last_sale = {}

    # ---------- Componentes ----------
    search_input = ft.TextField(
        hint_text="Buscar producto o código (Enter)",
        autofocus=True,
        color=TEXT,
        hint_style=ft.TextStyle(color=MUTED),
        bgcolor=SURFACE2,
        filled=True,
        prefix_icon=ft.Icons.SEARCH,
        border={
            ft.ControlState.DEFAULT: ft.OutlineInputBorder(
                side=ft.BorderSide(width=1, color=BORDER), border_radius=10
            ),
            ft.ControlState.FOCUSED: ft.OutlineInputBorder(
                side=ft.BorderSide(width=2, color=PRIMARY), border_radius=10
            ),
        },
        expand=True,
    )
    ticket_list = ft.ListView(expand=True, spacing=6)
    grid = ft.GridView(
        expand=True, max_extent=190, child_aspect_ratio=2.1, spacing=9, run_spacing=9
    )
    grid_info = ft.Text("", color=MUTED, size=12, visible=False)
    grid_empty = ft.Text("", color=MUTED, visible=False)
    # La grilla solo se ve mientras hay texto en el buscador.
    grid_box = ft.Container(content=grid, height=170, visible=False)
    def _head(text, numeric=False):
        return ft.DataColumn(
            ft.Text(text.upper(), size=11, weight=ft.FontWeight.W_800, color=MUTED),
            numeric=numeric,
        )

    table = ft.DataTable(
        column_spacing=18,
        horizontal_margin=6,
        heading_row_height=36,
        data_row_min_height=48,
        divider_thickness=1,
        columns=[
            _head("Producto"),
            _head("Cant"),
            _head("Precio", numeric=True),
            _head("Subtotal", numeric=True),
            _head(""),
        ],
    )
    ticket_empty = ft.Container(
        content=ft.Column(
            [
                ft.Text("Ticket vacío.", color=MUTED, size=14, weight=ft.FontWeight.W_600),
                ft.Text(
                    "Escanea un código o escribe el nombre: los productos aparecen al buscar.",
                    color=MUTED,
                    size=13,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(vertical=22),
        visible=False,
    )
    stock_text = ft.Text("", color=WARN_TEXT)
    stock_bar = ft.Container(
        content=stock_text, bgcolor=WARN_BG, padding=10, border_radius=10, visible=False
    )
    total_lbl = ft.Text(
        "$0", size=40, weight=ft.FontWeight.BOLD, color=TEXT, font_family=MONO
    )
    subtotal_lbl = ft.Text("$0", color=TEXT, font_family=MONO, weight=ft.FontWeight.W_600)
    items_lbl = ft.Text("0", color=TEXT, font_family=MONO, weight=ft.FontWeight.W_600)
    ticket_title = ft.Text("Ticket actual", size=15, weight=ft.FontWeight.BOLD, color=TEXT)

    # ---------- Dialogos (page.overlay) ----------
    def any_dialog_open():
        return any(isinstance(c, ft.AlertDialog) and c.open for c in page.overlay)

    async def focus_search():
        if any_dialog_open():
            return
        try:
            await search_input.focus()
        except Exception:
            # El foco es best-effort: si el control no esta visible, no
            # tiene que romper el flujo (tambien lo usan los tests).
            pass

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
            is_current = tid == current_ticket_id
            ticket_list.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.RECEIPT_LONG,
                                size=18,
                                color=PRIMARY if is_current else MUTED,
                            ),
                            ft.Text(
                                t["name"] or "",
                                color=TEXT,
                                weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.W_600,
                                expand=True,
                                no_wrap=True,
                            ),
                            ft.Text(
                                fmt_money(t["pending_total"]),
                                color=TEXT if is_current else MUTED,
                                font_family=MONO,
                                size=13,
                            ),
                        ],
                        spacing=8,
                    ),
                    bgcolor=SURFACE2 if is_current else WHITE,
                    border=ft.Border.all(1.5 if is_current else 1, PRIMARY if is_current else BORDER),
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    on_click=make_load_handler(tid),
                    ink=True,
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
                        ft.DataCell(
                            ft.Text(item["product_name"], color=TEXT, weight=ft.FontWeight.W_600)
                        ),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(
                                        ft.Icons.REMOVE,
                                        icon_color=ICON,
                                        icon_size=16,
                                        tooltip="Quitar uno",
                                        style=_qty_style(),
                                        on_click=make_qty_handler(item_id, -1),
                                    ),
                                    ft.Container(
                                        ft.Text(
                                            str(item["qty"]),
                                            color=TEXT,
                                            font_family=MONO,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        width=28,
                                        alignment=ft.Alignment.CENTER,
                                    ),
                                    ft.IconButton(
                                        ft.Icons.ADD,
                                        icon_color=ICON,
                                        icon_size=16,
                                        tooltip="Agregar uno",
                                        style=_qty_style(),
                                        on_click=make_qty_handler(item_id, 1),
                                    ),
                                ],
                                spacing=2,
                            )
                        ),
                        ft.DataCell(
                            ft.Text(fmt_money(item["unit_price"]), color=TEXT, font_family=MONO)
                        ),
                        ft.DataCell(
                            ft.Text(fmt_money(item["line_total"]), color=TEXT, font_family=MONO)
                        ),
                        ft.DataCell(
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                icon_color=ERROR,
                                icon_size=19,
                                tooltip="Quitar línea",
                                on_click=lambda e, item_id=item_id: ask_delete_item(item_id),
                            )
                        ),
                    ]
                )
            )
        table.rows = rows
        table.visible = bool(items)
        ticket_empty.visible = not items
        total = items_total(items)
        total_lbl.value = fmt_money(total)
        subtotal_lbl.value = fmt_money(total)
        items_lbl.value = str(sum(int(i["qty"]) for i in items))
        current = ts.get_ticket(current_ticket_id)
        ticket_title.value = f'Ticket actual · {(current or {}).get("name") or ""}'.rstrip(" ·")
        cobrar_btn.disabled = not items
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
            # Como al escanear: se agrega, el buscador se limpia y la
            # grilla se esconde para seguir con el siguiente producto.
            search_input.value = ""
            refresh_grid()
            add_product(product)
            await focus_search()

        return handler

    def refresh_grid():
        # Solo muestra coincidencias del texto escrito; vacio = sin grilla.
        q = (search_input.value or "").strip()
        shown, total_matches = search_grid_products(q)

        def card(p):
            stock = int(p.get("stock") or 0)
            low = stock <= int(p.get("min_stock") or 0)
            code = (p.get("barcode") or "").strip()
            sub = (f"Cód. {code} · " if code else "") + f"Stock {stock}"
            price_row = [
                ft.Text(
                    fmt_money(p["sale_price"]), color=PRIMARY, weight=ft.FontWeight.BOLD,
                    size=13.5, font_family=MONO,
                )
            ]
            if low:
                # Amarillo solo avisa; texto oscuro fijo para que se lea.
                price_row.append(
                    ft.Container(
                        ft.Text("Stock bajo", size=10.5, weight=ft.FontWeight.W_800, color=TEXT),
                        bgcolor=WARN_BADGE,
                        border_radius=5,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=1),
                    )
                )
            parts = [
                ft.Text(
                    p["name"], color=TEXT, weight=ft.FontWeight.BOLD, size=13,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(sub, color=MUTED, size=11.5, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(expand=True),
                ft.Row(price_row, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]
            return ft.Container(
                content=ft.Column(parts, spacing=2),
                bgcolor=WHITE,
                border=ft.Border.all(1, BORDER),
                border_radius=12,
                padding=10,
                on_click=make_grid_handler(p),
                ink=True,
            )

        grid.controls = [card(p) for p in shown]
        grid_box.visible = bool(shown)
        # Con pocos resultados basta una fila; si no, dos filas con scroll.
        grid_box.height = 82 if len(shown) <= 3 else 170
        grid_empty.visible = bool(q) and total_matches == 0
        grid_empty.value = f'Sin resultados para "{q}".'
        grid_info.visible = total_matches > GRID_LIMIT
        grid_info.value = (
            f"Mostrando {GRID_LIMIT} de {total_matches} coincidencias. "
            "Escribe más del nombre o el código para acotar."
        )

    def on_search_change(e):
        refresh_grid()
        page.update()

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

    # ---------- Vista Productos (Fase 2) ----------
    # Al crear/editar/quitar un producto, la grilla del POS se actualiza.
    productos_view = ProductosView(page, on_products_changed=refresh_grid)

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
        refresh_grid()
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
    search_input.on_change = on_search_change

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

    # ---------- Boleta (comprobante interno): imprimir y enviar ----------
    def _field(label, value="", **kwargs):
        return ft.TextField(
            label=label,
            value="" if value is None else str(value),
            color=TEXT,
            label_style=ft.TextStyle(color=MUTED),
            bgcolor=WHITE,
            border=_outline(BORDER),
            **kwargs,
        )

    def receipt_for(sale_id, received):
        return bol.build_receipt(sale_id, received=received)

    async def print_sale(sale_id, received):
        _cfg, boleta_cfg, _smtp = bol.load_settings()
        try:
            data = receipt_for(sale_id, received)
            await asyncio.to_thread(bol.print_receipt, data, boleta_cfg)
        except bol.BoletaError as exc:
            show_message(f"No se pudo imprimir: {exc}")
            return
        except Exception as exc:  # driver o cola de impresion de Windows
            show_message(f"No se pudo imprimir: {exc}")
            return
        show_message(f"Comprobante {sale_id} enviado a imprimir.")

    def ask_email_sale(sale_id, received):
        _cfg, _boleta, smtp_cfg = bol.load_settings()
        to_input = _field("Correo del cliente", autofocus=True, keyboard_type=ft.KeyboardType.EMAIL)
        status = ft.Text("", color=ERROR)
        dlg = ft.AlertDialog(
            title=ft.Text("Enviar comprobante por correo", color=TEXT),
            bgcolor=WHITE,
        )
        smtp_ok = bol.smtp_is_configured(smtp_cfg)
        hint = (
            f'Se envía desde {smtp_cfg.get("sender") or smtp_cfg.get("user")} con el PDF adjunto.'
            if smtp_ok
            else "El envío directo no está configurado: usa «Abrir programa de correo» "
            "o actívalo en Configuración."
        )
        dlg.content = ft.Column(
            [to_input, ft.Text(hint, color=MUTED, size=12), status], tight=True, width=380
        )

        def validate():
            to = (to_input.value or "").strip()
            if not bol.is_valid_email(to):
                status.value = "Escribe un correo válido, por ejemplo cliente@correo.cl."
                page.update()
                return None
            return to

        async def send_smtp(e):
            to = validate()
            if to is None:
                return
            send_btn.disabled = True
            status.color = MUTED
            status.value = "Enviando…"
            page.update()
            try:
                data = receipt_for(sale_id, received)
                pdf_path = bol.build_pdf(data, paper_mm=80)
                await asyncio.to_thread(bol.send_email_smtp, smtp_cfg, to, data, pdf_path)
            except bol.BoletaError as exc:
                send_btn.disabled = False
                status.color = ERROR
                status.value = str(exc)
                page.update()
                return
            close_dialog(dlg)
            show_message(f"Comprobante {sale_id} enviado a {to}.")

        def open_mail_client(e):
            to = validate()
            if to is None:
                return
            data = receipt_for(sale_id, received)
            webbrowser.open(bol.mailto_url(to, data))
            close_dialog(dlg)

        send_btn = ft.FilledButton(
            "Enviar", on_click=send_smtp, style=_state_style(PRIMARY, WHITE, radius=10),
            disabled=not smtp_ok,
        )
        to_input.on_submit = send_smtp if smtp_ok else open_mail_client
        dlg.actions = [
            send_btn,
            ft.TextButton("Abrir programa de correo", on_click=open_mail_client,
                          style=ft.ButtonStyle(color=PRIMARY)),
            ft.TextButton("Cancelar", on_click=lambda e: close_dialog(dlg),
                          style=ft.ButtonStyle(color=PRIMARY)),
        ]
        open_dialog(dlg)

    def show_sale_done(sale_id, summary, received):
        """Aviso de venta cobrada con opciones de comprobante.

        Aceptar tiene el foco: Enter cierra y la cajera sigue escaneando.
        Queda guardada como "ultimo comprobante" para reimprimir o enviar
        despues, si la cajera cerro el aviso sin hacerlo.
        """
        last_sale.update(sale_id=sale_id, summary=summary, received=received)
        last_receipt_btn.visible = True
        dlg = ft.AlertDialog(
            title=ft.Text("Venta cobrada", color=TEXT),
            content=ft.Text(summary, color=TEXT),
            bgcolor=WHITE,
        )

        async def do_print(e):
            close_dialog(dlg)
            await print_sale(sale_id, received)

        def do_email(e):
            close_dialog(dlg)
            ask_email_sale(sale_id, received)

        actions = [
            ft.TextButton("Imprimir comprobante", icon=ft.Icons.PRINT, on_click=do_print,
                          style=ft.ButtonStyle(color=PRIMARY)),
        ]
        # El correo es opcional: solo aparece si se activo en Configuracion.
        _cfg, _boleta, smtp_cfg = bol.load_settings()
        if bol.email_enabled(smtp_cfg):
            actions.append(
                ft.TextButton("Enviar por correo", icon=ft.Icons.EMAIL_OUTLINED, on_click=do_email,
                              style=ft.ButtonStyle(color=PRIMARY))
            )
        actions.append(
            ft.FilledButton("Aceptar", autofocus=True, on_click=lambda e: close_dialog(dlg),
                            style=_state_style(PRIMARY, WHITE, radius=10))
        )
        dlg.actions = actions
        open_dialog(dlg)

    def open_settings_dialog(e=None):
        """Configuracion: impresora de boletas y correo (opcional)."""
        _cfg, boleta_cfg, smtp_cfg = bol.load_settings()
        printers = bol.list_windows_printers()
        current_printer = boleta_cfg.get("printer") or bol.default_windows_printer()
        mode = ft.Dropdown(
            label="Cómo imprimir",
            value=boleta_cfg.get("print_mode") or "windows",
            options=[ft.DropdownOption(key=k, text=v) for k, v in bol.PRINT_MODES.items()],
            width=380,
        )
        printer = ft.Dropdown(
            label="Impresora de Windows",
            value=current_printer if current_printer in printers else None,
            options=[ft.DropdownOption(key=p, text=p) for p in printers],
            width=380,
        )
        paper = ft.Dropdown(
            label="Ancho de papel",
            value=str(boleta_cfg.get("paper_mm") or 80),
            options=[ft.DropdownOption(key="80", text="80 mm"), ft.DropdownOption(key="58", text="58 mm")],
            width=180,
        )
        host = _field("IP de la térmica (red)", boleta_cfg.get("host"), width=240)
        port = _field("Puerto", boleta_cfg.get("port") or 9100, width=120,
                      keyboard_type=ft.KeyboardType.NUMBER)
        net_row = ft.Row([host, port])
        smtp_host = _field("Servidor SMTP", smtp_cfg.get("host"), width=260)
        smtp_port = _field("Puerto", smtp_cfg.get("port"), width=100, keyboard_type=ft.KeyboardType.NUMBER)
        smtp_sec = ft.Dropdown(
            label="Seguridad",
            value=smtp_cfg.get("security") or "starttls",
            options=[ft.DropdownOption(key="starttls", text="STARTTLS (587)"),
                     ft.DropdownOption(key="ssl", text="SSL (465)")],
            width=380,
        )
        smtp_user = _field("Usuario (correo de envío)", smtp_cfg.get("user"), width=380)
        smtp_pass = _field(
            "Contraseña de aplicación",
            "",
            width=380,
            password=True,
            can_reveal_password=True,
            hint_text="Guardada" if smtp_cfg.get("password_dpapi") else "",
            hint_style=ft.TextStyle(color=MUTED),
        )
        msg = ft.Text("", color=ERROR)
        email_on = ft.Checkbox(
            label="Enviar comprobantes por correo (opcional)",
            value=bol.email_enabled(smtp_cfg),
            label_style=ft.TextStyle(color=TEXT),
        )
        email_box = ft.Column(
            [
                ft.Text(
                    "Gmail: smtp.gmail.com, STARTTLS 587 y una contraseña de aplicación. "
                    "La contraseña se guarda cifrada con la protección de Windows.",
                    color=MUTED, size=12,
                ),
                ft.Row([smtp_host, smtp_port]),
                smtp_sec, smtp_user, smtp_pass,
            ],
            tight=True,
        )

        def sync_visibility(e=None):
            net_row.visible = mode.value == "escpos_red"
            printer.visible = mode.value != "escpos_red"
            email_box.visible = bool(email_on.value)
            page.update()

        mode.on_select = sync_visibility
        email_on.on_change = sync_visibility

        def collect():
            try:
                port_n = int(parse_price(port.value) or 9100)
                smtp_port_n = int(parse_price(smtp_port.value) or 587)
            except ValueError:
                port_n, smtp_port_n = 9100, 587
            new_boleta = {
                "print_mode": mode.value or "windows",
                "printer": printer.value or "",
                "host": (host.value or "").strip(),
                "port": port_n,
                "paper_mm": int(paper.value or 80),
            }
            new_smtp = {
                "enabled": bool(email_on.value),
                "host": (smtp_host.value or "").strip(),
                "port": smtp_port_n,
                "security": smtp_sec.value or "starttls",
                "user": (smtp_user.value or "").strip(),
                "sender": (smtp_user.value or "").strip(),
                "password_dpapi": smtp_cfg.get("password_dpapi") or "",
            }
            if smtp_pass.value:
                new_smtp["password_dpapi"] = bol.protect_password(smtp_pass.value)
            return new_boleta, new_smtp

        def save(e):
            new_boleta, new_smtp = collect()
            bol.save_settings(boleta=new_boleta, smtp=new_smtp)
            close_dialog(dlg)
            show_message("Configuración guardada.")

        async def test_print(e):
            new_boleta, _ = collect()
            data = {
                "business_name": (core_config.load_config().get("business_name") or "Mi POS"),
                "rut": "", "address": "", "phone": "",
                "sale_id": "PRUEBA", "created_at": "",
                "items": [{"name": "Prueba de impresión", "qty": 1, "unit_price": 0, "line_total": 0}],
                "total": 0, "pay_method": "efectivo", "pay_label": "Efectivo",
                "received": None, "change": None,
            }
            msg.color = MUTED
            msg.value = "Imprimiendo prueba…"
            page.update()
            try:
                await asyncio.to_thread(bol.print_receipt, data, new_boleta)
            except Exception as exc:
                msg.color = ERROR
                msg.value = f"No se pudo imprimir: {exc}"
                page.update()
                return
            msg.color = PRIMARY
            msg.value = "Prueba enviada a la impresora."
            page.update()

        no_printers = ft.Text(
            "Windows no muestra ninguna impresora. Conecta la impresora de boletas, "
            "instala el programa (driver) que trae y vuelve a abrir esta ventana.",
            color=ERROR, size=12, visible=not printers,
        )
        dlg = ft.AlertDialog(
            title=ft.Text("Configuración", color=TEXT),
            bgcolor=WHITE,
            content=ft.Column(
                [
                    _caps("Impresora de boletas"),
                    ft.Text(
                        "Es la impresora térmica de rollo (80 o 58 mm) de la caja. "
                        "Conéctala, instala el driver que trae y elígela en la lista: "
                        "suele llamarse POS-80, XP-80C, EPSON TM-T20 o similar. "
                        "Si no sabes cuál es, deja «Impresora de Windows» y usa "
                        "«Imprimir prueba».",
                        color=MUTED, size=12,
                    ),
                    mode, printer, no_printers, net_row, paper,
                    ft.Text(
                        "Imprime un comprobante interno de venta: no es boleta electrónica del SII.",
                        color=MUTED, size=12,
                    ),
                    ft.Divider(color=BORDER),
                    _caps("Correo (opcional)"),
                    email_on,
                    email_box,
                ],
                tight=True,
                width=400,
                scroll=ft.ScrollMode.AUTO,
                height=400,
            ),
        )
        # El estado (prueba de impresion) queda siempre a la vista, fuera
        # del area con scroll.
        dlg.content = ft.Column([dlg.content, msg], tight=True, width=400)
        dlg.actions = [
            ft.TextButton("Imprimir prueba", icon=ft.Icons.PRINT, on_click=test_print,
                          style=ft.ButtonStyle(color=PRIMARY)),
            ft.FilledButton("Guardar", on_click=save, style=_state_style(PRIMARY, WHITE, radius=10)),
            ft.TextButton("Cancelar", on_click=lambda e: close_dialog(dlg),
                          style=ft.ButtonStyle(color=PRIMARY)),
        ]
        net_row.visible = mode.value == "escpos_red"
        printer.visible = mode.value != "escpos_red"
        email_box.visible = bool(email_on.value)
        open_dialog(dlg)

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
                _caps("Total"),
                ft.Text(
                    fmt_money(total), color=TEXT, size=30, weight=ft.FontWeight.BOLD, font_family=MONO
                ),
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
                show_sale_done(
                    sale_id,
                    charge_summary(sale_id, method, received - total, sale_warnings),
                    received if method == "efectivo" else None,
                )

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

    # ---------- Layout (maqueta moderna) ----------
    # Pestanas arriba (POS / Productos), tickets abiertos en la columna
    # izquierda y el total en su propia tarjeta a la derecha.

    # Columna izquierda: tickets abiertos (solo se ve en el POS).
    tickets_box = ft.Container(
        width=220,
        bgcolor=WHITE,
        border=ft.Border.only(right=ft.BorderSide(width=1, color=BORDER)),
        padding=ft.Padding.only(left=12, right=12, top=16, bottom=12),
        content=ft.Column(
            [
                _caps("Tickets abiertos"),
                ticket_list,
                ft.FilledButton(
                    content=ft.Row(
                        [ft.Icon(ft.Icons.ADD, size=18), ft.Text("Nuevo ticket", weight=ft.FontWeight.BOLD)],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    on_click=new_ticket,
                    style=_state_style(PRIMARY, WHITE, radius=10),
                    height=44,
                ),
                ft.TextButton(
                    "Eliminar ticket",
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=lambda e: ask_delete_ticket(),
                    style=ft.ButtonStyle(color=ERROR, shape=ft.RoundedRectangleBorder(radius=10)),
                ),
            ],
            expand=True,
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    # Tarjeta de busqueda + grilla de productos.
    search_card = _card(
        ft.Column(
            [
                ft.Row([search_input]),
                grid_info,
                grid_empty,
                grid_box,
            ],
            spacing=10,
        )
    )

    # Tarjeta del ticket actual.
    ticket_card = _card(
        ft.Column(
            [
                ft.Row(
                    [
                        ticket_title,
                        ft.TextButton(
                            "Limpiar ticket",
                            on_click=lambda e: ask_clear_ticket(),
                            style=ft.ButtonStyle(
                                color=ERROR,
                                shape=ft.RoundedRectangleBorder(radius=10),
                                side=ft.BorderSide(width=1, color=BORDER),
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                stock_bar,
                ft.Column(
                    [
                        # Scroll horizontal: las acciones nunca quedan cortadas.
                        ft.Row([table], scroll=ft.ScrollMode.AUTO),
                        ticket_empty,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            spacing=8,
            expand=True,
        ),
        expand=True,
    )

    main_col = ft.Column([search_card, ticket_card], expand=True, spacing=14)

    # Tarjeta del total: lo unico que "grita" junto al boton Cobrar.
    cobrar_btn = ft.FilledButton(
        content=ft.Text("Cobrar", size=17, weight=ft.FontWeight.W_800),
        on_click=open_charge_dialog,
        style=_state_style(PRIMARY, WHITE, radius=12),
        height=56,
    )

    # Reabre el aviso de la ultima venta para imprimir o enviar el comprobante.
    last_receipt_btn = ft.TextButton(
        "Último comprobante",
        icon=ft.Icons.RECEIPT_LONG,
        visible=False,
        on_click=lambda e: show_sale_done(
            last_sale["sale_id"], last_sale["summary"], last_sale["received"]
        ),
        style=ft.ButtonStyle(color=PRIMARY, shape=ft.RoundedRectangleBorder(radius=10)),
    )

    def _sum_row(label, value):
        return ft.Row(
            [ft.Text(label, color=MUTED, size=13.5), value],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    summary_card = _card(
        ft.Column(
            [
                _caps("Total a cobrar"),
                total_lbl,
                _sum_row("Subtotal", subtotal_lbl),
                _sum_row("Ítems", items_lbl),
                ft.Container(height=8),
                cobrar_btn,
                ft.Text(
                    "El medio de pago se elige al cobrar: efectivo, tarjeta o transferencia.",
                    color=MUTED,
                    size=12,
                ),
                last_receipt_btn,
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        width=270,
    )
    right_col = ft.Column([summary_card], width=270)

    # Vista Productos dentro de una tarjeta con titulo, como la maqueta.
    productos_card = _card(
        ft.Column(
            [
                ft.Text("Productos", size=22, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text(
                    "Crea, edita y desactiva productos. El stock bajo se marca en rojo.",
                    color=MUTED,
                    size=13.5,
                ),
                productos_view,
            ],
            spacing=6,
            expand=True,
        ),
        expand=True,
    )

    # El area central cambia entre el POS y la vista Productos sin
    # reconstruir nada: el ticket actual y la busqueda se conservan.
    content_area = ft.Row(
        [main_col, right_col],
        expand=True,
        spacing=14,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    # Pestanas arriba: la activa en primario, la otra texto atenuado sin
    # fondo (un FilledButton transparente se veia gris, como deshabilitado).
    nav_pos_btn = ft.Container(border_radius=10, ink=True)
    nav_prod_btn = ft.Container(border_radius=10, ink=True)
    tabs = (
        (nav_pos_btn, "pos", "POS", ft.Icons.POINT_OF_SALE),
        (nav_prod_btn, "productos", "Productos", ft.Icons.INVENTORY_2),
    )

    def paint_tabs(active):
        for btn, name, label, icon in tabs:
            on = name == active
            fg = WHITE if on else MUTED
            btn.content = ft.Row(
                [
                    ft.Icon(icon, size=19, color=fg),
                    ft.Text(label, color=fg, weight=ft.FontWeight.BOLD, size=14),
                ],
                spacing=8,
                tight=True,
            )
            btn.bgcolor = PRIMARY if on else None
            btn.padding = ft.Padding.symmetric(horizontal=16, vertical=10)

    async def show_view(name):
        paint_tabs(name)
        if name == "productos":
            content_area.controls = [productos_card]
            tickets_box.visible = False
            productos_view.load_data()
            page.update()
            await productos_view.focus_search()
        else:
            content_area.controls = [main_col, right_col]
            tickets_box.visible = True
            refresh_grid()
            refresh_ui()
            await focus_search()
        page.update()

    async def show_pos(e):
        await show_view("pos")

    async def show_productos(e):
        await show_view("productos")

    nav_pos_btn.on_click = show_pos
    nav_prod_btn.on_click = show_productos
    paint_tabs("pos")

    initial = (business_name[:1] or "M").upper()
    brand = ft.Row(
        [
            ft.Container(
                ft.Text(initial, color=WHITE, weight=ft.FontWeight.W_800, size=15),
                width=36,
                height=36,
                bgcolor=PRIMARY,
                border_radius=9,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Column(
                [
                    ft.Text(business_name, size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text("Punto de venta", size=11.5, color=MUTED),
                ],
                spacing=0,
            ),
        ],
        spacing=10,
    )
    top_bar = ft.Container(
        bgcolor=WHITE,
        border=ft.Border.only(bottom=ft.BorderSide(width=1, color=BORDER)),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        content=ft.Row(
            [
                brand,
                ft.Container(width=24),
                nav_pos_btn,
                nav_prod_btn,
                ft.Container(expand=True),
                ft.TextButton(
                    "Configuración",
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    on_click=open_settings_dialog,
                    style=ft.ButtonStyle(color=MUTED, shape=ft.RoundedRectangleBorder(radius=10)),
                ),
            ],
            spacing=6,
        ),
    )

    page.add(
        ft.Column(
            [
                top_bar,
                ft.Row(
                    [tickets_box, ft.Container(content_area, padding=16, expand=True)],
                    expand=True,
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ],
            expand=True,
            spacing=0,
        )
    )

    ensure_ticket()
    refresh_grid()
    refresh_ui()
    productos_view.load_data()


if __name__ == "__main__":
    ft.run(main)
