"""Tests del comprobante interno de venta (flet_app/boletas.py).

Nada sale del equipo: el SMTP es un servidor falso y la termica de red es
un socket local. No se imprime en ninguna impresora real.
"""

import os
import re
import shutil
import socket
import smtplib
import threading
import zlib

import pytest

from core import config as core_config
from core import product_service as ps
from core import sales_service as ss
from core import ticket_service as ts
from flet_app import boletas as bol

CFG = {"business_name": "Cervecería Ñandú", "rut": "11.111.111-1", "address": "Calle 1", "phone": "123"}


def _venta(method="efectivo"):
    pid = ps.create_product(name="Cerveza Ñandú 500 ml", sale_price=1500, barcode="7801", stock=10)
    pid2 = ps.create_product(name="Papas", sale_price=1000, barcode="7802", stock=10)
    tid = ts.create_ticket("Ticket 1")
    ts.add_item(tid, pid, 2, 1500)
    ts.add_item(tid, pid2, 1, 1000)
    ts.set_pay_method(tid, method)
    sale_id, _ = ss.cobrar_ticket(tid)
    return sale_id


def test_build_receipt_con_vuelto(temp_db):
    sale_id = _venta()
    data = bol.build_receipt(sale_id, received=5000, cfg=CFG)
    assert data["total"] == 4000
    assert data["received"] == 5000 and data["change"] == 1000
    assert [i["name"] for i in data["items"]] == ["Cerveza Ñandú 500 ml", "Papas"]
    assert data["pay_label"] == "Efectivo"


def test_build_receipt_tarjeta_sin_vuelto(temp_db):
    sale_id = _venta("debito")
    data = bol.build_receipt(sale_id, received=5000, cfg=CFG)
    assert data["received"] is None and data["change"] is None
    assert data["pay_label"] == "Tarjeta de débito"


def test_build_receipt_venta_inexistente(temp_db):
    with pytest.raises(bol.BoletaError, match="No existe la venta"):
        bol.build_receipt(999, cfg=CFG)


@pytest.mark.parametrize("cols", [32, 42])
def test_receipt_text_contenido_y_ancho(temp_db, cols):
    data = bol.build_receipt(_venta(), received=5000, cfg=CFG)
    text = bol.receipt_text(data, cols)
    for expected in (
        "Cervecería Ñandú",
        "RUT: 11.111.111-1",
        bol.DOC_TITLE,
        "no válido como boleta",
        "2 x $1.500",
        "$3.000",
        "$4.000",
        "Recibido",
        "$5.000",
        "Vuelto",
        "$1.000",
    ):
        assert expected in text, expected
    assert all(len(line) <= cols for line in text.splitlines())


def test_escpos_bytes(temp_db):
    data = bol.build_receipt(_venta(), received=5000, cfg=CFG)
    payload = bol.escpos_bytes(data, 42)
    assert payload.startswith(b"\x1b@")  # inicializar
    assert b"\x1bt\x02" in payload  # tabla PC850
    assert payload.endswith(b"\x1dVB\x00")  # corte
    assert "Ñandú".encode("cp850") in payload  # tildes y ñ legibles en la termica


def test_build_pdf(temp_db, tmp_path):
    data = bol.build_receipt(_venta(), received=5000, cfg=CFG)
    path = bol.build_pdf(data, str(tmp_path / "c.pdf"), paper_mm=80)
    with open(path, "rb") as f:
        assert f.read(5) == b"%PDF-"
    path58 = bol.build_pdf(data, str(tmp_path / "c58.pdf"), paper_mm=58)
    with open(path58, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_mailto_url(temp_db):
    data = bol.build_receipt(_venta(), cfg=CFG)
    url = bol.mailto_url("cliente@correo.cl", data)
    assert url.startswith("mailto:cliente%40correo.cl?subject=")
    assert "Comprobante%20de%20venta" in url
    assert " " not in url


def test_is_valid_email():
    assert bol.is_valid_email("a@b.cl")
    assert not bol.is_valid_email("")
    assert not bol.is_valid_email("sin-arroba")
    assert not bol.is_valid_email("a@b")


class FakeSMTP:
    sent = []

    def __init__(self, host, port, fail_auth=False):
        self.host, self.port, self.fail_auth = host, port, fail_auth
        self.logged = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        if self.fail_auth:
            raise smtplib.SMTPAuthenticationError(535, b"bad")
        self.logged = (user, password)

    def send_message(self, msg):
        FakeSMTP.sent.append((self.logged, msg))


SMTP_CFG = {"host": "smtp.test", "port": 587, "security": "starttls", "user": "caja@negocio.cl",
            "sender": "caja@negocio.cl", "password_dpapi": ""}


def test_send_email_smtp_adjunta_pdf(temp_db, tmp_path):
    FakeSMTP.sent = []
    data = bol.build_receipt(_venta(), received=5000, cfg=CFG)
    pdf = bol.build_pdf(data, str(tmp_path / "c.pdf"))
    bol.send_email_smtp(SMTP_CFG, "cliente@correo.cl", data, pdf, password="secreta",
                        smtp_factory=lambda h, p: FakeSMTP(h, p))
    (logged, msg), = FakeSMTP.sent
    assert logged == ("caja@negocio.cl", "secreta")
    assert msg["To"] == "cliente@correo.cl"
    assert "Comprobante de venta" in msg["Subject"]
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == "application/pdf"
    assert attachments[0].get_content().startswith(b"%PDF-")


def test_send_email_smtp_errores(temp_db, tmp_path):
    data = bol.build_receipt(_venta(), cfg=CFG)
    pdf = bol.build_pdf(data, str(tmp_path / "c.pdf"))
    with pytest.raises(bol.BoletaError, match="correo válido"):
        bol.send_email_smtp(SMTP_CFG, "malo", data, pdf, password="x",
                            smtp_factory=lambda h, p: FakeSMTP(h, p))
    with pytest.raises(bol.BoletaError, match="contraseña de aplicación"):
        bol.send_email_smtp(SMTP_CFG, "c@c.cl", data, pdf, password="x",
                            smtp_factory=lambda h, p: FakeSMTP(h, p, fail_auth=True))
    with pytest.raises(bol.BoletaError, match="Falta configurar"):
        bol.send_email_smtp(SMTP_CFG, "c@c.cl", data, pdf)


def test_send_escpos_network_a_socket_local():
    received = bytearray()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def accept():
        conn, _ = server.accept()
        with conn:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                received.extend(chunk)

    t = threading.Thread(target=accept)
    t.start()
    bol.send_escpos_network(b"\x1b@hola", "127.0.0.1", port)
    t.join(timeout=5)
    server.close()
    assert bytes(received) == b"\x1b@hola"


def test_send_escpos_network_sin_ip():
    with pytest.raises(bol.BoletaError, match="Falta la IP"):
        bol.send_escpos_network(b"x", "", 9100)


def test_settings_guardar_y_cargar(tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    bol.save_settings(boleta={"print_mode": "escpos_red", "host": "192.168.1.50"},
                      smtp={"host": "smtp.gmail.com", "user": "caja@negocio.cl"})
    cfg, boleta, smtp = bol.load_settings()
    assert boleta["print_mode"] == "escpos_red" and boleta["host"] == "192.168.1.50"
    assert boleta["port"] == 9100 and boleta["paper_mm"] == 80
    assert smtp["user"] == "caja@negocio.cl" and smtp["port"] == 587
    # No borra el resto de la configuracion.
    assert cfg["business_name"] == "Mi POS"


def test_password_dpapi_ida_y_vuelta():
    pytest.importorskip("win32crypt")
    stored = bol.protect_password("mi-clave")
    assert stored and "mi-clave" not in stored
    assert bol.unprotect_password(stored) == "mi-clave"


def test_correo_viene_apagado_por_defecto(tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    _cfg, _boleta, smtp = bol.load_settings()
    assert bol.email_enabled(smtp) is False
    bol.save_settings(smtp={"enabled": True})
    assert bol.email_enabled(bol.load_settings()[2]) is True


def test_modo_recomendado_es_impresora_de_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(tmp_path / "config.json"))
    assert bol.load_settings()[1]["print_mode"] == "windows"
    assert "recomendado" in bol.PRINT_MODES["windows"]


# ---------- Encabezado del PDF con los datos del negocio ----------
PAPER_80_PT = 226.77  # 80 mm en puntos


def _pdf_content(path):
    """Contenido descomprimido de la pagina (los PDF de fpdf2 van en Flate)."""
    with open(path, "rb") as f:
        raw = f.read()
    parts = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        try:
            parts.append(zlib.decompress(m.group(1)).decode("latin-1"))
        except zlib.error:
            continue
    return raw, "\n".join(parts)


def _pdf_lines(path):
    """[(tamano_de_letra, texto)] de cada linea impresa, en orden."""
    _raw, content = _pdf_content(path)
    size, out = None, []
    for line in content.splitlines():
        m = re.match(r"BT /F\d+ ([\d.]+) Tf ET", line)
        if m:
            size = float(m.group(1))
            continue
        m = re.match(r"BT [\d.]+ [\d.]+ Td \((.*)\) Tj ET$", line)
        if m:
            text = re.sub(r"\\([()\\])", r"\1", m.group(1))
            out.append((size, text))
    return out


def _pdf_text(path):
    return "\n".join(t for _s, t in _pdf_lines(path))


def _cfg_file(tmp_path, monkeypatch, **cfg):
    path = tmp_path / "config.json"
    monkeypatch.setattr(core_config, "CONFIG_PATH", str(path))
    core_config.save_config({**core_config.DEFAULT_CONFIG, **cfg}, str(path))


def test_pdf_incluye_rut_direccion_y_telefono_de_la_config(temp_db, tmp_path, monkeypatch):
    _cfg_file(
        tmp_path, monkeypatch,
        business_name="Cervecería Prueba", rut="76.123.456-7",
        address="Av. Providencia 1234", phone="+56 9 1234 5678",
    )
    # cfg=None: los datos salen de load_config(), como al cobrar en la app.
    data = bol.build_receipt(_venta(), received=5000)
    text = _pdf_text(bol.build_pdf(data, str(tmp_path / "c.pdf"), paper_mm=80))
    for expected in ("Cervecería Prueba", "RUT: 76.123.456-7", "Av. Providencia 1234", "Tel: +56 9 1234 5678"):
        assert expected in text, expected
    # Orden del encabezado: nombre, RUT, direccion, telefono y luego el titulo.
    order = [text.index(x) for x in ("Cervecería Prueba", "RUT:", "Av. Providencia", "Tel:", bol.DOC_TITLE)]
    assert order == sorted(order)


def test_pdf_mantiene_titulo_aviso_numero_fecha_y_gracias(temp_db, tmp_path, monkeypatch):
    _cfg_file(tmp_path, monkeypatch, rut="76.123.456-7")
    sale_id = _venta()
    data = bol.build_receipt(sale_id, received=5000)
    text = _pdf_text(bol.build_pdf(data, str(tmp_path / "c.pdf")))
    assert bol.DOC_TITLE in text
    assert "no válido como boleta tributaria" in text
    assert f"N° {sale_id}" in text and data["created_at"] in text
    assert bol.THANKS.replace("¡", "") in text.replace("¡", "")


def test_pdf_con_campos_vacios_no_imprime_lineas_en_blanco(temp_db, tmp_path, monkeypatch):
    _cfg_file(tmp_path, monkeypatch, business_name="Mi POS", rut="", address="", phone="")
    data = bol.build_receipt(_venta(), received=5000)
    blocks = bol.receipt_blocks(data, 42)
    # Sin datos opcionales: nombre y enseguida la primera linea separadora.
    assert blocks[0][0].strip() == "Mi POS" and blocks[1][1] == "rule"
    assert all(text.strip() for text, _style in blocks)  # ninguna linea vacia
    text = _pdf_text(bol.build_pdf(data, str(tmp_path / "c.pdf")))
    assert "RUT" not in text and "Tel:" not in text
    assert bol.DOC_TITLE in text and "$4.000" in text


@pytest.mark.parametrize(
    "cfg",
    [
        {"rut": None, "address": None, "phone": None},          # null en config.json
        {"rut": "   ", "address": "  ", "phone": " "},          # solo espacios
        {"phone": 56912345678},                                  # numero, no texto
        {"business_name": ""},                                   # nombre vacio -> "Mi POS"
    ],
)
def test_pdf_no_se_rompe_con_valores_raros_en_config(temp_db, tmp_path, cfg):
    data = bol.build_receipt(_venta(), received=5000, cfg=cfg)
    path = bol.build_pdf(data, str(tmp_path / "c.pdf"))
    text = _pdf_text(path)
    assert bol.DOC_TITLE in text
    if cfg.get("phone") == 56912345678:
        assert "Tel: 56912345678" in text
    elif "business_name" in cfg:
        assert "Mi POS" in text
    else:
        assert "RUT" not in text and "Tel:" not in text


def test_pdf_separadores_entre_encabezado_items_y_totales(temp_db):
    data = bol.build_receipt(_venta(), received=5000, cfg=CFG)
    styles = [s for _t, s in bol.receipt_blocks(data, 42)]
    texts = [t for t, _s in bol.receipt_blocks(data, 42)]
    rules = [i for i, s in enumerate(styles) if s == "rule"]
    first_item = next(i for i, t in enumerate(texts) if t.startswith("Cerveza"))
    total = next(i for i, t in enumerate(texts) if t.startswith("TOTAL"))
    # Hay una regla antes de los items, otra entre items y totales, y otra al cierre.
    assert any(r < first_item for r in rules)
    assert any(first_item < r < total for r in rules)
    assert any(r > total for r in rules)
    assert styles[total] == "bold_left"  # TOTAL en negrita
    assert styles[0] == "big_center"     # nombre centrado y en negrita


def test_pdf_es_blanco_y_negro_ancho_ticket_sin_imagenes(temp_db, tmp_path):
    data = bol.build_receipt(_venta(), received=5000, cfg=CFG)
    raw, content = _pdf_content(bol.build_pdf(data, str(tmp_path / "c.pdf"), paper_mm=80))
    assert f"/MediaBox [0 0 {PAPER_80_PT}".encode() in raw  # 80 mm de ancho
    assert not re.search(r"\b(rg|RG|k|K|sc|SC|scn|SCN)\b", content)  # ningun operador de color
    # Sin logo ni imagenes. "/ProcSet [... /ImageB ...]" lo escribe fpdf2 siempre
    # y no es una imagen: se buscan objetos de imagen reales.
    assert not re.search(rb"/Subtype\s*/Image", raw) and b"/XObject" not in raw


def test_pdf_nombre_largo_cabe_en_el_ancho_del_ticket(temp_db, tmp_path):
    cfg = dict(CFG, business_name="Cervecería Artesanal Los Tres Hermanos SpA")
    data = bol.build_receipt(_venta(), received=5000, cfg=cfg)
    lines = _pdf_lines(bol.build_pdf(data, str(tmp_path / "c.pdf"), paper_mm=80))
    for size, text in lines:
        # Courier: cada caracter mide 0.6 de la altura de letra.
        width_mm = len(text) * 0.6 * size / 72 * 25.4
        assert width_mm <= 80 - 6 - 2, f"{text!r} mide {width_mm:.1f} mm y se sale del ticket"


def test_pdf_cambios_no_tocan_el_contenido_de_la_venta(temp_db):
    data = bol.build_receipt(_venta(), received=5000, cfg=CFG)
    text = bol.receipt_text(data, 42)
    for expected in ("2 x $1.500", "$3.000", "1 x $1.000", "$4.000", "Efectivo", "$5.000", "$1.000"):
        assert expected in text, expected


def test_pdf_de_ejemplo_para_revisar(temp_db, tmp_path, monkeypatch):
    """Genera un PDF completo. Con MIPOS_SAMPLE_PDF_DIR lo deja ahi para verlo."""
    _cfg_file(
        tmp_path, monkeypatch,
        business_name="Cervecería Prueba", rut="76.123.456-7",
        address="Av. Providencia 1234, Santiago", phone="+56 9 1234 5678",
    )
    data = bol.build_receipt(_venta(), received=5000)
    path = bol.build_pdf(data, str(tmp_path / "ejemplo.pdf"), paper_mm=80)
    assert os.path.getsize(path) > 1000
    out_dir = os.environ.get("MIPOS_SAMPLE_PDF_DIR")
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        shutil.copyfile(path, os.path.join(out_dir, "comprobante_ejemplo.pdf"))
