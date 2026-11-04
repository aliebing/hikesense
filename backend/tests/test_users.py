import uuid

import pytest

from hikesense.users import list_app_users, set_status, status_of

pytestmark = pytest.mark.db


def _user(conn, confirmed=True):
    uid = uuid.uuid4()
    conn.execute(
        "insert into auth.users (id, email, email_confirmed_at) values (%s, %s, %s)",
        (uid, f"{uid}@test.invalid", "2026-11-04T10:00:00Z" if confirmed else None),
    )
    return str(uid)


def _find(conn, uid):
    return next(u for u in list_app_users(conn) if u.user_id == uid)


def test_list_marks_unconfirmed(conn):
    uid = _user(conn, confirmed=False)
    u = _find(conn, uid)
    assert u.status == "unbestätigt"
    assert u.email == f"{uid}@test.invalid"


def test_list_shows_active_and_blocked(conn):
    a, b = _user(conn), _user(conn)
    set_status(conn, b, "gesperrt")
    assert _find(conn, a).status == "aktiv"
    assert _find(conn, b).status == "gesperrt"


def test_status_of_unknown_is_aktiv(conn):
    assert status_of(conn, str(uuid.uuid4())) == "aktiv"


def test_status_of_invalid_uuid_is_aktiv(conn):
    assert status_of(conn, "gast:abc") == "aktiv"
    assert conn.execute("select 1").fetchone() == (1,)  # transaction still usable


def test_set_status_sets_and_clears_blocked_at(conn):
    a = _user(conn)
    assert set_status(conn, a, "gesperrt") is True
    assert status_of(conn, a) == "gesperrt"
    assert conn.execute("select blocked_at is not null from app_users where user_id = %s", (a,)).fetchone()[0]
    assert set_status(conn, a, "aktiv") is True
    assert conn.execute("select status, blocked_at from app_users where user_id = %s", (a,)).fetchone() == ("aktiv", None)


def test_set_status_unknown_user_returns_false(conn):
    assert set_status(conn, str(uuid.uuid4()), "gesperrt") is False


class FakeAdmin:
    def __init__(self, admin_id=None):
        self.confirmed, self.deleted, self.admin_id = [], [], admin_id

    def confirm_user(self, uid):
        self.confirmed.append(uid)

    def find_user_id(self, email):
        assert email == "admin@hikesense.local"
        return self.admin_id

    def delete_user(self, uid):
        self.deleted.append(uid)


def test_migrate_confirms_unconfirmed_and_deletes_old_admin(conn):
    from hikesense.users import migrate_accounts

    pending = _user(conn, confirmed=False)
    done = _user(conn)
    fake = FakeAdmin(admin_id="old-admin")
    lines = migrate_accounts(conn, fake)
    assert pending in fake.confirmed and done not in fake.confirmed
    assert fake.deleted == ["old-admin"]
    assert any("old-admin" in line or "admin@hikesense.local" in line for line in lines)


def test_migrate_without_old_admin_deletes_nothing(conn):
    from hikesense.users import migrate_accounts

    fake = FakeAdmin(admin_id=None)
    migrate_accounts(conn, fake)
    assert fake.deleted == []
