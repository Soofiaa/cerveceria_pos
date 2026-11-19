"""Mi POS en Flet - Vista Configuracion (Fase 3).

Datos del negocio (nombre, RUT, direccion, telefono, logo_path como texto),
prefijo de ticket (Ticket/Mesa), selector de 6 temas e "Impresora y correo"
(lo que antes era el dialogo de Configuracion de la fase 2: impresora de
boletas y correo SMTP opcional, con la misma persistencia de flet_app.boletas).

- El tema se aplica de inmediato: se avisa a main.py con on_theme_change,
  que repinta la app sin reconstruir el ticket ni perder la busqueda.
- Guardar pide confirmacion y escribe config.json (core.config).

Flet 1.1.2: Dropdown usa on_select (no on_change).
"""

import flet as ft

from core import config as core_config
from flet_app import boletas as bol
from flet_app.theme import THEMES

THEME_LABELS = {
    "neutro": "Neutro",
    "cerveceria": "Cervecería",
    "oscuro": "Oscuro",
    "menta": "Menta",
    "grafito": "Grafito",
    "lila": "Lila",
}
PREFIXES = ("Ticket", "Mesa")


def _caps(text, colors):
    return ft.Text(text.upper(), size=11, weight=ft.FontWeight.W_800, color=colors["secondary"])


class ConfigView(ft.Column):
    def __init__(self, page, colors, on_theme_change, on_saved):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.colors = colors
        self._on_theme_change = on_theme_change
        self._on_saved = on_saved

        cfg = core_config.load_config()
        _cfg, boleta_cfg, smtp_cfg = bol.load_settings()
        self._smtp_cfg = smtp_cfg

        self.in_name = self._field("Nombre del negocio", cfg.get("business_name", ""))
        self.in_rut = self._field("RUT", cfg.get("rut", ""))
        self.in_address = self._field("Dirección", cfg.get("address", ""))
        self.in_phone = self._field("Teléfono", cfg.get("phone", ""))
        self.in_logo = self._field("Ruta del logo (texto, no se muestra)", cfg.get("logo_path", ""))

        prefix = cfg.get("ticket_prefix", "Ticket")
        self.dd_prefix = ft.Dropdown(
            label="Prefijo de ticket",
            # Sin tooltip el lector de pantalla ve un boton sin nombre.
            tooltip="Prefijo de ticket",
            value=prefix if prefix in PREFIXES else "Ticket",
            options=[ft.DropdownOption(key=p, text=p) for p in PREFIXES],
            width=240,
            color=colors["text"],
            on_select=self._on_prefix_select,
        )

        theme = cfg.get("theme", "lila")
        self.theme_active = theme if theme in THEMES else "lila"
        self.theme_row = ft.Row(wrap=True, spacing=8)
        self._paint_theme_buttons()

        # Impresora y correo (fusionado desde el antiguo dialogo).
        self.dd_mode = ft.Dropdown(
            label="Cómo imprimir",
            value=boleta_cfg.get("print_mode") or "windows",
            options=[ft.DropdownOption(key=k, text=v) for k, v in bol.PRINT_MODES.items()],
            width=380, on_select=self._sync_printer_visibility,
        )
        printers = bol.list_windows_printers()
        current = boleta_cfg.get("printer") or bol.default_windows_printer()
        self.dd_printer = ft.Dropdown(
            label="Impresora de Windows",
            value=current if current in printers else None,
            options=[ft.DropdownOption(key=p, text=p) for p in printers],
            width=380,
        )
        self.dd_paper = ft.Dropdown(
            label="Ancho de papel",
            value=str(boleta_cfg.get("paper_mm") or 80),
            options=[ft.DropdownOption(key="80", text="80 mm"), ft.DropdownOption(key="58", text="58 mm")],
            width=180,
        )
        self.in_host = self._field("IP de la térmica (red)", boleta_cfg.get("host") or "", width=240)
        self.in_port = self._field("Puerto", str(boleta_cfg.get("port") or 9100), width=120)
        self.net_row = ft.Row([self.in_host, self.in_port], visible=False)
        self.no_printers = ft.Text(
            "Windows no muestra ninguna impresora. Conecta la impresora de boletas.",
            color=colors["danger"], size=12, visible=not printers,
        )

        self.chk_email = ft.Checkbox(
            label="Enviar comprobantes por correo (opcional)",
            value=bol.email_enabled(smtp_cfg),
            on_change=self._sync_printer_visibility,
        )
        self.in_smtp_host = self._field("Servidor SMTP", smtp_cfg.get("host") or "", width=260)
        self.in_smtp_port = self._field("Puerto SMTP", str(smtp_cfg.get("port") or 587), width=100)
        self.dd_smtp_sec = ft.Dropdown(
            label="Seguridad",
            value=smtp_cfg.get("security") or "starttls",
            options=[ft.DropdownOption(key="starttls", text="STARTTLS (587)"),
                     ft.DropdownOption(key="ssl", text="SSL (465)")],
            width=380,
        )
        self.in_smtp_user = self._field("Usuario (correo de envío)", smtp_cfg.get("user") or "", width=380)
        self.in_smtp_pass = ft.TextField(
            label="Contraseña de aplicación", value="", width=380, password=True,
            can_reveal_password=True, color=colors["text"],
            hint_text="Guardada" if smtp_cfg.get("password_dpapi") else "",
        )
        self.email_box = ft.Column(
            [
                ft.Row([self.in_smtp_host, self.in_smtp_port]),
                self.dd_smtp_sec, self.in_smtp_user, self.in_smtp_pass,
            ],
            tight=True, visible=bool(self.chk_email.value),
        )
        self._sync_printer_visibility()

        self.msg = ft.Text("", color=colors["secondary"])
        self.btn_guardar = ft.FilledButton("Guardar", on_click=self._ask_save)

        self.controls = [
            ft.Text("Configuración", size=22, weight=ft.FontWeight.BOLD),
            _caps("Datos del negocio", colors),
            self.in_name,
            ft.Row([self.in_rut, self.in_phone], spacing=12),
            self.in_address,
            self.in_logo,
            ft.Divider(),
            _caps("Formato de ticket", colors),
            self.dd_prefix,
            ft.Text("Los tickets nuevos se llaman «Ticket N» o «Mesa N» con el número libre más bajo.",
                    size=12, color=colors["secondary"]),
            ft.Divider(),
            _caps("Tema visual", colors),
            self.theme_row,
            ft.Divider(),
            _caps("Impresora y correo", colors),
            ft.Text(
                "Impresora térmica de rollo (80 o 58 mm) de la caja. Si no sabes cuál es, "
                "deja «Impresora de Windows». El correo es opcional (Gmail: smtp.gmail.com, "
                "STARTTLS 587 y una contraseña de aplicación).",
                size=12, color=colors["secondary"],
            ),
            self.dd_mode, self.dd_printer, self.no_printers, self.net_row, self.dd_paper,
            self.chk_email, self.email_box,
            ft.Divider(),
            self.btn_guardar,
            self.msg,
        ]
        self.apply_colors(colors)

    def _field(self, label, value, width=400):
        return ft.TextField(label=label, value=value, width=width, color=self.colors["text"])

    # ---------- Tema: se aplica al instante ----------
    def _paint_theme_buttons(self):
        c = self.colors
        self.theme_row.controls = [
            ft.FilledButton(
                THEME_LABELS[name],
                on_click=lambda e, n=name: self._select_theme(n),
                style=ft.ButtonStyle(
                    bgcolor=c["primary"] if name == self.theme_active else c["surface"],
                    color=c["primary_text"] if name == self.theme_active else c["text"],
                ),
            )
            for name in THEMES
        ]

    def _select_theme(self, name):
        self.theme_active = name
        self._paint_theme_buttons()
        # El tema se guarda al elegirlo (el brief: se aplica y se guarda).
        cfg = dict(core_config.load_config())  # copia: load_config puede devolver DEFAULT_CONFIG
        cfg["theme"] = name
        core_config.save_config(cfg)
        self._page.update()
        self._on_theme_change(name)

    # ---------- Impresora / correo ----------
    def _sync_printer_visibility(self, e=None):
        self.net_row.visible = self.dd_mode.value == "escpos_red"
        self.dd_printer.visible = self.dd_mode.value != "escpos_red"
        self.email_box.visible = bool(self.chk_email.value)
        self._page.update()

    def _on_prefix_select(self, e):
        pass  # se guarda al pulsar Guardar

    # ---------- Guardar (con confirmacion) ----------
    def _ask_save(self, e=None):
        dlg = ft.AlertDialog(
            title=ft.Text("Guardar configuración", color=self.colors["text"]),
            content=ft.Text("¿Guardar los cambios?", color=self.colors["text"]),
            bgcolor=self.colors["surface"],
        )

        def yes(e2):
            dlg.open = False
            self._page.update()
            self._save()

        def no(e2):
            dlg.open = False
            self._page.update()

        dlg.actions = [
            ft.FilledButton("Guardar", on_click=yes, style=ft.ButtonStyle(bgcolor=self.colors["primary"], color=self.colors["primary_text"])),
            ft.TextButton("Cancelar", on_click=no, style=ft.ButtonStyle(color=self.colors["primary"])),
        ]
        self._open_message(dlg)

    def _save(self):
        cfg = dict(core_config.load_config())  # copia: no mutar DEFAULT_CONFIG
        cfg.update({
            "business_name": (self.in_name.value or "").strip() or "Mi POS",
            "rut": (self.in_rut.value or "").strip(),
            "address": (self.in_address.value or "").strip(),
            "phone": (self.in_phone.value or "").strip(),
            "logo_path": (self.in_logo.value or "").strip(),
            "ticket_prefix": self.dd_prefix.value or "Ticket",
            "theme": self.theme_active,
        })
        core_config.save_config(cfg)

        new_boleta = {
            "print_mode": self.dd_mode.value or "windows",
            "printer": self.dd_printer.value or "",
            "host": (self.in_host.value or "").strip(),
            "port": int(self.in_port.value or 9100) if (self.in_port.value or "").isdigit() else 9100,
            "paper_mm": int(self.dd_paper.value or 80),
        }
        new_smtp = {
            "enabled": bool(self.chk_email.value),
            "host": (self.in_smtp_host.value or "").strip(),
            "port": int(self.in_smtp_port.value or 587) if (self.in_smtp_port.value or "").isdigit() else 587,
            "security": self.dd_smtp_sec.value or "starttls",
            "user": (self.in_smtp_user.value or "").strip(),
            "sender": (self.in_smtp_user.value or "").strip(),
            "password_dpapi": self._smtp_cfg.get("password_dpapi") or "",
        }
        if self.in_smtp_pass.value:
            new_smtp["password_dpapi"] = bol.protect_password(self.in_smtp_pass.value)
        bol.save_settings(boleta=new_boleta, smtp=new_smtp)

        self._on_saved(cfg)
        self.msg.value = "Configuración guardada."
        self.msg.color = self.colors["primary"]
        self._page.update()

    # ---------- Estado al reconstruir la interfaz por cambio de tema ----------
    _FIELDS = ("in_name", "in_rut", "in_address", "in_phone", "in_logo", "in_host", "in_port",
               "in_smtp_host", "in_smtp_port", "in_smtp_user", "in_smtp_pass")
    _DROPS = ("dd_prefix", "dd_mode", "dd_printer", "dd_paper", "dd_smtp_sec")

    def snapshot(self):
        """Lo escrito (aun sin guardar), para no perderlo al cambiar de tema."""
        data = {n: getattr(self, n).value for n in self._FIELDS + self._DROPS}
        data["chk_email"] = self.chk_email.value
        return data

    def restore(self, data):
        if not data:
            return
        for n in self._FIELDS + self._DROPS:
            if n in data:
                getattr(self, n).value = data[n]
        self.chk_email.value = data.get("chk_email", self.chk_email.value)
        self._sync_printer_visibility()

    # ---------- Repintado al cambiar de tema ----------
    def apply_colors(self, colors):
        """Repinta los colores de la vista sin tocar los valores escritos."""
        self.colors = colors
        self._paint_theme_buttons()
        self.msg.color = colors["secondary"]
        for tf in (self.in_name, self.in_rut, self.in_address, self.in_phone, self.in_logo,
                   self.in_host, self.in_port, self.in_smtp_host, self.in_smtp_port,
                   self.in_smtp_user, self.in_smtp_pass):
            tf.color = colors["text"]
        self.no_printers.color = colors["danger"]
        self.btn_guardar.style = ft.ButtonStyle(bgcolor=colors["primary"], color=colors["primary_text"])

    # ---------- Avisos ----------
    def _open_message(self, dlg):
        async def on_dismiss(e):
            if dlg in self._page.overlay:
                self._page.overlay.remove(dlg)
            self._page.update()

        dlg.on_dismiss = on_dismiss
        self._page.overlay.append(dlg)
        dlg.open = True
        self._page.update()
