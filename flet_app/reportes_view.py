"""Mi POS en Flet - Vista Reportes (Fase 3).

Rango Desde/Hasta (campo de fecha + DatePicker), por defecto hoy. Muestra
Total vendido, N° de ventas y Ticket promedio (core.report_service.summary),
la tabla de ventas del rango (list_sales, mas nuevas primero) y los
productos mas vendidos (top_products). Exporta el rango a CSV.

Reglas:
- NO muestra ganancia ni margen: summary usa precio-costo cuando
  gain_per_unit es 0 y eso infla la ganancia (M1, otra fase).
- Flet 1.1.2: DatePicker se abre con page.show_dialog(dp) (no existe
  pick_date ni page.overlay para el). El FilePicker es un Service: va en
  la pagina, no en page.overlay; save_file es async.
- Los dialogos de aviso van en page.overlay y se quitan en on_dismiss.
"""

import csv
from datetime import date, datetime

import flet as ft

from core import config as core_config
from flet_app.api_client import ApiError, SinConexion
from flet_app.backend import LocalBackend
from flet_app.lista_compras_pdf import build_lista_compras_pdf


def _fmt_money(value):
    """Formato chileno: 1500 -> $1.500."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    sign = "-" if n < 0 else ""
    return sign + "$" + f"{abs(n):,}".replace(",", ".")


def _iso(d):
    return d.strftime("%Y-%m-%d")


def parse_range(desde_txt, hasta_txt):
    """Valida el rango. Devuelve (desde, hasta) como 'YYYY-MM-DD' o lanza ValueError.

    Vacio = hoy. El mensaje de ValueError ya es para la cajera (sin texto
    tecnico de Python): se muestra tal cual en pantalla.
    """
    hoy = _iso(date.today())

    def one(txt, nombre):
        raw = (txt or "").strip()
        if not raw:
            return hoy
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"La fecha «{nombre}» no es válida: «{raw}». "
                f"Escríbela como AAAA-MM-DD, por ejemplo {hoy}."
            ) from None

    d1, d2 = one(desde_txt, "Desde"), one(hasta_txt, "Hasta")
    if d1 > d2:
        raise ValueError(
            f"La fecha «Desde» ({d1}) es posterior a «Hasta» ({d2}). Revisa el rango."
        )
    return d1, d2


class ReportesView(ft.Column):
    """Vista Reportes: rango, tarjetas, tabla de ventas, top productos, CSV."""

    def __init__(self, page, colors, backend=None):
        super().__init__(expand=True, spacing=14)
        self._page = page
        self.colors = colors
        self.backend = backend or LocalBackend()
        self.picker = ft.FilePicker()

        today = _iso(date.today())
        self.in_desde = ft.TextField(
            label="Desde (AAAA-MM-DD)", value=today, width=200, color=colors["text"],
            on_submit=lambda e: self.load_data(),
        )
        self.in_hasta = ft.TextField(
            label="Hasta (AAAA-MM-DD)", value=today, width=200, color=colors["text"],
            on_submit=lambda e: self.load_data(),
        )
        self.dp_desde = ft.DatePicker(
            value=datetime.now(), on_change=self._on_dp_desde,
        )
        self.dp_hasta = ft.DatePicker(
            value=datetime.now(), on_change=self._on_dp_hasta,
        )

        self.txt_total = ft.Text("$0", size=24, weight=ft.FontWeight.BOLD)
        self.txt_count = ft.Text("0", size=24, weight=ft.FontWeight.BOLD)
        self.txt_avg = ft.Text("$0", size=24, weight=ft.FontWeight.BOLD)
        self.msg = ft.Text("", color=colors["secondary"])

        self.sales_table = ft.DataTable(
            column_spacing=18, horizontal_margin=8, heading_row_height=36,
            columns=[
                ft.DataColumn(ft.Text("Fecha / hora")),
                ft.DataColumn(ft.Text("N° venta")),
                ft.DataColumn(ft.Text("Total"), numeric=True),
            ],
        )
        self.top_table = ft.DataTable(
            column_spacing=18, horizontal_margin=8, heading_row_height=36,
            columns=[
                ft.DataColumn(ft.Text("Producto")),
                ft.DataColumn(ft.Text("Cantidad"), numeric=True),
                ft.DataColumn(ft.Text("Recaudado"), numeric=True),
            ],
        )

        self.btn_ver = ft.FilledButton("Ver", on_click=lambda e: self.load_data())
        self.btn_pdf = ft.TextButton("Exportar PDF...", on_click=self._export_pdf, style=ft.ButtonStyle(color=self.colors["primary"]))
        self.lista_compras_container = ft.Column(spacing=10, expand=True)

        self.cards = ft.Row(
            [
                self._card("Total vendido", self.txt_total),
                self._card("N° de ventas", self.txt_count),
                self._card("Ticket promedio", self.txt_avg),
            ],
            spacing=14,
        )
        self.controls = [
            ft.Row(
                [
                    self.in_desde,
                    ft.IconButton(ft.Icons.DATE_RANGE, tooltip="Elegir fecha desde",
                                  on_click=self._open_dp_desde),
                    self.in_hasta,
                    ft.IconButton(ft.Icons.DATE_RANGE, tooltip="Elegir fecha hasta",
                                  on_click=self._open_dp_hasta),
                    self.btn_ver,
                    ft.TextButton("Exportar CSV...", on_click=self._export_csv, style=ft.ButtonStyle(color=self.colors["primary"])),
                ],
                spacing=10,
            ),
            self.msg,
            self.cards,
            ft.Row(
                [
                    ft.Column([ft.Text("Ventas del rango", weight=ft.FontWeight.BOLD),
                               ft.Column([self.sales_table], scroll=ft.ScrollMode.AUTO, expand=True)],
                              expand=True),
                    ft.Column([ft.Text("Productos más vendidos", weight=ft.FontWeight.BOLD),
                               ft.Column([self.top_table], scroll=ft.ScrollMode.AUTO, expand=True)],
                              expand=True),
                ],
                spacing=20,
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            ft.Divider(),
            ft.Row([ft.Text("Lista de compras", size=20, weight=ft.FontWeight.BOLD), self.btn_pdf], spacing=10),
            ft.Column([self.lista_compras_container], scroll=ft.ScrollMode.AUTO, expand=True),
        ]
        self.apply_colors(colors)

    # ---------- Colores (se repintan al cambiar de tema) ----------
    def apply_colors(self, colors):
        self.colors = colors
        self.txt_total.color = colors["primary"]
        self.txt_count.color = colors["primary"]
        self.txt_avg.color = colors["primary"]
        self.msg.color = colors["secondary"]
        self.btn_ver.style = ft.ButtonStyle(bgcolor=colors["primary"], color=colors["primary_text"])
        for tf in (self.in_desde, self.in_hasta):
            tf.color = colors["text"]

    def _card(self, title, value):
        return ft.Container(
            content=ft.Column(
                [ft.Text(title.upper(), size=11, weight=ft.FontWeight.W_800, color=self.colors["secondary"]),
                 value],
                spacing=4,
            ),
            padding=16,
            border_radius=14,
            width=220,
            bgcolor=self.colors["surface"],
            border=ft.Border.all(1, self.colors["accent"]),
        )

    # ---------- DatePicker: se abre con page.show_dialog ----------
    def _open_dp_desde(self, e=None):
        self._page.show_dialog(self.dp_desde)

    def _open_dp_hasta(self, e=None):
        self._page.show_dialog(self.dp_hasta)

    def _on_dp_desde(self, e):
        if self.dp_desde.value:
            self.in_desde.value = _iso(self.dp_desde.value)
            self.load_data()

    def _on_dp_hasta(self, e):
        if self.dp_hasta.value:
            self.in_hasta.value = _iso(self.dp_hasta.value)
            self.load_data()

    # ---------- Datos ----------
    def _rango(self):
        return parse_range(self.in_desde.value, self.in_hasta.value)

    def load_data(self, e=None):
        try:
            d1, d2 = self._rango()
        except ValueError as exc:
            # Con un rango invalido no se deja el resultado anterior a la
            # vista: parecería el total de las fechas escritas.
            self.msg.value = str(exc)
            self.msg.color = self.colors["danger"]
            self.txt_total.value = self.txt_avg.value = "$0"
            self.txt_count.value = "0"
            self.sales_table.rows = []
            self.top_table.rows = []
            self._page.update()
            return
        self.msg.color = self.colors["secondary"]

        try:
            s = self.backend.report_summary(d1, d2)
            sales = self.backend.report_sales(d1, d2)
            top = self.backend.report_top_products(d1, d2)
        except (SinConexion, ApiError):
            self.msg.value = "Sin conexión con la Caja 1: no se pueden cargar los reportes."
            self.msg.color = self.colors["danger"]
            self.txt_total.value = self.txt_avg.value = "$0"
            self.txt_count.value = "0"
            self.sales_table.rows = []
            self.top_table.rows = []
            self._page.update()
            return

        self.txt_total.value = _fmt_money(s["total"])
        self.txt_count.value = str(s["tickets"])
        self.txt_avg.value = _fmt_money(s["avg_ticket"])
        self.msg.value = "" if sales else f"No hay ventas entre {d1} y {d2}."
        self.sales_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(v["created_at"])),
                ft.DataCell(ft.Text(str(v["id"]))),
                ft.DataCell(ft.Text(_fmt_money(v["total"]))),
            ])
            for v in sales
        ]
        self.top_table.rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(p["name"])),
                ft.DataCell(ft.Text(str(p["qty"]))),
                ft.DataCell(ft.Text(_fmt_money(p["revenue"]))),
            ])
            for p in top
        ]

        # Lista de compras
        self.lista_compras_container.controls = []
        if getattr(self.backend, "is_remote", False):
            self.lista_compras_container.controls = [ft.Text("La lista de compras se genera en la Caja 1.")]
            self.btn_pdf.visible = False
        else:
            self.btn_pdf.visible = True
            items = self.backend.shopping_list()
            if not items:
                self.lista_compras_container.controls = [ft.Text("Nada falta por ahora.")]
            else:
                for item in items:
                    agotado = item['agotado']
                    s = item['sugerido']
                    s_txt = f"Comprar {s}" if s is not None else "Comprar: a criterio"
                    card = ft.Container(
                        content=ft.Row(
                            [
                                ft.Column([
                                    ft.Text(item['name'], weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text(f"Quedan {item['stock']} · {s_txt}", size=13),
                                ], expand=True),
                                ft.Container(
                                    content=ft.Text("AGOTADO" if agotado else "QUEDA POCO", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=12),
                                    padding=5,
                                    bgcolor=self.colors["danger"] if agotado else "#b97d0a",
                                    border_radius=5
                                )
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                        ),
                        padding=10,
                        border=ft.Border.all(1, self.colors["accent"]),
                        border_radius=10
                    )
                    self.lista_compras_container.controls.append(card)

        self._page.update()

    # ---------- Exportar CSV (mismo patron que Productos) ----------
    async def _export_csv(self, e=None):
        try:
            d1, d2 = self._rango()
        except ValueError as exc:
            self._show_message(str(exc))
            return
        try:
            path = await self.picker.save_file(
                dialog_title="Exportar reporte de ventas",
                file_name=f"ventas_{d1}_a_{d2}.csv",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["csv"],
            )
        except Exception as exc:
            self._show_message(f"No se pudo abrir el diálogo para guardar: {exc}")
            return
        if not path:
            return
        self._save_csv_to(path, d1, d2)

    def _save_csv_to(self, path, d1, d2):
        try:
            sales = self.backend.report_sales(d1, d2)
        except (SinConexion, ApiError):
            self._show_message("Sin conexión con la Caja 1: no se puede exportar el reporte.")
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["Fecha/hora", "N° venta", "Total"])
                for v in sales:
                    w.writerow([v["created_at"], v["id"], v["total"]])
        except Exception as exc:
            self._show_message(f"No se pudo guardar el reporte: {exc}")
            return
        self._show_message(f"Reporte guardado en:\n{path}")

    # ---------- Exportar PDF (Lista de compras) ----------
    async def _export_pdf(self, e=None):
        try:
            path = await self.picker.save_file(
                dialog_title="Exportar lista de compras",
                file_name="lista-de-compras.pdf",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["pdf"],
            )
        except Exception as exc:
            self._show_message(f"No se pudo abrir el diálogo para guardar: {exc}")
            return
        if not path:
            return
        self._save_pdf_to(path)

    def _save_pdf_to(self, path):
        try:
            items = self.backend.shopping_list()
        except Exception as exc:
            self._show_message(f"No se pudo obtener la lista de compras: {exc}")
            return

        cfg = core_config.load_config()
        business_name = cfg.get("business_name", "")
        generado_el = datetime.now().strftime("%d-%m-%Y %H:%M")

        try:
            build_lista_compras_pdf(items, business_name, generado_el, path)
        except Exception as exc:
            self._show_message(f"No se pudo generar el PDF: {exc}")
            return
        self._show_message(f"Lista de compras guardada en:\n{path}")

    # ---------- Avisos (page.overlay, se quitan en on_dismiss) ----------
    def _show_message(self, text):
        dlg = ft.AlertDialog(
            title=ft.Text("Reportes", color=self.colors["text"]),
            content=ft.Text(text, color=self.colors["text"]),
            bgcolor=self.colors["surface"],
        )

        def close(e):
            dlg.open = False
            self._page.update()

        dlg.actions = [ft.TextButton("Aceptar", autofocus=True, on_click=close,
                                     style=ft.ButtonStyle(color=self.colors["primary"]))]

        async def on_dismiss(e):
            if dlg in self._page.overlay:
                self._page.overlay.remove(dlg)
            self._page.update()

        dlg.on_dismiss = on_dismiss
        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()
