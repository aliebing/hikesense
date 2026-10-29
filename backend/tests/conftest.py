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


class Ramp:
    """Fake elevation provider: rises 1 m per 10 m along LINE (takes LatLon points)."""

    def elevations(self, pts):
        return [(p.lon - 8.0) * 7400 for p in pts]
