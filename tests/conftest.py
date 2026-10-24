import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import connect_ro  # noqa: E402


@pytest.fixture()
def con():
    c = connect_ro()
    yield c
    c.close()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from api.index import app
    return TestClient(app)


def parcel_review_id(con) -> int:
    return con.execute("SELECT id FROM review_queue WHERE item_type='parcel_inclusion'").fetchone()["id"]
