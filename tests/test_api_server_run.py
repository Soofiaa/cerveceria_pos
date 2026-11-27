"""Tests para comprobar que run() de api_server usa run_simple y arranca correctamente.
"""

import threading
import time
import requests
import pytest

from flet_app import api_server


def test_api_server_run_uses_run_simple(monkeypatch):
    called = []
    flask_run_called = []

    monkeypatch.setattr(api_server, "bootstrap", lambda: None, raising=False)
    monkeypatch.setattr(api_server, "ensure_api_token", lambda: None)
    monkeypatch.setattr(api_server, "create_app", lambda: "sentinel-app")
    monkeypatch.setattr(api_server, "run_simple", lambda host, port, app, **kwargs: called.append((host, port, app, kwargs)))

    # Asegurar que Flask.run no se llame
    from flask import Flask
    monkeypatch.setattr(Flask, "run", lambda self, *a, **k: flask_run_called.append(1))

    api_server.run(host="127.0.0.1", port=8799, bootstrap=False)

    assert len(called) == 1
    host, port, app, kwargs = called[0]
    assert host == "127.0.0.1"
    assert port == 8799
    assert app == "sentinel-app"
    assert kwargs.get("threaded") is True
    assert kwargs.get("use_reloader") is False
    assert kwargs.get("use_debugger") is False
    assert flask_run_called == []


def test_api_server_run_smoke_real(temp_db, monkeypatch, tmp_path):
    # Base temporal y config temporal
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr("core.config.CONFIG_PATH", str(cfg_path))
    
    port = 8799
    # Arrancar run en un hilo daemon
    t = threading.Thread(target=lambda: api_server.run(host="127.0.0.1", port=port, bootstrap=True), daemon=True)
    t.start()

    # Polling hasta obtener 200 en /api/health (timeout 10s)
    url = f"http://127.0.0.1:{port}/api/health"
    start = time.time()
    ok = False
    while time.time() - start < 10:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code == 200 and r.json().get("ok"):
                ok = True
                break
        except Exception:
            time.sleep(0.2)

    assert ok, "El servidor empaquetado no respondió en /api/health a tiempo"
