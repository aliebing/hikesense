import os

import psycopg
import pytest

DEFAULT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


@pytest.fixture
def conn():
    url = os.environ.get("SUPABASE_DB_URL", DEFAULT_URL)
    try:
        c = psycopg.connect(url, connect_timeout=3)
    except psycopg.OperationalError as e:
        pytest.skip(f"database not reachable: {e}")
    try:
        yield c
    finally:
        c.rollback()
        c.close()


# Shared geometry/fakes for ingest tests.
LINE = [(48.0, 8.0 + i * 0.001) for i in range(101)]  # ~7.4 km straight line
# An L: 0.05 deg north (~5.56 km), then 0.075 deg east (~5.58 km at 48.05 N). In degrees the
# north leg is only 40 % of the line, on the ground it is 50 %: km positions along a trail must
# come from metres, not from degree fractions.
L_LINE = [(48.0 + i * 0.001, 8.0) for i in range(51)] + [
    (48.05, 8.0 + i * 0.001) for i in range(1, 76)
]
L_LEN_KM = 11.14
L_CORNER_KM = 5.56  # the corner (48.05, 8.0)


class Ramp:
    """Fake elevation provider: rises 1 m per 10 m along LINE (takes LatLon points)."""

    def elevations(self, pts):
        return [(p.lon - 8.0) * 7400 for p in pts]


def upsert_l_trail(conn, trail_id: str, source_id: str) -> None:
    """The L_LINE as a long-distance trail (the source must exist)."""
    from hikeall.db import upsert_trail

    upsert_trail(
        conn, id=trail_id, name="L", kind="long_distance", region="black_forest", roundtrip=False, osm_relation_id=None,
        length_km=L_LEN_KM, ascent_m=0, descent_m=0, profile=[(0.0, 500.0)], line=L_LINE,
        source_id=source_id,
    )  # fmt: skip
