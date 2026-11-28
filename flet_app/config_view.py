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

import base64
import socket

import flet as ft

from core import config as core_config
from flet_app import boletas as bol
from flet_app import multicaja
from flet_app.api_client import ApiError, SinConexion
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
MODE_LABELS = {
    "standalone": "Una sola caja (sin red)",
    "server": "Caja 1 (principal, comparte su base)",
    "client": "Caja adicional (se conecta a la Caja 1)",
}

INVENTARIO_PUERTO = 8780


def _ip_local():
    """IP local de esta maquina sin enviar trafico (truco del socket UDP)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _qr_svg(texto):
    """Codigo QR en SVG (texto). Requiere qrcode>=7."""
    import qrcode
    import qrcode.image.svg
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(texto, image_factory=factory, box_size=10, border=4)
    return img.to_string(encoding="unicode")


def _caps(text, colors):
    return ft.Text(text.upper(), size=11, weight=ft.FontWeight.W_800, color=colors["secondary"])


class ConfigView(ft.Column):
    def __init__(self, page, colors, on_theme_change, on_saved, backend=None):
        super().__init__(expand=True, spacing=12, scroll=ft.ScrollMode.AUTO)
        self._page = page
        self.colors = colors
        self._on_theme_change = on_theme_change
        self._on_saved = on_saved
        self.backend = backend
        self.is_remote = getattr(backend, "is_remote", False)

        cfg = core_config.load_config()
        _cfg, boleta_cfg, smtp_cfg = bol.load_settings()
        self._smtp_cfg = smtp_cfg
        server_cfg = {}
        business_note = ""
        if self.is_remote:
            try:
                server_cfg = self.backend.config()
                business_note = "Los datos del negocio se editan en la Caja 1."
            except (SinConexion, ApiError):
                business_note = "Sin conexión con la Caja 1."

        if self.is_remote:
            # Datos del negocio de la Caja 1 (vacios si no responde). El logo no
            # viaja por la API: se muestra vacio en vez de el logo local.
            cfg = dict(cfg, business_name=server_cfg.get("business_name", ""),
                       rut=server_cfg.get("rut", ""), address=server_cfg.get("address", ""),
                       phone=server_cfg.get("phone", ""), logo_path="")

        self.in_name = self._field("Nombre del negocio", cfg.get("business_name", ""), disabled=self.is_remote)
        self.in_rut = self._field("RUT", cfg.get("rut", ""), disabled=self.is_remote)
        self.in_address = self._field("Dirección", cfg.get("address", ""), disabled=self.is_remote)
        self.in_phone = self._field("Teléfono", cfg.get("phone", ""), disabled=self.is_remote)
        self.in_logo = self._field("Ruta del logo (texto, no se muestra)", cfg.get("logo_path", ""), disabled=self.is_remote)
        self.business_note = ft.Text(business_note, size=12, color=colors["secondary"], visible=self.is_remote)

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

        # Modo de la caja (Fase 5.1). Se aplica al reiniciar la app.
        caja = multicaja.get_caja_settings(cfg)
        self.dd_caja_mode = ft.Dropdown(
            label="Modo de esta caja",
            tooltip="Modo de esta caja",
            value=caja["mode"],
            options=[ft.DropdownOption(key=k, text=v) for k, v in MODE_LABELS.items()],
            width=400, on_select=self._sync_caja_visibility,
        )
        self.in_caja_name = self._field("Nombre de esta caja", cfg.get("caja_name") or "")
        self.in_caja_number = self._field("Número de caja", str(caja["caja_number"]), width=140)
        self.in_server_url = self._field("Dirección de la Caja 1", cfg.get("server_url") or "")
        # Caja adicional: pega aqui la clave que muestra la Caja 1.
        self.in_api_token = ft.TextField(
            label="Clave de la Caja 1", value=cfg.get("api_token") or "", width=400,
            password=True, can_reveal_password=True, color=self.colors["text"],
        )
        self.caja_server_box = ft.Column([self.in_server_url, self.in_api_token], tight=True)
        # Caja 1: muestra la clave enmascarada; el boton copia la completa.
        self._token_completo = str(cfg.get("api_token") or "")
        self.txt_token = ft.TextField(
            label="Clave de esta Caja 1 (cópiala en las cajas adicionales)",
            value=self._mascarar_token(self._token_completo),
            read_only=True, width=340, color=colors["text"],
            hint_text="Se genera al iniciar la Caja 1",
        )
        self.clipboard = ft.Clipboard()  # servicio: se registra solo en la pagina
        self.btn_copy_token = ft.IconButton(
            ft.Icons.CONTENT_COPY, tooltip="Copiar la clave", on_click=self._copy_token,
        )
        self.caja_token_box = ft.Column(
            [ft.Row([self.txt_token, self.btn_copy_token], spacing=4),
             ft.Text("Sin esta clave, las cajas adicionales no pueden conectarse a la Caja 1.",
                     size=12, color=colors["secondary"])],
            tight=True,
        )

        # ---------- Inventario en el telefono (solo modo servidor) ----------
        self._inventory_key_completo = str(multicaja.ensure_inventory_key() or "")
        self.txt_inv_key = ft.TextField(
            label="Clave de inventario del telefono",
            value=self._mascarar_token(self._inventory_key_completo),
            read_only=True, width=340, color=colors["text"],
            hint_text="Se genera al iniciar la Caja 1",
        )
        self.btn_copy_inv_key = ft.IconButton(
            ft.Icons.CONTENT_COPY, tooltip="Copiar la clave", on_click=self._copy_inv_key,
        )
        self.inv_url = ft.TextField(
            label="Enlace para el telefono (copialo o escanea el QR)",
            value="", read_only=True, width=520, color=colors["text"],
        )
        self.btn_regenerar_inv = ft.TextButton(
            "Regenerar clave",
            on_click=self._ask_regenerar_inv_key,
            style=ft.ButtonStyle(color=colors["danger"]),
        )
        self.qr_img = ft.Image(src="", width=220, height=220)
        self.inv_box = ft.Column(
            [
                ft.Row([self.txt_inv_key, self.btn_copy_inv_key], spacing=4),
                self.inv_url,
                ft.Row([self.btn_regenerar_inv, self.qr_img], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Text("Solo lectura: el telefono solo puede ver el inventario. "
                        "Al regenerar la clave, los telefonos con el enlace anterior dejan de funcionar.",
                        size=12, color=colors["secondary"]),
            ],
            tight=True,
            visible=self.dd_caja_mode.value == "server",
        )
        self._sync_caja_visibility()

        self.msg = ft.Text("", color=colors["secondary"])
        self.btn_guardar = ft.FilledButton("Guardar", on_click=self._ask_save)

        self.controls = [
            ft.Text("Configuración", size=22, weight=ft.FontWeight.BOLD),
            _caps("Datos del negocio", colors),
            self.business_note,
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
            _caps("Modo de la caja", colors),
            ft.Text("Cambiar el modo se aplica al reiniciar la app. Una caja adicional no usa base "
                    "propia: vende con los productos y el stock de la Caja 1.",
                    size=12, color=colors["secondary"]),
            self.dd_caja_mode,
            ft.Row([self.in_caja_name, self.in_caja_number], spacing=12),
            self.caja_server_box,
            self.caja_token_box,
            self.inv_box,
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

    def _field(self, label, value, width=400, disabled=False):
        return ft.TextField(label=label, value=value, width=width, color=self.colors["text"], disabled=disabled)

    @staticmethod
    def _mascarar_token(token):
        """Muestra la clave enmascarada: puntos y solo los ultimos 4 caracteres."""
        token = str(token or "")
        if len(token) <= 4:
            return "•" * len(token)
        return "•" * (len(token) - 4) + token[-4:]

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

    # ---------- Modo de la caja ----------
    def _sync_caja_visibility(self, e=None):
        # La direccion de la Caja 1 solo se pide en una caja adicional.
        self.caja_server_box.visible = self.dd_caja_mode.value == "client"
        # La clave generada solo se muestra en la Caja 1 (la que sirve la API).
        self.caja_token_box.visible = self.dd_caja_mode.value == "server"
        # El bloque de inventario solo se muestra en la Caja 1 (servidor).
        self.inv_box.visible = self.dd_caja_mode.value == "server"
        if e is not None:
            self._page.update()

    async def _copy_token(self, e=None):
        token = self._token_completo or ""
        if not token:
            self.msg.value = "Aún no hay clave: se genera al iniciar la Caja 1."
            self.msg.color = self.colors["danger"]
            self._page.update()
            return
        await self.clipboard.set(token)
        self.msg.value = "Clave copiada."
        self.msg.color = self.colors["primary"]
        self._page.update()

    async def _copy_inv_key(self, e=None):
        key = self._inventory_key_completo or ""
        if not key:
            self.msg.value = "Aún no hay clave de inventario: se genera al iniciar la Caja 1."
            self.msg.color = self.colors["danger"]
            self._page.update()
            return
        await self.clipboard.set(key)
        self.msg.value = "Clave de inventario copiada."
        self.msg.color = self.colors["primary"]
        self._page.update()

    async def _ask_regenerar_inv_key(self, e=None):
        dlg = ft.AlertDialog(
            title=ft.Text("Regenerar clave de inventario", color=self.colors["text"]),
            content=ft.Text("Los telefonos con el enlace anterior dejaran de funcionar. ¿Continuar?",
                            color=self.colors["text"]),
            bgcolor=self.colors["surface"],
        )

        def yes(e2):
            dlg.open = False
            self._page.update()
            self._regenerar_inv_key()

        def no(e2):
            dlg.open = False
            self._page.update()

        dlg.actions = [
            ft.FilledButton("Regenerar", on_click=yes,
                            style=ft.ButtonStyle(bgcolor=self.colors["danger"], color=self.colors["primary_text"])),
            ft.TextButton("Cancelar", on_click=no, style=ft.ButtonStyle(color=self.colors["primary"])),
        ]
        self._open_message(dlg)

    def _regenerar_inv_key(self):
        key = multicaja.ensure_inventory_key(regenerate=True)
        self._inventory_key_completo = str(key or "")
        self.txt_inv_key.value = self._mascarar_token(self._inventory_key_completo)
        self._armar_inv_url()
        self._page.update()
        self.msg.value = "Clave de inventario regenerada."
        self.msg.color = self.colors["primary"]
        self._page.update()

    def _armar_inv_url(self):
        clave = self._inventory_key_completo or ""
        ip = _ip_local()
        url = f"http://{ip}:{INVENTARIO_PUERTO}/inventario?clave={clave}"
        self.inv_url.value = url
        try:
            self.qr_img.src = "data:image/svg+xml;base64," + base64.b64encode(_qr_svg(url).encode("utf-8")).decode("ascii")
        except Exception:
            self.qr_img.src = ""

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
        mode = self.dd_caja_mode.value or multicaja.DEFAULT_MODE
        if mode == "client":
            error = multicaja.validate_client_url(self.in_server_url.value)
            if error:
                self.msg.value = error
                self.msg.color = self.colors["danger"]
                self._page.update()
                return
        cfg = dict(core_config.load_config())  # copia: no mutar DEFAULT_CONFIG
        cfg_data = {
            "mode": mode,
            "server_url": multicaja.normalize_url(self.in_server_url.value) if mode == "client" else (cfg.get("server_url") or ""),
            "caja_number": multicaja._caja_number({"caja_number": self.in_caja_number.value}),
            "caja_name": (self.in_caja_name.value or "").strip(),
            # Caja adicional: la que se pego. Caja 1 y standalone: la que ya hay (la
            # generada al arrancar); el campo de la caja adicional esta oculto y vacio.
            "api_token": (self.in_api_token.value or "").strip() if mode == "client"
            else str(cfg.get("api_token") or "").strip(),
            "ticket_prefix": self.dd_prefix.value or "Ticket",
            "theme": self.theme_active,
        }
        if not self.is_remote:
            cfg_data.update({
                "business_name": (self.in_name.value or "").strip() or "Mi POS",
                "rut": (self.in_rut.value or "").strip(),
                "address": (self.in_address.value or "").strip(),
                "phone": (self.in_phone.value or "").strip(),
                "logo_path": (self.in_logo.value or "").strip(),
            })
        cfg.update(cfg_data)
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
               "in_caja_name", "in_caja_number", "in_server_url", "in_api_token",
               "in_smtp_host", "in_smtp_port", "in_smtp_user", "in_smtp_pass")
    _DROPS = ("dd_prefix", "dd_mode", "dd_printer", "dd_paper", "dd_smtp_sec", "dd_caja_mode")

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
        self._sync_caja_visibility()
        self._armar_inv_url()

    # ---------- Repintado al cambiar de tema ----------
    def apply_colors(self, colors):
        """Repinta los colores de la vista sin tocar los valores escritos."""
        self.colors = colors
        self._paint_theme_buttons()
        self.msg.color = colors["secondary"]
        for tf in (self.in_name, self.in_rut, self.in_address, self.in_phone, self.in_logo,
                   self.in_host, self.in_port, self.in_smtp_host, self.in_smtp_port,
                   self.in_smtp_user, self.in_smtp_pass, self.in_caja_name, self.in_caja_number,
                   self.in_server_url, self.in_api_token, self.txt_token):
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
