"""Mi POS - Modo de la caja (Fase 5.1, multi-caja).

Tres modos, definidos en config.json:
- "standalone": una sola maquina con base local (como antes de esta fase).
- "server": la Caja 1. App local + API HTTP, con la base central.
- "client": caja adicional. No usa ni crea base local: todo va por la API.

Claves nuevas en config.json: "mode", "server_url", "caja_number", "caja_name"
y "api_token" (clave compartida entre la Caja 1 y las cajas cliente; la Caja 1 la
genera sola al arrancar si no existe, ver ensure_api_token).
core/config.py no se toca: sus valores por defecto no incluyen estas claves,
asi que aqui se aplican los defaults y se leen del archivo con load_config().
"""

import secrets
from urllib.parse import urlparse

from core import config as core_config

MODES = ("standalone", "server", "client")
DEFAULT_MODE = "server"  # la Caja 1 es el caso por defecto de esta fase
DEFAULT_PORT = 8780


def _caja_number(cfg):
    try:
        n = int(cfg.get("caja_number"))
    except (TypeError, ValueError):
        return 1
    return n if n >= 1 else 1


def get_caja_settings(cfg=None):
    """Modo y datos de la caja con valores por defecto. Nunca lanza por un config raro."""
    if cfg is None:
        cfg = core_config.load_config()
    mode = cfg.get("mode") if cfg.get("mode") in MODES else DEFAULT_MODE
    number = _caja_number(cfg)
    name = str(cfg.get("caja_name") or "").strip() or f"Caja {number}"
    return {
        "mode": mode,
        "server_url": normalize_url(cfg.get("server_url")),
        "caja_number": number,
        "caja_name": name,
        "api_port": DEFAULT_PORT,
        "api_token": str(cfg.get("api_token") or "").strip(),
    }


def normalize_url(url):
    """'192.168.1.10' -> 'http://192.168.1.10:8780'; vacio si no es una direccion usable."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    if any(ch.isspace() for ch in raw):
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    try:
        port = parsed.port or DEFAULT_PORT
    except ValueError:  # puerto fuera de rango o no numerico
        return ""
    return f"{parsed.scheme}://{parsed.hostname}:{port}"


def validate_client_url(url):
    """Mensaje de error para la cajera, o None si la direccion sirve."""
    if not normalize_url(url):
        return "Escribe la direccion de la Caja 1, por ejemplo 192.168.1.10 o http://192.168.1.10:8780."
    return None


def ensure_api_token():
    """Devuelve el token de la API; si no hay uno, genera uno aleatorio y lo guarda en config.json.

    Lo llama el arranque del servidor: la API de la Caja 1 nunca queda abierta a la red.
    secrets.token_urlsafe(16): 128 bits, sin caracteres que molesten al copiarlo.
    """
    cfg = dict(core_config.load_config())  # copia: load_config puede devolver DEFAULT_CONFIG
    token = str(cfg.get("api_token") or "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(16)
    cfg["api_token"] = token
    core_config.save_config(cfg)
    return token


def save_caja_settings(mode=None, server_url=None, caja_number=None, caja_name=None):
    """Guarda los campos pasados en config.json sin tocar el resto."""
    cfg = dict(core_config.load_config())  # copia: load_config puede devolver DEFAULT_CONFIG
    if mode is not None:
        if mode not in MODES:
            raise ValueError("Modo no valido.")
        cfg["mode"] = mode
    if server_url is not None:
        cfg["server_url"] = normalize_url(server_url) or str(server_url).strip()
    if caja_number is not None:
        cfg["caja_number"] = _caja_number({"caja_number": caja_number})
    if caja_name is not None:
        cfg["caja_name"] = str(caja_name).strip()
    core_config.save_config(cfg)
    return cfg
