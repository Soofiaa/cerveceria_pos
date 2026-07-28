# conftest.py (raíz del repo)
#
# Vive en la raíz (no dentro de tests/) para que pytest agregue este
# directorio a sys.path automáticamente y los tests puedan hacer
# "import core.xxx" / "import ui.xxx" sin configuración adicional.
import os
import shutil
import tempfile

import pytest

import core.db_manager as db_manager


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
