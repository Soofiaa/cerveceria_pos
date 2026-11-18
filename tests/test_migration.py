import os
import shutil
import sqlite3
import pytest
from core.db_manager import _migrate_db_if_needed, USER_DATA_DIR, OLD_USER_DATA_DIR

def test_migration_copies_db():
    # Setup
    if not os.path.exists(OLD_USER_DATA_DIR):
        os.makedirs(OLD_USER_DATA_DIR)
    
    old_db = os.path.join(OLD_USER_DATA_DIR, "cerveceria.db")
    new_db = os.path.join(USER_DATA_DIR, "cerveceria.db")
    
    # Clean up previous runs
    if os.path.exists(new_db):
        os.remove(new_db)
    
    # Create dummy old DB
    with sqlite3.connect(old_db) as con:
        con.execute("DROP TABLE IF EXISTS test")
        con.execute("CREATE TABLE test (id INTEGER)")
        con.execute("INSERT INTO test VALUES (1)")
    
    # Run migration
    _migrate_db_if_needed()
    
    # Verify
    assert os.path.exists(new_db)
    with sqlite3.connect(new_db) as con:
        res = con.execute("SELECT id FROM test").fetchone()
        assert res[0] == 1
