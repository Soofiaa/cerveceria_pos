"""Mi POS en Flet - Boletas (comprobante interno de venta).

Genera el comprobante de una venta ya cobrada y lo:
- guarda como PDF (fpdf2), para adjuntarlo o archivarlo;
- imprime en una impresora de Windows (dibujo GDI con pywin32: sirve para
  cualquier impresora con driver, incluidas termicas y "Microsoft Print to
  PDF");
- imprime en una termica ESC/POS, por su cola de Windows (RAW) o por red
  (TCP, normalmente puerto 9100);
- envia por correo: SMTP con la cuenta configurada (PDF adjunto) o abriendo
  el programa de correo con un enlace mailto (sin adjunto: mailto no lo
  permite, va el detalle en el cuerpo).

IMPORTANTE: es un comprobante INTERNO, no una boleta electronica del SII.
El documento lo dice explicitamente para que no se confunda.

No modifica core/: lee la venta con db_manager.get_conn y sales_service.
pywin32 se importa solo cuando hace falta, asi los tests corren sin el.
"""

import base64
import math
import os
import re
import smtplib
import socket
import ssl
import textwrap
from email.message import EmailMessage
from urllib.parse import quote

from core import config as core_config
from core import db_manager
from core import sales_service as ss

PAY_LABELS = {
    "efectivo": "Efectivo",
    "credito": "Tarjeta de crédito",
    "debito": "Tarjeta de débito",
    "transferencia": "Transferencia",
}

DOC_TITLE = "COMPROBANTE DE VENTA"
DOC_DISCLAIMER = "Documento no válido como boleta tributaria"
THANKS = "¡Gracias por su compra!"

# Columnas de texto por ancho de papel (fuente monoespaciada estandar).
COLS_BY_PAPER = {58: 32, 80: 42}

# "windows" es lo recomendado: sirve para cualquier impresora de boletas
# con su driver instalado. Los modos ESC/POS hablan directo con la termica
# (mas rapido y con corte de papel) y son para quien sabe que la tiene asi.
PRINT_MODES = {
    "windows": "Impresora de Windows (recomendado)",
    "escpos_windows": "Térmica ESC/POS por USB (avanzado)",
    "escpos_red": "Térmica ESC/POS por red/IP (avanzado)",
}

DEFAULT_BOLETA_CFG = {
    "print_mode": "windows",
    "printer": "",
    "host": "",
    "port": 9100,
    "paper_mm": 80,
}

# El correo es opcional y viene apagado: solo se ofrece si se activa en
# Configuracion.
DEFAULT_SMTP_CFG = {
    "enabled": False,
    "host": "smtp.gmail.com",
    "port": 587,
    "security": "starttls",  # "starttls" o "ssl"
    "user": "",
    "sender": "",
    "password_dpapi": "",
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BoletaError(Exception):
    """Error con mensaje en espanol listo para mostrar a la cajera."""


# ---------- Formato ----------
def fmt_money(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    sign = "-" if n < 0 else ""
    return sign + "$" + f"{abs(n):,}".replace(",", ".")


def is_valid_email(address):
    return bool(EMAIL_RE.match((address or "").strip()))


# ---------- Configuracion ----------
def _load_config_copy():
    """Copia de la configuracion.

    core.config.load_config() devuelve el mismo dict DEFAULT_CONFIG cuando
    aun no existe config.json: modificarlo lo cambiaria para todo el
    programa. Por eso aqui siempre se trabaja sobre una copia.
    """
    return dict(core_config.load_config())


def load_settings():
    """(config completa, boleta, smtp) con valores por defecto aplicados."""
    cfg = _load_config_copy()
    boleta = {**DEFAULT_BOLETA_CFG, **(cfg.get("boleta") or {})}
    smtp = {**DEFAULT_SMTP_CFG, **(cfg.get("smtp") or {})}
    return cfg, boleta, smtp


def save_settings(boleta=None, smtp=None):
    cfg = _load_config_copy()
    if boleta is not None:
        cfg["boleta"] = {**DEFAULT_BOLETA_CFG, **boleta}
    if smtp is not None:
        cfg["smtp"] = {**DEFAULT_SMTP_CFG, **smtp}
    core_config.save_config(cfg)


def boletas_dir():
    path = os.path.join(core_config.USER_DATA_DIR, "boletas")
    os.makedirs(path, exist_ok=True)
    return path


# ---------- Contrasena SMTP (DPAPI de Windows) ----------
def protect_password(plain):
    """Cifra la contrasena con DPAPI (solo este usuario de Windows la lee)."""
    if not plain:
        return ""
    import win32crypt  # pywin32

    blob = win32crypt.CryptProtectData(plain.encode("utf-8"), "MiPOS SMTP", None, None, None, 0)
    return base64.b64encode(blob).decode("ascii")


def unprotect_password(stored):
    if not stored:
        return ""
    import win32crypt  # pywin32

    _desc, data = win32crypt.CryptUnprotectData(base64.b64decode(stored), None, None, None, 0)
    return data.decode("utf-8")


# ---------- Datos del comprobante ----------
def get_sale(sale_id):
    with db_manager.get_conn() as con:
        cur = con.cursor()
        cur.execute(
            "SELECT id, created_at, subtotal, total, pay_method, status FROM sales WHERE id=?",
            (int(sale_id),),
        )
        r = cur.fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "created_at": r[1],
        "subtotal": r[2],
        "total": r[3],
        "pay_method": r[4],
        "status": r[5],
    }


def build_receipt(sale_id, received=None, cfg=None):
    """Datos del comprobante de una venta cobrada.

    received: monto recibido en efectivo (no se guarda en la base; solo se
    conoce al cobrar). Si se pasa, el comprobante muestra recibido y vuelto.
    """
    sale = get_sale(sale_id)
    if sale is None:
        raise BoletaError(f"No existe la venta {sale_id}.")
    if cfg is None:
        cfg = _load_config_copy()
    items = ss.items_de_venta(sale_id)
    total = int(sale["total"] or 0)
    method = sale["pay_method"] or "efectivo"
    data = {
        # str(): un telefono escrito como numero en config.json no debe romper el comprobante.
        "business_name": str(cfg.get("business_name") or "Mi POS").strip() or "Mi POS",
        "rut": str(cfg.get("rut") or "").strip(),
        "address": str(cfg.get("address") or "").strip(),
        "phone": str(cfg.get("phone") or "").strip(),
        "sale_id": sale["id"],
        "created_at": sale["created_at"] or "",
        "items": [
            {
                "name": i["product_name"],
                "qty": int(i["qty"]),
                "unit_price": int(i["unit_price"]),
                "line_total": int(i["line_total"]),
            }
            for i in items
        ],
        "total": total,
        "pay_method": method,
        "pay_label": PAY_LABELS.get(method, method),
        "received": None,
        "change": None,
    }
    if method == "efectivo" and received is not None and int(received) >= total:
        data["received"] = int(received)
        data["change"] = int(received) - total
    return data


def receipt_blocks(data, cols=42):
    """Lineas del comprobante con estilo: (texto, estilo).

    Estilos: "center", "bold_center", "big_center", "left", "bold_left",
    "rule". Se usan igual para ESC/POS, impresora Windows, PDF y correo.
    """
    out = []

    def center(text, style="center"):
        for chunk in textwrap.wrap(text, cols) or [""]:
            out.append((chunk.center(cols).rstrip(), style))

    def pair(left, right, style="left"):
        space = cols - len(left) - len(right)
        if space < 1:
            out.append((left[:cols], style))
            out.append((right.rjust(cols), style))
        else:
            out.append((left + " " * space + right, style))

    rule = ("-" * cols, "rule")

    # Encabezado: solo las lineas con valor (nunca una linea en blanco ni
    # "RUT:" vacio). `or ""` cubre campos ausentes o null en config.json.
    def field(key):
        return str(data.get(key) or "").strip()

    center(field("business_name") or "Mi POS", "big_center")
    if field("rut"):
        center(f"RUT: {field('rut')}")
    if field("address"):
        center(field("address"))
    if field("phone"):
        center(f"Tel: {field('phone')}")
    out.append(rule)
    center(DOC_TITLE, "bold_center")
    center(DOC_DISCLAIMER)
    out.append(rule)
    pair(f"N° {data['sale_id']}", data["created_at"])
    out.append(rule)
    for it in data["items"]:
        for chunk in textwrap.wrap(it["name"], cols) or [""]:
            out.append((chunk, "left"))
        pair(f"  {it['qty']} x {fmt_money(it['unit_price'])}", fmt_money(it["line_total"]))
    out.append(rule)
    pair("TOTAL", fmt_money(data["total"]), "bold_left")
    pair("Medio de pago", data["pay_label"])
    if data["received"] is not None:
        pair("Recibido", fmt_money(data["received"]))
        pair("Vuelto", fmt_money(data["change"]))
    out.append(rule)
    center(THANKS)
    return out


def receipt_text(data, cols=42):
    return "\n".join(text for text, _style in receipt_blocks(data, cols))


# ---------- PDF ----------
def build_pdf(data, path=None, paper_mm=80):
    """Guarda el comprobante como PDF de ancho ticket y devuelve la ruta."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    cols = COLS_BY_PAPER.get(int(paper_mm), 42)
    blocks = receipt_blocks(data, cols)
    line_h = 4.2
    height = 14 + line_h * (len(blocks) + 2)
    pdf = FPDF(orientation="P", unit="mm", format=(float(paper_mm), max(height, 60.0)))
    pdf.set_auto_page_break(False)
    pdf.set_margins(3, 5, 3)
    pdf.add_page()
    pdf.set_title(f"Comprobante de venta {data['sale_id']}")
    # Courier: monoespaciada, asi las columnas quedan alineadas.
    width = float(paper_mm) - 6
    font_size = 7.6 if cols >= 42 else 7.2
    for text, style in blocks:
        bold = style in ("bold_center", "bold_left", "big_center")
        size = font_size + (2.4 if style == "big_center" else 0)
        pdf.set_font("Courier", "B" if bold else "", size)
        safe = text.encode("latin-1", "replace").decode("latin-1")
        # Courier es de ancho fijo: un nombre largo en letra grande se sale
        # del papel y queda cortado. Se achica la letra hasta que quepa.
        avail = width - 2 * pdf.c_margin
        text_w = pdf.get_string_width(safe)
        if text_w > avail:
            # Hacia abajo a 2 decimales: el PDF guarda el tamano con 2 decimales
            # y redondear al mas cercano lo dejaba 0,009 mm sobre el limite.
            pdf.set_font_size(math.floor(size * avail / text_w * 100) / 100)
        pdf.cell(width, line_h, safe, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if path is None:
        path = os.path.join(boletas_dir(), f"comprobante_{data['sale_id']}.pdf")
    pdf.output(path)
    return path


# ---------- ESC/POS ----------
ESC = b"\x1b"
GS = b"\x1d"


def escpos_bytes(data, cols=42):
    """Bytes ESC/POS del comprobante (pagina de codigos PC850 para tildes y ñ)."""
    buf = bytearray()
    buf += ESC + b"@"  # inicializar
    buf += ESC + b"t" + bytes([2])  # tabla PC850
    for text, style in receipt_blocks(data, cols):
        align = 1 if style.endswith("center") else 0
        buf += ESC + b"a" + bytes([align])
        buf += ESC + b"E" + bytes([1 if style.startswith("bold") or style == "big_center" else 0])
        buf += GS + b"!" + bytes([0x11 if style == "big_center" else 0x00])
        line = text.strip() if align == 1 else text
        if style == "big_center":
            # Doble ancho: caben la mitad de columnas.
            line = line[: max(1, cols // 2)]
        buf += line.encode("cp850", "replace") + b"\n"
    buf += GS + b"!" + bytes([0]) + ESC + b"E" + bytes([0]) + ESC + b"a" + bytes([0])
    buf += ESC + b"d" + bytes([4])  # avanzar 4 lineas
    buf += GS + b"V" + bytes([66, 0])  # corte parcial
    return bytes(buf)


def send_escpos_network(payload, host, port=9100, timeout=6):
    if not (host or "").strip():
        raise BoletaError("Falta la IP de la impresora térmica. Configúrala en Configuración.")
    try:
        with socket.create_connection((host.strip(), int(port)), timeout=timeout) as sock:
            sock.sendall(payload)
    except OSError as exc:
        raise BoletaError(
            f"No se pudo conectar con la impresora en {host}:{port}. "
            "Revisa que esté encendida y en la misma red."
        ) from exc


def send_raw_windows(payload, printer_name, job_name="Comprobante"):
    if not printer_name:
        raise BoletaError("Elige la impresora en Configuración.")
    import win32print  # pywin32

    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        raise BoletaError(f'No se encontró la impresora "{printer_name}".') from exc
    try:
        win32print.StartDocPrinter(handle, 1, (job_name, None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, payload)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


# ---------- Impresora de Windows (GDI) ----------
def list_windows_printers():
    """Nombres de impresoras instaladas en Windows (vacio si no hay pywin32)."""
    try:
        import win32print
    except ImportError:
        return []
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in win32print.EnumPrinters(flags)]


def default_windows_printer():
    try:
        import win32print

        return win32print.GetDefaultPrinter()
    except Exception:
        return ""


def print_windows_gdi(data, printer_name, cols=42):
    """Dibuja el comprobante en cualquier impresora de Windows."""
    import win32ui  # pywin32

    name = printer_name or default_windows_printer()
    if not name:
        raise BoletaError("No hay impresora elegida ni impresora predeterminada en Windows.")
    blocks = receipt_blocks(data, cols)
    dc = win32ui.CreateDC()
    try:
        dc.CreatePrinterDC(name)
    except Exception as exc:
        raise BoletaError(f'No se pudo abrir la impresora "{name}".') from exc
    try:
        horz = dc.GetDeviceCaps(8)  # HORZRES: ancho imprimible en px
        dpi_y = dc.GetDeviceCaps(90)  # LOGPIXELSY
        # Tamano de letra: el que hace caber `cols` columnas, maximo 10 pt.
        max_h = int(dpi_y * 10 / 72)
        fit_h = int(horz / (cols * 0.56))
        height = max(8, min(max_h, fit_h))
        regular = win32ui.CreateFont({"name": "Consolas", "height": -height, "weight": 400})
        bold = win32ui.CreateFont({"name": "Consolas", "height": -height, "weight": 700})
        dc.StartDoc(f"Comprobante {data['sale_id']}")
        dc.StartPage()
        y = int(height * 0.5)
        line_h = int(height * 1.25)
        for text, style in blocks:
            dc.SelectObject(bold if style.startswith("bold") or style == "big_center" else regular)
            dc.TextOut(0, y, text)
            y += line_h
        dc.EndPage()
        dc.EndDoc()
    finally:
        dc.DeleteDC()


def print_receipt(data, boleta_cfg):
    """Imprime segun el modo configurado. Lanza BoletaError con el motivo."""
    mode = boleta_cfg.get("print_mode") or "windows"
    cols = COLS_BY_PAPER.get(int(boleta_cfg.get("paper_mm") or 80), 42)
    if mode == "escpos_red":
        send_escpos_network(escpos_bytes(data, cols), boleta_cfg.get("host"), boleta_cfg.get("port") or 9100)
    elif mode == "escpos_windows":
        send_raw_windows(escpos_bytes(data, cols), boleta_cfg.get("printer"), f"Comprobante {data['sale_id']}")
    else:
        print_windows_gdi(data, boleta_cfg.get("printer"), cols)


# ---------- Correo ----------
def email_subject(data):
    return f"Comprobante de venta N° {data['sale_id']} - {data['business_name']}"


def email_body(data):
    return (
        "Hola,\n\nAdjuntamos el comprobante de tu compra.\n\n"
        + receipt_text(data, 42)
        + "\n\n"
        + DOC_DISCLAIMER
        + ".\n"
    )


def mailto_url(to, data):
    """Enlace mailto con asunto y detalle en el cuerpo (mailto no adjunta)."""
    body = email_body(data).replace("Adjuntamos el comprobante", "Este es el comprobante")
    return f"mailto:{quote((to or '').strip())}?subject={quote(email_subject(data))}&body={quote(body)}"


def email_enabled(smtp_cfg):
    """True si se activo "Enviar comprobantes por correo" en Configuracion."""
    return bool(smtp_cfg.get("enabled"))


def smtp_is_configured(smtp_cfg):
    return bool(smtp_cfg.get("host") and smtp_cfg.get("user") and smtp_cfg.get("password_dpapi"))


def send_email_smtp(smtp_cfg, to, data, pdf_path, password=None, smtp_factory=None):
    """Envia el comprobante con el PDF adjunto. Lanza BoletaError con el motivo.

    smtp_factory es para los tests (permite un servidor SMTP falso).
    """
    to = (to or "").strip()
    if not is_valid_email(to):
        raise BoletaError("Escribe un correo válido, por ejemplo cliente@correo.cl.")
    if not smtp_is_configured(smtp_cfg) and password is None:
        raise BoletaError("Falta configurar el correo de envío en Configuración.")
    if password is None:
        password = unprotect_password(smtp_cfg["password_dpapi"])
    sender = (smtp_cfg.get("sender") or smtp_cfg.get("user") or "").strip()

    msg = EmailMessage()
    msg["Subject"] = email_subject(data)
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(email_body(data))
    with open(pdf_path, "rb") as f:
        msg.add_attachment(
            f.read(), maintype="application", subtype="pdf", filename=os.path.basename(pdf_path)
        )

    host = smtp_cfg["host"]
    port = int(smtp_cfg.get("port") or 587)
    context = ssl.create_default_context()
    try:
        if smtp_factory is not None:
            server = smtp_factory(host, port)
        elif smtp_cfg.get("security") == "ssl":
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
        with server:
            if smtp_factory is None and smtp_cfg.get("security") != "ssl":
                server.starttls(context=context)
            server.login(smtp_cfg["user"], password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise BoletaError(
            "El servidor rechazó el usuario o la contraseña. En Gmail usa una "
            "contraseña de aplicación, no la contraseña normal."
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise BoletaError(f"No se pudo enviar el correo: {exc}") from exc
