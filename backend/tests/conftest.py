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
