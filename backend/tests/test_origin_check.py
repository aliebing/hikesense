"""POST requests from a foreign web page are refused (defence in depth next to SameSite=strict)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from hikesense.api.app import create_app
from hikesense.config import Settings
from hikesense.guest_quota import GuestDecision


class Quota:
    def acquire(self, key):
        return GuestDecision(True, "ok", 0)


@pytest.fixture
def client(tmp_path):
    s = Settings(
        supabase_db_url="postgresql://x:x@127.0.0.1:1/none",
        chat_log_path=tmp_path / "chat.jsonl",
        chroma_dir=tmp_path / "chroma",
        hikesense_allowed_origins="https://hikesense.example.org",
    )
    app = create_app(s, deps_factory=lambda: "deps", guest_quota=Quota(), status_lookup=lambda u: "aktiv")
    return TestClient(app)


def body():
    return {"thread_id": str(uuid.uuid4()), "message": "x"}


@pytest.mark.parametrize("path", ["/chat", "/backend/login", "/backend/logout"])
def test_foreign_origin_is_refused(client, path):
    r = client.post(path, json=body(), headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json() == {"detail": "origin_not_allowed"}


def test_same_host_behind_the_proxy_is_allowed(client):
    # the web app forwards the browser's Host as X-Forwarded-Host (phone tunnel, any name)
    h = {"Origin": "https://abc.trycloudflare.com", "X-Forwarded-Host": "abc.trycloudflare.com"}
    assert client.post("/backend/logout", headers=h).status_code == 200


def test_local_and_configured_origins_are_allowed(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000", "https://hikesense.example.org"):
        assert client.post("/backend/logout", headers={"Origin": origin}).status_code == 200


def test_no_origin_header_is_allowed(client):
    # curl, the smoke run, server-side calls: no browser, no cross-site request
    assert client.post("/backend/logout").status_code == 200


def test_get_is_not_checked(client):
    assert client.get("/health", headers={"Origin": "https://evil.example"}).status_code == 200


def test_opaque_null_origin_is_refused(client):
    r = client.post("/backend/logout", headers={"Origin": "null"})
    assert r.status_code == 403
