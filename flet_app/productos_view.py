"""Mi POS en Flet - Vista Productos (Fase 2).

Lista, busqueda, crear/editar, quitar (borrar o desactivar) y reactivar
productos, y exportacion CSV. Reutiliza core/product_service y
core/product_backup_service sin modificarlos.

Reglas:
- Flet 1.1.2: no existen page.dialog ni page.snack_bar: los dialogos van
  en page.overlay y se quitan en on_dismiss. focus() es asincrono.
- ft.UserControl NO existe en Flet 1.1.2 (AttributeError al importar):
  la vista es subclase de ft.Column y construye sus controles en __init__.
- FilePicker es un Service: al construirlo se registra solo en la pagina.
  NO va en page.overlay (ahi el cliente lo trata como control visual y
  muestra "Unknown control: FilePicker"). save_file es async y devuelve
  la ruta elegida (o None si se cancela).
- "Producto comun" es especial: se muestra pero no se puede quitar ni
  desactivar.
"""

import base64
import flet as ft

import base64
from core import product_backup_service as pbs
from core import product_service as ps
from core import category_service as cs
from core.utils_format import fmt_money as _fmt_money
from flet_app import multicaja
from flet_app.config_view import _ip_local, _qr_svg, INVENTARIO_PUERTO

TEXT = "#1c2833"
PRIMARY = "#6c3483"
PRIMARY_TEXT = "#ffffff"
WHITE = "#ffffff"
MUTED = "#5d6d7e"
ERROR = "#a93226"
WARN_BG = "#fff4d6"
WARN_TEXT = "#6e4500"
SURFACE2 = "#efe3f1"
BORDER = "#e2d0e6"

COMMON_PRODUCT_NAME = "Producto común"


def _parse_money(txt):
    """'$10.500', '10.500', '10,500' -> 10500. Igual que Qt: solo digitos."""
    digits = "".join(ch for ch in (txt or "") if ch.isdigit())
    return int(digits) if digits else 0


def _parse_money_or_none(txt):
    """Entero del texto, o None si tiene letras (no es un monto valido)."""
    raw = (txt or "").strip()
    if not raw:
        return None
    cleaned = raw.replace("$", "").replace(".", "").replace(",", "").replace(" ", "")
    if not cleaned.isdigit():
        return None
    return int(cleaned)


def is_common_product(product):
    return (product.get("name") or "").strip().lower() == COMMON_PRODUCT_NAME.lower()


def _state_style(bg, fg, radius=10):
    """Boton con radio 10, como en la maqueta."""
    return ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=radius),
        bgcolor=bg,
        color=fg,
    )


class ProductosView(ft.Column):
    """Vista Productos: tabla, busqueda, crear/editar, quitar, reactivar."""

    def __init__(self, page, on_products_changed=None):
        super().__init__(expand=True, spacing=10)
        self._page = page
        self.on_products_changed = on_products_changed

        self.search = ft.TextField(
            hint_text="Buscar por nombre o código",
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
            on_submit=lambda e: self.load_data(),
            expand=True,
        )
        self.filter_category = ft.Dropdown(
            label="Categoría",
            width=160,
            options=[
                ft.DropdownOption(key="all", text="Todas"),
                ft.DropdownOption(key="", text="Sin categoría"),
            ],
            value="all",
            on_select=lambda e: self.load_data(),
        )
        # Switch no tiene label_style en Flet 1.1.2: la etiqueta va aparte
        # para que se lea (antes quedaba texto claro sobre fondo claro).
        self.chk_inactivos = ft.Switch(
            value=False,
            on_change=lambda e: self.load_data(),
        )
        self.count_lbl = ft.Text("", color=MUTED, size=12)
        self.empty_lbl = ft.Text(
            "No hay productos. Agrega uno con el botón de abajo.",
            color=MUTED,
            visible=False,
        )
        self.table = ft.DataTable(
            column_spacing=16,
            horizontal_margin=8,
            columns=[
                ft.DataColumn(ft.Text("Nombre", color=TEXT, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Código", color=TEXT, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Venta", color=TEXT, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Compra", color=TEXT, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Stock", color=TEXT, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Stock mín.", color=TEXT, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Estado", color=TEXT, weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Acciones", color=TEXT, weight=ft.FontWeight.BOLD)),
            ],
        )
        # FilePicker es un Service: al construirlo se registra solo en la
        # pagina. NO va en page.overlay: ahi el cliente lo trata como
        # control visual y muestra "Unknown control: FilePicker".
        self.picker = ft.FilePicker()

        self.controls = [
            ft.Row(
                [
                    self.search,
                    self.filter_category,
                    ft.FilledButton(
                        "Buscar",
                        on_click=lambda e: self.load_data(),
                        style=_state_style(PRIMARY, PRIMARY_TEXT),
                        height=44,
                    ),
                    ft.Row(
                        [self.chk_inactivos, ft.Text("Ver inactivos", color=TEXT, size=13.5)],
                        spacing=4,
                    ),
                ]
            ),
            ft.Row(
                [
                    ft.FilledButton(
                        "Agregar producto",
                        on_click=self._on_add,
                        style=_state_style(PRIMARY, PRIMARY_TEXT),
                    ),
                    ft.TextButton(
                        "Categorías",
                        on_click=self._open_categories_dialog,
                        style=ft.ButtonStyle(color=PRIMARY),
                    ),
                    ft.TextButton(
                        "Ver en el teléfono",
                        on_click=self._open_telefono_dialog,
                        style=ft.ButtonStyle(color=PRIMARY),
                    ),
                    ft.TextButton(
                        "Guardar lista...",
                        on_click=self._export_csv,
                        style=ft.ButtonStyle(color=PRIMARY),
                    ),
                ]
            ),
            self.count_lbl,
            self.empty_lbl,
            # Scroll horizontal (Acciones nunca queda cortada) y vertical; la
            # tabla queda arriba, no centrada con un hueco encima.
            ft.Column(
                [ft.Row([self.table], scroll=ft.ScrollMode.AUTO)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ]

    async def focus_search(self):
        try:
            await self.search.focus()
        except Exception:
            pass

    # ---------- Avisos y confirmaciones (page.overlay, como en main.py) ----------
    def _display_dialog(self, dlg):
        async def on_dismiss(e):
            if dlg in self._page.overlay:
                self._page.overlay.remove(dlg)
            self._page.update()

        dlg.on_dismiss = on_dismiss
        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    def _close_dialog(self, dlg):
        dlg.open = False
        self._page.update()

    def _show_message(self, text):
        dlg = ft.AlertDialog(
            title=ft.Text("Mi POS", color=TEXT),
            content=ft.Text(text, color=TEXT),
            bgcolor=WHITE,
            actions=[
                ft.TextButton(
                    "Aceptar",
                    autofocus=True,
                    on_click=lambda e: self._close_dialog(dlg),
                    style=ft.ButtonStyle(color=PRIMARY),
                )
            ],
        )
        self._display_dialog(dlg)

    def _ask_confirm(self, title, text, on_yes):
        dlg = ft.AlertDialog(
            title=ft.Text(title, color=TEXT),
            content=ft.Text(text, color=TEXT),
            bgcolor=WHITE,
        )

        def yes(e):
            self._close_dialog(dlg)
            on_yes()

        dlg.actions = [
            ft.TextButton("Sí", on_click=yes, style=ft.ButtonStyle(color=ERROR)),
            ft.TextButton(
                "No",
                autofocus=True,
                on_click=lambda e: self._close_dialog(dlg),
                style=ft.ButtonStyle(color=PRIMARY),
            ),
        ]
        self._display_dialog(dlg)

    def _notify_changed(self):
        if self.on_products_changed is not None:
            self.on_products_changed()

    # ---------- Lista ----------
    def _refresh_category_filters(self):
        cats = cs.list_categories()
        opts = [
            ft.DropdownOption(key="all", text="Todas"),
            ft.DropdownOption(key="", text="Sin categoría"),
        ]
        for c in cats:
            opts.append(ft.DropdownOption(key=str(c["id"]), text=c["name"]))
        curr_val = self.filter_category.value
        self.filter_category.options = opts
        if curr_val != "all" and curr_val != "" and not any(o.key == curr_val for o in opts):
            self.filter_category.value = "all"
        self._page.update()

    def load_data(self, e=None):
        self._refresh_category_filters()
        q = (self.search.value or "").strip()
        prods = ps.list_products(q, incluir_inactivos=self.chk_inactivos.value)
        
        cat_filter = self.filter_category.value
        if cat_filter not in (None, "all"):
            if cat_filter == "":
                prods = [p for p in prods if p["category_id"] is None]
            else:
                cat_id_int = int(cat_filter)
                prods = [p for p in prods if p["category_id"] == cat_id_int]

        rows = []
        for p in prods:
            pid = p["id"]
            stock = int(p["stock"] or 0)
            min_stock = int(p["min_stock"] or 0)
            low = stock <= min_stock
            estado = "Inactivo" if not p["is_active"] else ("Activo · Stock bajo" if low else "Activo")
            stock_text = ft.Text(
                str(stock),
                color=ERROR if low else TEXT,
                weight=ft.FontWeight.BOLD if low else None,
            )
            acciones = [
                ft.TextButton(
                    "Editar",
                    on_click=self._make_edit_handler(pid),
                    style=ft.ButtonStyle(color=PRIMARY),
                )
            ]
            if p["is_active"]:
                acciones.append(
                    ft.TextButton(
                        "Quitar",
                        tooltip="Producto especial, no se puede quitar"
                        if is_common_product(p)
                        else None,
                        disabled=is_common_product(p),
                        on_click=lambda e, pid=pid, name=p["name"]: self._confirm_delete(pid, name),
                        style=ft.ButtonStyle(color=ERROR),
                    )
                )
            else:
                acciones.append(
                    ft.TextButton(
                        "Reactivar",
                        on_click=lambda e, pid=pid, name=p["name"]: self._confirm_reactivar(pid, name),
                        style=ft.ButtonStyle(color=PRIMARY),
                    )
                )
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(p["name"], color=TEXT)),
                        ft.DataCell(ft.Text(p["barcode"] or "", color=TEXT)),
                        ft.DataCell(ft.Text(_fmt_money(p["sale_price"]), color=TEXT)),
                        ft.DataCell(ft.Text(_fmt_money(p["purchase_price"]), color=TEXT)),
                        ft.DataCell(stock_text),
                        ft.DataCell(ft.Text(str(min_stock), color=TEXT)),
                        ft.DataCell(ft.Text(estado, color=ERROR if low else TEXT)),
                        ft.DataCell(ft.Row(acciones, spacing=0)),
                    ]
                )
            )
        self.table.rows = rows
        self.count_lbl.value = f"Mostrando {len(prods)} producto(s)."
        self.empty_lbl.visible = not prods
        self._page.update()

    # ---------- Crear / editar ----------
    # Flet solo hace await de un handler si el handler mismo es async def.
    # Un lambda que llama a una funcion async solo crea la corrutina y la
    # descarta ("coroutine ... was never awaited"): por eso los botones
    # que abren el dialogo usan estos handlers async.
    async def _on_add(self, e=None):
        await self._open_dialog()

    def _make_edit_handler(self, product_id):
        async def handler(e=None):
            await self._open_dialog(product_id)

        return handler

    async def _open_dialog(self, product_id=None):
        is_edit = product_id is not None
        data = None
        if is_edit:
            data = ps.get_product(product_id)
            if data is None:
                self._show_message("No se pudo cargar el producto.")
                return

        def field(label, value="", keyboard_number=False):
            return ft.TextField(
                label=label,
                value=value,
                color=TEXT,
                label_style=ft.TextStyle(color=MUTED),
                bgcolor=WHITE,
                keyboard_type=ft.KeyboardType.NUMBER if keyboard_number else ft.KeyboardType.TEXT,
            )

        in_name = field("Nombre*", data.get("name", "") if data else "")
        in_sale = field(
            "Precio venta*",
            str(data.get("sale_price", "")) if data else "",
            keyboard_number=True,
        )
        in_purchase = field(
            "Precio compra",
            str(data.get("purchase_price", "")) if data else "",
            keyboard_number=True,
        )
        in_barcode = field("Código de barras", data.get("barcode", "") if data else "")
        in_stock = field(
            "Stock actual", str(data.get("stock", "")) if data else "", keyboard_number=True
        )
        in_min_stock = field(
            "Stock mínimo",
            str(data.get("min_stock", "")) if data else "",
            keyboard_number=True,
        )
        
        cats = cs.list_categories()
        cat_options = [ft.DropdownOption(key="", text="Sin categoría")]
        for c in cats:
            cat_options.append(ft.DropdownOption(key=str(c["id"]), text=c["name"]))
        
        default_cat = str(data.get("category_id") or "") if data else ""
        in_category = ft.Dropdown(
            label="Categoría",
            options=cat_options,
            value=default_cat,
            color=TEXT,
            bgcolor=WHITE,
            expand=True,
        )

        async def _on_new_category(e=None):
            in_cat_name = ft.TextField(label="Nombre de categoría", color=TEXT, bgcolor=WHITE)
            err_cat = ft.Text("", color=ERROR)
            dlg_cat = ft.AlertDialog(
                title=ft.Text("Nueva categoría", color=TEXT),
                content=ft.Column([in_cat_name, err_cat], tight=True, width=300),
                bgcolor=WHITE,
            )
            def save_cat(ev):
                cname = (in_cat_name.value or "").strip()
                try:
                    new_id = cs.create_category(cname)
                except ValueError as exc:
                    err_cat.value = str(exc)
                    self._page.update()
                    return
                self._close_dialog(dlg_cat)
                updated_cats = cs.list_categories()
                new_opts = [ft.DropdownOption(key="", text="Sin categoría")]
                for c in updated_cats:
                    new_opts.append(ft.DropdownOption(key=str(c["id"]), text=c["name"]))
                in_category.options = new_opts
                in_category.value = str(new_id)
                self._refresh_category_filters()
                self._page.update()

            dlg_cat.actions = [
                ft.FilledButton("Guardar", on_click=save_cat, style=_state_style(PRIMARY, PRIMARY_TEXT)),
                ft.TextButton("Cancelar", on_click=lambda ev: self._close_dialog(dlg_cat), style=ft.ButtonStyle(color=PRIMARY)),
            ]
            self._display_dialog(dlg_cat)

        btn_new_cat = ft.TextButton("Nueva", on_click=_on_new_category, style=ft.ButtonStyle(color=PRIMARY))
        
        error_lbl = ft.Text("", color=ERROR)

        dlg = ft.AlertDialog(
            title=ft.Text(
                "Editar producto" if is_edit else "Nuevo producto", color=TEXT
            ),
            content=ft.Column(
                [in_name, in_sale, in_purchase, in_barcode, in_stock, in_min_stock, 
                 ft.Row([in_category, btn_new_cat], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                 error_lbl],
                tight=True,
                width=380,
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=WHITE,
        )

        def save(e):
            name = (in_name.value or "").strip()
            if not name:
                error_lbl.value = "El nombre es obligatorio."
                self._page.update()
                return
            sale = _parse_money_or_none(in_sale.value)
            if sale is None:
                error_lbl.value = "El precio de venta es obligatorio (solo números, $ y puntos)."
                self._page.update()
                return
            purchase = _parse_money_or_none(in_purchase.value)
            stock = _parse_money_or_none(in_stock.value)
            min_stock = _parse_money_or_none(in_min_stock.value)
            if purchase is None:
                purchase = 0
            if stock is None:
                stock = 0
            if min_stock is None:
                min_stock = 0
            barcode = (in_barcode.value or "").strip() or None
            
            cat_val = in_category.value
            category_id = int(cat_val) if cat_val else None

            try:
                if is_edit:
                    ps.update_product(
                        product_id,
                        name=name,
                        sale_price=sale,
                        purchase_price=purchase,
                        barcode=barcode,
                        stock=stock,
                        min_stock=min_stock,
                        category_id=category_id,
                    )
                else:
                    ps.create_product(
                        name,
                        sale,
                        purchase_price=purchase,
                        barcode=barcode,
                        stock=stock,
                        min_stock=min_stock,
                        category_id=category_id,
                    )
            except ValueError as exc:
                error_lbl.value = str(exc)
                self._page.update()
                return
            self._close_dialog(dlg)
            self.load_data()
            self._notify_changed()
            self._show_message(
                "Producto actualizado." if is_edit else "Producto creado."
            )

        dlg.actions = [
            ft.FilledButton(
                "Guardar", on_click=save, style=_state_style(PRIMARY, PRIMARY_TEXT)
            ),
            ft.TextButton(
                "Cancelar",
                on_click=lambda e: self._close_dialog(dlg),
                style=ft.ButtonStyle(color=PRIMARY),
            ),
        ]
        self._display_dialog(dlg)
        try:
            await in_name.focus()
        except Exception:
            pass

    # ---------- Quitar / desactivar / reactivar ----------
    # Son sincronas a proposito (no esperan nada): se llaman desde lambdas
    # de botones y desde do_delete, y asi siempre se ejecutan.
    def _confirm_delete(self, product_id, name):
        if name.strip().lower() == COMMON_PRODUCT_NAME.lower():
            self._show_message(
                "Producto común es un producto especial y no se puede quitar."
            )
            return

        def do_delete():
            try:
                ps.delete_product(product_id)
            except ValueError as exc:
                self._offer_deactivate(product_id, str(exc))
                return
            self.load_data()
            self._notify_changed()
            self._show_message("Producto eliminado.")

        self._ask_confirm("Quitar producto", f'¿Quitar "{name}"?', do_delete)

    def _offer_deactivate(self, product_id, reason):
        dlg = ft.AlertDialog(
            title=ft.Text("Quitar producto", color=TEXT),
            content=ft.Text(
                f"{reason}\n\n¿Deseas desactivarlo? Ya no aparecerá en las ventas, "
                "pero se podrá reactivar después.",
                color=TEXT,
            ),
            bgcolor=WHITE,
        )

        def do_deactivate(e):
            try:
                ps.desactivar_producto(product_id)
            except ValueError as exc:
                self._close_dialog(dlg)
                self._show_message(str(exc))
                return
            self._close_dialog(dlg)
            self.load_data()
            self._notify_changed()
            self._show_message("Producto desactivado.")

        dlg.actions = [
            ft.TextButton("Sí, desactivar", on_click=do_deactivate, style=ft.ButtonStyle(color=ERROR)),
            ft.TextButton(
                "No",
                autofocus=True,
                on_click=lambda e: self._close_dialog(dlg),
                style=ft.ButtonStyle(color=PRIMARY),
            ),
        ]
        self._display_dialog(dlg)

    def _confirm_reactivar(self, product_id, name):
        def do_reactivate():
            ps.reactivar_producto(product_id)
            self.load_data()
            self._notify_changed()
            self._show_message("Producto reactivado.")

        self._ask_confirm(
            "Reactivar producto", f'¿Reactivar "{name}"?', do_reactivate
        )

    # ---------- Exportar CSV ----------
    async def _export_csv(self, e=None):
        try:
            path = await self.picker.save_file(
                dialog_title="Guardar lista de productos",
                file_name="productos.csv",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["csv"],
            )
        except Exception as exc:
            self._show_message(f"No se pudo abrir el diálogo para guardar: {exc}")
            return
        if not path:
            return
        self._save_csv_to(path)

    def _save_csv_to(self, path):
        try:
            pbs.export_products_csv(path)
        except Exception as exc:
            self._show_message(f"No se pudo guardar la lista: {exc}")
            return
        self._show_message(f"Lista guardada en:\n{path}")

    # ---------- Telefono (QR) ----------
    def _open_telefono_dialog(self, e=None):
        inv_key = multicaja.ensure_inventory_key()
        ip = _ip_local()
        url = f"http://{ip}:{INVENTARIO_PUERTO}/inventario?clave={inv_key}"
        
        try:
            qr_src = "data:image/svg+xml;base64," + base64.b64encode(_qr_svg(url).encode("utf-8")).decode("ascii")
        except Exception:
            qr_src = ""

        qr_image = ft.Image(src=qr_src, width=220, height=220)
        url_field = ft.TextField(value=url, read_only=True, width=380, color=TEXT)
        tip_text = ft.Text("En el teléfono, agrega la página a la pantalla de inicio para abrirla después con un toque.", size=13, color=TEXT)

        dlg = ft.AlertDialog(
            title=ft.Text("Inventario en el teléfono", color=TEXT),
            content=ft.Column([qr_image, url_field, tip_text], tight=True, spacing=10),
            bgcolor=WHITE,
        )

        def close(e2):
            dlg.open = False
            self._page.update()

        dlg.actions = [ft.TextButton("Aceptar", autofocus=True, on_click=close,
                                     style=ft.ButtonStyle(color=PRIMARY))]

        async def on_dismiss(e2):
            if dlg in self._page.overlay:
                self._page.overlay.remove(dlg)
            self._page.update()

        dlg.on_dismiss = on_dismiss
        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()

    # ---------- Categorías ----------
    def _open_categories_dialog(self, e=None):
        cats = cs.list_categories()
        rows = [
            ft.Row([
                ft.Text(f"{c['name']} ({c['product_count']})", color=TEXT, expand=True),
                ft.TextButton("Renombrar", style=ft.ButtonStyle(color=PRIMARY),
                              on_click=lambda ev, cid=c['id'], cname=c['name']: self._open_rename_category_dialog(dlg, cid, cname)),
                ft.TextButton("Eliminar", style=ft.ButtonStyle(color=ERROR),
                              on_click=lambda ev, cid=c['id'], cname=c['name']: self._confirm_delete_category(dlg, cid, cname)),
            ])
            for c in cats
        ]
        if not rows:
            rows = [ft.Text("No hay categorías todavía.", color=MUTED)]
        dlg = ft.AlertDialog(
            title=ft.Text("Categorías", color=TEXT),
            content=ft.Column(rows, tight=True, width=420, scroll=ft.ScrollMode.AUTO),
            bgcolor=WHITE,
        )

        def close(ev):
            self._close_dialog(dlg)
            self.load_data()  # filtro y selectores reflejan los cambios

        dlg.actions = [ft.TextButton("Cerrar", autofocus=True, on_click=close, style=ft.ButtonStyle(color=PRIMARY))]
        self._display_dialog(dlg)

    def _open_rename_category_dialog(self, list_dlg, category_id, current_name):
        in_name = ft.TextField(label="Nombre", value=current_name, color=TEXT, bgcolor=WHITE)
        err_cat = ft.Text("", color=ERROR)
        dlg = ft.AlertDialog(title=ft.Text("Renombrar categoría", color=TEXT),
                             content=ft.Column([in_name, err_cat], tight=True, width=300), bgcolor=WHITE)

        def save(e):
            try:
                cs.rename_category(category_id, in_name.value)
            except ValueError as exc:
                err_cat.value = str(exc)
                self._page.update()
                return
            self._close_dialog(dlg)
            self._close_dialog(list_dlg)
            self._open_categories_dialog()  # lista con el nombre nuevo

        dlg.actions = [
            ft.FilledButton("Guardar", on_click=save, style=_state_style(PRIMARY, PRIMARY_TEXT)),
            ft.TextButton("Cancelar", on_click=lambda e: self._close_dialog(dlg), style=ft.ButtonStyle(color=PRIMARY)),
        ]
        self._display_dialog(dlg)

    def _confirm_delete_category(self, list_dlg, category_id, name):
        def do_delete():
            cs.delete_category(category_id)
            self._close_dialog(list_dlg)
            self._open_categories_dialog()

        self._ask_confirm("Eliminar categoría",
                          f'¿Eliminar "{name}"? Sus productos quedarán sin categoría (no se borra ningún producto).',
                          do_delete)

