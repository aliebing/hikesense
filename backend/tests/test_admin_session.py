import bcrypt

from hikesense.admin_session import SESSION_S, LoginThrottle, Sessions, check_password

SECRET = "s" * 32
_store = Sessions()
issue, valid = _store.issue, _store.valid


def test_valid_cookie_accepted():
    assert valid(issue(SECRET, now=1000.0), SECRET, now=1000.0 + SESSION_S - 1)


def test_tampered_exp_rejected():
    exp, sid, sig = issue(SECRET, now=1000.0).split(".")
    assert not valid(f"{int(exp) + 3600}.{sid}.{sig}", SECRET, now=1000.0)


def test_wrong_secret_rejected():
    assert not valid(issue(SECRET, now=1000.0), "t" * 32, now=1000.0)


def test_expired_rejected():
    assert not valid(issue(SECRET, now=1000.0), SECRET, now=1000.0 + SESSION_S + 1)


def test_garbage_rejected():
    for bad in (None, "", "abc", "1.2.3", "x.y", "1.2"):
        assert not valid(bad, SECRET, now=0.0)


def test_non_ascii_digits_rejected_without_crash():
    # "²" and Arabic-Indic digits pass str.isdigit() but are no expiry time
    _, sid, sig = issue(SECRET, now=1000.0).split(".")
    for exp in ("\u00b2", "\u0661\u0662\u0663", "\uff11\uff12"):
        assert not valid(f"{exp}.{sid}.{sig}", SECRET, now=0.0)


def test_logout_revokes_the_cookie_on_the_server():
    store = Sessions()
    cookie = store.issue(SECRET, now=1000.0)
    store.revoke(cookie)
    assert not store.valid(cookie, SECRET, now=1001.0)


def test_cookie_of_another_process_is_not_valid():
    # a restart forgets all sessions: the admin signs in again
    cookie = Sessions().issue(SECRET, now=1000.0)
    assert not Sessions().valid(cookie, SECRET, now=1001.0)


def test_expired_sessions_are_dropped():
    store = Sessions()
    store.issue(SECRET, now=0.0)
    store.issue(SECRET, now=SESSION_S + 10.0)
    assert len(store) == 1


def test_check_password():
    h = bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=4)).decode()
    assert check_password("pw", h)
    assert not check_password("px", h)
    assert not check_password("pw", "not-a-hash")
    assert not check_password("x" * 100, h)  # over bcrypt's 72 bytes: refused, no crash


def test_throttle_blocks_after_five_failures_and_frees_after_window():
    now = [0.0]
    t = LoginThrottle(clock=lambda: now[0])
    for _ in range(5):
        assert t.blocked("ip") == 0
        t.failed("ip")
    assert t.blocked("ip") > 0
    assert t.blocked("other") == 0
    now[0] = 901.0
    assert t.blocked("ip") == 0


def test_throttle_success_resets():
    t = LoginThrottle(clock=lambda: 0.0)
    for _ in range(4):
        t.failed("ip")
    t.succeeded("ip")
    t.failed("ip")
    assert t.blocked("ip") == 0


def test_try_acquire_reserves_before_the_password_check():
    # parallel wrong logins: each attempt is counted when it starts, not after bcrypt
    t = LoginThrottle(clock=lambda: 0.0)
    granted = [t.try_acquire("ip") for _ in range(8)]
    assert granted[:5] == [0] * 5
    assert all(w > 0 for w in granted[5:])


def test_try_acquire_success_frees_the_ip():
    t = LoginThrottle(clock=lambda: 0.0)
    for _ in range(4):
        t.try_acquire("ip")
    t.succeeded("ip")
    assert t.try_acquire("ip") == 0
