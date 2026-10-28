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
def test_anon_sees_trail_and_only_public_photos(conn):
    conn.execute("insert into sources (id) values ('rls')")
    conn.execute("insert into trails (id, source_id) values ('rls-t', 'rls')")
    for src in ("commons", "upload"):
        conn.execute(
            "insert into photos (trail_id, source, url, author, license)"
            " values ('rls-t', %s, %s, 'a', 'l')",
            (src, f"http://x/{src}"),
        )
    conn.execute("set role anon")
    assert conn.execute("select count(*) from trails where id='rls-t'").fetchone()[0] == 1
    rows = conn.execute("select source from photos where trail_id='rls-t'").fetchall()
    assert rows == [("commons",)]


@pytest.mark.db
def test_upsert_source_is_idempotent(conn):
    s = Source(id="t", name="n", url="u", license="l", retrieved_at=date(2026, 1, 1))
    db.upsert_source(conn, s)
    db.upsert_source(conn, s.model_copy(update={"name": "n2"}))
    rows = conn.execute("select name from sources where id='t'").fetchall()
    assert rows == [("n2",)]
