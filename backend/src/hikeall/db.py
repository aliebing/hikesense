"""Postgres access helpers."""

from __future__ import annotations

import psycopg

from hikeall.models import Source


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url)


def upsert_source(conn: psycopg.Connection, source: Source) -> None:
    conn.execute(
        """
        insert into sources (id, name, url, license, retrieved_at)
        values (%(id)s, %(name)s, %(url)s, %(license)s, %(retrieved_at)s)
        on conflict (id) do update set
            name = excluded.name,
            url = excluded.url,
            license = excluded.license,
            retrieved_at = excluded.retrieved_at
        """,
        source.model_dump(),
    )
