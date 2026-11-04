import bcrypt

from hikesense import cli


def _run(monkeypatch, capsys, *answers):
    it = iter(answers)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(it))
    code = cli.admin_secrets_cmd()
    return code, capsys.readouterr()


def test_prints_hash_session_secret_and_guest_salt(monkeypatch, capsys):
    code, out = _run(monkeypatch, capsys, "richtig-lang", "richtig-lang")
    assert code == 0
    lines = dict(
        line.split("=", 1) for line in out.out.splitlines() if line.startswith("HIKESENSE_")
    )
    assert set(lines) == {
        "HIKESENSE_ADMIN_PASSWORD_HASH",
        "HIKESENSE_ADMIN_SESSION_SECRET",
        "HIKESENSE_GUEST_SALT",
    }
    assert bcrypt.checkpw(b"richtig-lang", lines["HIKESENSE_ADMIN_PASSWORD_HASH"].strip("'").encode())


def test_password_over_72_bytes_is_refused_not_a_crash(monkeypatch, capsys):
    long = "ä" * 40  # 80 bytes in UTF-8
    code, out = _run(monkeypatch, capsys, long, long)
    assert code == 2
    assert "72" in out.err
