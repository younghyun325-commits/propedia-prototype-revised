import sqlite3

import pytest

from core.db import connect_ro


def test_insert_fails_on_readonly_connection():
    con = connect_ro()
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("INSERT INTO meta(key, value) VALUES ('x', 'y')")
    finally:
        con.close()
