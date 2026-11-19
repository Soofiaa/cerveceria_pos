"""Tests del comprobante interno de venta (flet_app/boletas.py).

Nada sale del equipo: el SMTP es un servidor falso y la termica de red es
un socket local. No se imprime en ninguna impresora real.
"""

import socket
import smtplib
import threading

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
