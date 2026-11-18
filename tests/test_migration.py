import os
import shutil
import sqlite3
import pytest
from core.db_manager import _migrate_db_if_needed, USER_DATA_DIR, OLD_USER_DATA_DIR

def test_migration_copies_db(tmp_path):
    # Setup usando tmp_path
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    
    old_db = old_dir / "cerveceria.db"
    new_db = new_dir / "cerveceria.db"
    
    # Create dummy old DB
    with sqlite3.connect(old_db) as con:
        con.execute("CREATE TABLE test (id INTEGER)")
        con.execute("INSERT INTO test VALUES (1)")
    
    # Run migration
    _migrate_db_if_needed(old_dir=str(old_dir), new_dir=str(new_dir))
    
    # Verify
    assert new_db.exists()
    with sqlite3.connect(str(new_db)) as con:
        res = con.execute("SELECT id FROM test").fetchone()
        assert res[0] == 1
