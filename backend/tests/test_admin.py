import pytest

from hikeall.admin import ADMIN_EMAIL, ensure_admin, is_bcrypt

HASH_A = "$2a$10$" + "a" * 53
HASH_B = "$2b$10$" + "b" * 53


def test_is_bcrypt():
    assert is_bcrypt(HASH_A)
    assert not is_bcrypt("admin")
    assert not is_bcrypt("")


def test_rejects_plain_password():
    with pytest.raises(ValueError, match="bcrypt"):
        ensure_admin(None, "admin")  # type: ignore[arg-type]


@pytest.mark.db
def test_creates_then_updates_admin(conn, monkeypatch):
    monkeypatch.setattr(conn, "commit", lambda: None)  # the fixture rolls back
    conn.execute("delete from auth.users where email = %s", (ADMIN_EMAIL,))
    assert ensure_admin(conn, HASH_A) == "angelegt"
    uid, pw, confirmed = conn.execute(
        "select id, encrypted_password, email_confirmed_at from auth.users where email = %s",
        (ADMIN_EMAIL,),
    ).fetchone()
    assert pw == HASH_A and confirmed is not None
    assert conn.execute(
        "select count(*) from auth.identities where user_id = %s and provider = 'email'", (uid,)
    ).fetchone()[0] == 1
    assert ensure_admin(conn, HASH_B) == "aktualisiert"
    assert conn.execute(
        "select encrypted_password from auth.users where id = %s", (uid,)
    ).fetchone()[0] == HASH_B
