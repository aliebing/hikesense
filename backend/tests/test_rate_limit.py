import pytest

from hikeall.rate_limit import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, s):
        self.now += s


@pytest.fixture
def fake_clock():
    return FakeClock()


def test_rate_limit_per_minute(fake_clock):
    rl = RateLimiter(clock=fake_clock)
    assert all(rl.acquire("1.2.3.4").allowed for _ in range(10))
    decision = rl.acquire("1.2.3.4")
    assert not decision.allowed
    assert 1 <= decision.retry_after_s <= 60


def test_retry_after_and_recovery(fake_clock):
    rl = RateLimiter(clock=fake_clock)
    for _ in range(10):
        rl.acquire("ip")
    fake_clock.advance(20)
    assert rl.acquire("ip").retry_after_s == 40
    fake_clock.advance(40)
    assert rl.acquire("ip").allowed


def test_ips_are_independent(fake_clock):
    rl = RateLimiter(clock=fake_clock)
    for _ in range(10):
        rl.acquire("a")
    assert not rl.acquire("a").allowed
    assert rl.acquire("b").allowed


def test_rate_limit_per_day(fake_clock):
    rl = RateLimiter(clock=fake_clock)
    for _ in range(100):
        assert rl.acquire("ip").allowed
        fake_clock.advance(61)  # stays under the per-minute cap
    decision = rl.acquire("ip")
    assert not decision.allowed
    assert decision.retry_after_s > 60
    fake_clock.advance(86400)
    assert rl.acquire("ip").allowed


def test_rejected_call_does_not_count(fake_clock):
    rl = RateLimiter(clock=fake_clock)
    for _ in range(10):
        rl.acquire("ip")
    for _ in range(5):
        assert not rl.acquire("ip").allowed
    fake_clock.advance(60)
    assert all(rl.acquire("ip").allowed for _ in range(10))


def test_retry_after_is_max_of_blocking_windows(fake_clock):
    rl = RateLimiter(per_minute=2, per_day=3, clock=fake_clock)
    assert rl.acquire("ip").allowed
    fake_clock.advance(100)
    assert rl.acquire("ip").allowed
    assert rl.acquire("ip").allowed
    # minute window (2 in last 60 s) and day window (3 in 24 h) both block
    decision = rl.acquire("ip")
    assert not decision.allowed
    assert decision.retry_after_s == 86400 - 100
