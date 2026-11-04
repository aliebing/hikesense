import json

import httpx
import pytest

from hikesense.config import Settings
from hikesense.supabase_admin import SupabaseAdmin, SupabaseAdminError

AUTH = "http://127.0.0.1:54321/auth/v1"


def settings(**kw):
    return Settings(
        **{
            "supabase_db_url": "postgresql://x",
            "supabase_url": "http://127.0.0.1:54321",
            "supabase_service_role_key": "service-key",
            **kw,
        }
    )


def test_ban_sends_long_ban_duration(respx_mock):
    route = respx_mock.put(f"{AUTH}/admin/users/u1").mock(
        return_value=httpx.Response(200, json={"id": "u1"})
    )
    with httpx.Client() as http:
        SupabaseAdmin(settings(), http).ban("u1")
    req = route.calls.last.request
    assert json.loads(req.content) == {"ban_duration": "876000h"}
    assert req.headers["apikey"] == "service-key"
    assert req.headers["authorization"] == "Bearer service-key"


def test_unban_sends_none(respx_mock):
    route = respx_mock.put(f"{AUTH}/admin/users/u1").mock(
        return_value=httpx.Response(200, json={"id": "u1"})
    )
    with httpx.Client() as http:
        SupabaseAdmin(settings(), http).unban("u1")
    assert json.loads(route.calls.last.request.content) == {"ban_duration": "none"}


def test_confirm_user_sets_email_confirm(respx_mock):
    route = respx_mock.put(f"{AUTH}/admin/users/u1").mock(
        return_value=httpx.Response(200, json={"id": "u1"})
    )
    with httpx.Client() as http:
        SupabaseAdmin(settings(), http).confirm_user("u1")
    assert json.loads(route.calls.last.request.content) == {"email_confirm": True}


def test_create_confirmed_user_sets_email_confirm(respx_mock):
    route = respx_mock.post(f"{AUTH}/admin/users").mock(
        return_value=httpx.Response(200, json={"id": "new-id"})
    )
    with httpx.Client() as http:
        uid = SupabaseAdmin(settings(), http).create_confirmed_user("a@b.de", "pw-123456")
    assert uid == "new-id"
    assert json.loads(route.calls.last.request.content) == {
        "email": "a@b.de",
        "password": "pw-123456",
        "email_confirm": True,
    }


def test_delete_user(respx_mock):
    route = respx_mock.delete(f"{AUTH}/admin/users/u1").mock(
        return_value=httpx.Response(200, json={})
    )
    with httpx.Client() as http:
        SupabaseAdmin(settings(), http).delete_user("u1")
    assert route.called


def test_find_user_id_pages_through_users(respx_mock):
    pages = [
        httpx.Response(
            200, json={"users": [{"id": f"x{i}", "email": f"x{i}@a.de"} for i in range(50)]}
        ),
        httpx.Response(200, json={"users": [{"id": "hit", "email": "Admin@HikeSense.local"}]}),
    ]
    respx_mock.get(f"{AUTH}/admin/users").mock(side_effect=pages)
    with httpx.Client() as http:
        assert SupabaseAdmin(settings(), http).find_user_id("admin@hikesense.local") == "hit"


def test_find_user_id_none_when_missing(respx_mock):
    respx_mock.get(f"{AUTH}/admin/users").mock(return_value=httpx.Response(200, json={"users": []}))
    with httpx.Client() as http:
        assert SupabaseAdmin(settings(), http).find_user_id("nobody@a.de") is None


def test_error_status_raises(respx_mock):
    respx_mock.put(f"{AUTH}/admin/users/u1").mock(return_value=httpx.Response(500, json={}))
    with httpx.Client() as http, pytest.raises(SupabaseAdminError) as exc:
        SupabaseAdmin(settings(), http).ban("u1")
    assert exc.value.status == 500


def test_unreachable_raises_status_zero(respx_mock):
    respx_mock.put(f"{AUTH}/admin/users/u1").mock(side_effect=httpx.ConnectError("down"))
    with httpx.Client() as http, pytest.raises(SupabaseAdminError) as exc:
        SupabaseAdmin(settings(), http).ban("u1")
    assert exc.value.status == 0


def test_missing_key_raises():
    with pytest.raises(SupabaseAdminError):
        SupabaseAdmin(settings(supabase_service_role_key=None))
