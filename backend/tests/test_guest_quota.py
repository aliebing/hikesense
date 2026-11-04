import uuid

import pytest
from starlette.requests import Request

from hikesense.guest_quota import client_ip, guest_owner, ip_key, quota_acquire


def _request(headers=None, client=("203.0.113.7", 1234)):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(
        {"type": "http", "headers": raw, "client": client, "method": "POST", "path": "/chat"}
    )


def test_client_ip_ignores_forwarded_header_without_trusted_proxy():
    # Next's rewrite proxy passes X-Forwarded-For through unchanged: it is the client's own text
    assert client_ip(_request({"X-Forwarded-For": "1.2.3.4"})) == "203.0.113.7"


def test_client_ip_takes_the_entry_of_the_trusted_proxy():
    req = _request({"X-Forwarded-For": "6.6.6.6, 1.2.3.4, 10.0.0.9"})
    assert client_ip(req, trusted_hops=1) == "10.0.0.9"
    assert client_ip(req, trusted_hops=2) == "1.2.3.4"


def test_client_ip_falls_back_to_peer_when_header_is_too_short():
    assert client_ip(_request({"X-Forwarded-For": "1.2.3.4"}), trusted_hops=2) == "203.0.113.7"


def test_client_ip_falls_back_to_peer():
    assert client_ip(_request()) == "203.0.113.7"


def test_client_ip_unknown_without_any_source():
    assert client_ip(_request(client=None)) == "unknown"


def test_ip_key_groups_ipv6_by_64():
    assert ip_key("2001:db8::1") == ip_key("2001:db8::ffff")
    assert ip_key("2001:db8::1") != ip_key("2001:db8:0:1::1")


def test_ip_key_keeps_ipv4_and_garbage():
    assert ip_key("198.51.100.4") == "198.51.100.4"
    assert ip_key("not-an-ip") == "not-an-ip"


def test_guest_owner_has_prefix_and_no_ip():
    owner = guest_owner("198.51.100.4")
    assert owner.startswith("gast:") and len(owner) == len("gast:") + 12
    assert "198.51.100.4" not in owner


@pytest.mark.db
def test_eleventh_request_from_same_ip_is_refused(conn):
    key = f"k-{uuid.uuid4()}"
    for _ in range(10):
        assert quota_acquire(conn, key, per_day=10, total_per_day=10_000).allowed
    d = quota_acquire(conn, key, per_day=10, total_per_day=10_000)
    assert (d.allowed, d.reason) == (False, "ip")
    assert 0 < d.retry_after_s <= 86400


@pytest.mark.db
def test_total_cap_refuses_new_ip(conn):
    conn.execute("delete from guest_requests")
    for i in range(3):
        assert quota_acquire(conn, f"k{i}", per_day=10, total_per_day=3).allowed
    d = quota_acquire(conn, "k-new", per_day=10, total_per_day=3)
    assert (d.allowed, d.reason) == (False, "total")


@pytest.mark.db
def test_old_requests_do_not_count(conn):
    key = f"k-{uuid.uuid4()}"
    conn.execute(
        "insert into guest_requests (key, ts) select %s, now() - interval '25 hours' from generate_series(1, 10)",
        (key,),
    )
    assert quota_acquire(conn, key, per_day=10, total_per_day=10_000).allowed
