import bcrypt

from hikesense.admin_session import SESSION_S, LoginThrottle, check_password, issue, valid

SECRET = "s" * 32


def test_valid_cookie_accepted():
    assert valid(issue(SECRET, now=1000.0), SECRET, now=1000.0 + SESSION_S - 1)


def test_tampered_exp_rejected():
    exp, sig = issue(SECRET, now=1000.0).split(".")
    assert not valid(f"{int(exp) + 3600}.{sig}", SECRET, now=1000.0)


def test_wrong_secret_rejected():
    assert not valid(issue(SECRET, now=1000.0), "t" * 32, now=1000.0)


def test_expired_rejected():
    assert not valid(issue(SECRET, now=1000.0), SECRET, now=1000.0 + SESSION_S + 1)


def test_garbage_rejected():
    for bad in (None, "", "abc", "1.2.3", "x.y"):
        assert not valid(bad, SECRET, now=0.0)


def test_check_password():
    h = bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=4)).decode()
    assert check_password("pw", h)
    assert not check_password("px", h)
    assert not check_password("pw", "not-a-hash")


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
