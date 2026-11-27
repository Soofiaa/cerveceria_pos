# conftest.py (raíz del repo)
#
# Vive en la raíz (no dentro de tests/) para que pytest agregue este
# directorio a sys.path automáticamente y los tests puedan hacer
# "import core.xxx" / "import ui.xxx" sin configuración adicional.
import hashlib
import os
import shutil
import tempfile

# ---------- Aislamiento de los datos reales del usuario ----------
# core/config.py y core/db_manager.py calculan CONFIG_PATH y DB_PATH con
# expanduser("~") AL IMPORTARSE, y en Windows eso lee USERPROFILE. Por eso
# esto va antes de cualquier import de core: durante los tests "~" es una
# carpeta temporal y las rutas por defecto nunca son las reales. Asi, un test
# que olvide pedir temp_db, o un monkeypatch.undo() que revierta su DB_PATH,
# cae en esa carpeta temporal y no en ~/MiPOS.
_REAL_HOME = os.path.expanduser("~")
_REAL_FILES = [
    os.path.join(_REAL_HOME, "MiPOS", "cerveceria.db"),
    os.path.join(_REAL_HOME, "MiPOS", "config.json"),
]
_FAKE_HOME = tempfile.mkdtemp(prefix="mipos_tests_home_")
os.environ["USERPROFILE"] = _FAKE_HOME
os.environ["HOME"] = _FAKE_HOME  # por si algo lo lee fuera de Windows

import pytest  # noqa: E402

import core.db_manager as db_manager  # noqa: E402

assert not db_manager.DB_PATH.startswith(os.path.join(_REAL_HOME, "MiPOS")), (
    "conftest: core se importo antes de aislar USERPROFILE; DB_PATH apunta a la base real"
)


def _huella(path):
    """sha256 del archivo, o None si no existe."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="session", autouse=True)
def _datos_reales_intactos():
    """Red de seguridad: si la suite cambia la base o el config reales, la corrida falla."""
    antes = {p: _huella(p) for p in _REAL_FILES}
    yield
    cambiados = [p for p in _REAL_FILES if _huella(p) != antes[p]]
    shutil.rmtree(_FAKE_HOME, ignore_errors=True)
    if cambiados:
        pytest.fail("La suite modifico datos reales del usuario: " + ", ".join(cambiados))


@pytest.fixture
def temp_db(monkeypatch):
    """
    Apunta DB_PATH a un archivo SQLite temporal (no ':memory:') y corre
    bootstrap() antes de cada test, para no tocar nunca la base de datos
    real del usuario (~/CerveceriaPOS/cerveceria.db).

    Nota sobre ':memory:': se descartó a propósito. get_conn() en
    db_manager.py abre una conexión nueva (sqlite3.connect(DB_PATH)) en
    cada llamada; con ':memory:' cada una de esas conexiones sería una
    base de datos en blanco distinta (SQLite no comparte una DB en
    memoria entre conexiones separadas salvo con una URI de caché
    compartida), así que bootstrap() crearía las tablas en una conexión
    y la siguiente operación las vería vacías. Un archivo temporal por
    test evita ese problema y sigue sin tocar datos reales.
    """
    tmpdir = tempfile.mkdtemp(prefix="cerveceria_pos_test_")
    db_path = os.path.join(tmpdir, "test.db")

    monkeypatch.setattr(db_manager, "DB_PATH", db_path)
    db_manager.bootstrap()

    yield db_path

    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_real_api_server(monkeypatch):
    """Ningun test abre un puerto real: en modo "server" main() arrancaria la API de la Caja 1.

    Los tests que necesitan la API la prueban con el cliente de pruebas de Flask
    (tests/test_api_server.py); los de main() solo comprueban que se le pidio arrancar.
    """
    try:
        from flet_app import main as pos_main
    except Exception:  # los tests de core no necesitan flet instalado
        return
    calls = []

    def fake_start(settings=None):
        calls.append(settings)
        return False

    monkeypatch.setattr(pos_main, "start_api_server_if_needed", fake_start)
    pos_main._api_start_calls = calls
