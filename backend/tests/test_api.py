import os

import pytest
from fastapi.testclient import TestClient

from hikeall.api.app import create_app
from hikeall.config import Settings

DEFAULT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def test_health_reports_db_false_without_db():
    app = create_app(Settings(supabase_db_url="postgresql://x:x@127.0.0.1:1/none"))
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": False}


@pytest.mark.db
def test_health_reports_db_true(conn):
    url = os.environ.get("SUPABASE_DB_URL", DEFAULT_URL)
    app = create_app(Settings(supabase_db_url=url))
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True}
