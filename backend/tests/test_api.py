import os

import pytest
from fastapi.testclient import TestClient

from hikeall.api.app import create_app
from hikeall.config import Settings

DEFAULT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


@pytest.fixture(autouse=True)
def _empty_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("HIKEALL_DATA_DIR", str(tmp_path))  # no knowledge index here


def test_health_reports_db_false_without_db():
    app = create_app(Settings(supabase_db_url="postgresql://x:x@127.0.0.1:1/none", openrouter_api_key=None))
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.pop("auth"), bool)
    assert body == {"status": "ok", "db": False, "llm": False, "knowledge": False}


@pytest.mark.db
def test_health_reports_db_true(conn):
    url = os.environ.get("SUPABASE_DB_URL", DEFAULT_URL)
    app = create_app(Settings(supabase_db_url=url, openrouter_api_key=None))
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.pop("auth"), bool)
    assert body == {"status": "ok", "db": True, "llm": False, "knowledge": False}


def test_health_reports_db_false_when_url_unset(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    r = TestClient(create_app()).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.pop("auth"), bool)
    assert body == {"status": "ok", "db": False, "llm": False, "knowledge": False}


def test_health_reports_db_false_for_malformed_url():
    app = create_app(Settings(supabase_db_url="not a url ::", openrouter_api_key=None))
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.pop("auth"), bool)
    assert body == {"status": "ok", "db": False, "llm": False, "knowledge": False}
