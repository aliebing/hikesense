from datetime import date

import pytest

from hikeall import db
from hikeall.models import Source


@pytest.mark.db
def test_schema_has_tables_and_postgis(conn):
    names = {
        r[0]
        for r in conn.execute(
            "select table_name from information_schema.tables where table_schema='public'"
        )
    }
    assert {"sources", "trails", "stages", "lodgings", "trail_lodgings", "photos"} <= names
    assert conn.execute("select postgis_version()").fetchone()[0]


@pytest.mark.db
def test_anon_can_read_trails(conn):
    conn.execute("set role anon")
    conn.execute("select count(*) from trails")  # must not raise


@pytest.mark.db
def test_upsert_source_is_idempotent(conn):
    s = Source(id="t", name="n", url="u", license="l", retrieved_at=date(2026, 1, 1))
    db.upsert_source(conn, s)
    db.upsert_source(conn, s.model_copy(update={"name": "n2"}))
    rows = conn.execute("select name from sources where id='t'").fetchall()
    assert rows == [("n2",)]
