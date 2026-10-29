"""Postgres access helpers."""

from __future__ import annotations

from collections.abc import Sequence

import psycopg
from psycopg.types.json import Jsonb

from hikeall.models import Lodging, Place, Poi, Source


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


def _wkt(line: Sequence[tuple[float, float]]) -> str:
    """(lat, lon) points → WKT LineString in lon/lat order."""
    return "LINESTRING(" + ",".join(f"{lon} {lat}" for lat, lon in line) + ")"


def upsert_trail(
    conn: psycopg.Connection,
    *,
    id: str,
    name: str,
    kind: str,
    roundtrip: bool,
    osm_relation_id: int | None,
    length_km: float,
    ascent_m: int,
    descent_m: int,
    profile: list[tuple[float, float]],
    line: Sequence[tuple[float, float]],
    source_id: str,
    surface_shares: dict | None = None,
    way_type_shares: dict | None = None,
) -> None:
    """Upsert a trail. Shares left at None keep whatever is stored."""
    conn.execute(
        """
        insert into trails (id, name, kind, roundtrip, osm_relation_id, length_km, ascent_m,
                            descent_m, profile, geom, source_id, surface_shares, way_type_shares)
        values (%(id)s, %(name)s, %(kind)s, %(roundtrip)s, %(rel)s, %(len)s, %(asc)s, %(desc)s,
                %(profile)s, st_geomfromtext(%(wkt)s, 4326), %(src)s, %(surf)s, %(wayt)s)
        on conflict (id) do update set
            name = excluded.name, kind = excluded.kind, roundtrip = excluded.roundtrip,
            osm_relation_id = excluded.osm_relation_id, length_km = excluded.length_km,
            ascent_m = excluded.ascent_m, descent_m = excluded.descent_m,
            profile = excluded.profile, geom = excluded.geom, source_id = excluded.source_id,
            surface_shares = coalesce(excluded.surface_shares, trails.surface_shares),
            way_type_shares = coalesce(excluded.way_type_shares, trails.way_type_shares)
        """,
        {
            "surf": Jsonb(surface_shares) if surface_shares is not None else None,
            "wayt": Jsonb(way_type_shares) if way_type_shares is not None else None,
            "id": id,
            "name": name,
            "kind": kind,
            "roundtrip": roundtrip,
            "rel": osm_relation_id,
            "len": length_km,
            "asc": ascent_m,
            "desc": descent_m,
            "profile": Jsonb(profile),
            "wkt": _wkt(line),
            "src": source_id,
        },
    )


def upsert_stage(
    conn: psycopg.Connection,
    *,
    id: str,
    trail_id: str,
    seq: int,
    name: str,
    start_name: str,
    end_name: str,
    length_km: float,
    ascent_m: int,
    descent_m: int,
    profile: list[tuple[float, float]],
    line: Sequence[tuple[float, float]],
    source_id: str,
) -> None:
    conn.execute(
        """
        insert into stages (id, trail_id, seq, name, start_name, end_name, length_km,
                            ascent_m, descent_m, profile, geom, source_id)
        values (%(id)s, %(trail)s, %(seq)s, %(name)s, %(start)s, %(end)s, %(len)s, %(asc)s,
                %(desc)s, %(profile)s, st_geomfromtext(%(wkt)s, 4326), %(src)s)
        on conflict (id) do update set
            trail_id = excluded.trail_id, seq = excluded.seq, name = excluded.name,
            start_name = excluded.start_name, end_name = excluded.end_name,
            length_km = excluded.length_km, ascent_m = excluded.ascent_m,
            descent_m = excluded.descent_m, profile = excluded.profile, geom = excluded.geom,
            source_id = excluded.source_id
        """,
        {
            "id": id,
            "trail": trail_id,
            "seq": seq,
            "name": name,
            "start": start_name,
            "end": end_name,
            "len": length_km,
            "asc": ascent_m,
            "desc": descent_m,
            "profile": Jsonb(profile),
            "wkt": _wkt(line),
            "src": source_id,
        },
    )


def delete_stages_after(conn: psycopg.Connection, trail_id: str, last_seq: int) -> None:
    """Remove stages beyond `last_seq`, so a shortened stage list leaves nothing behind."""
    conn.execute("delete from stages where trail_id = %s and seq > %s", [trail_id, last_seq])


def delete_day_hike(conn: psycopg.Connection, trail_id: str) -> bool:
    """Remove a day hike, its lodging links and its Commons photos; True if a
    trail was deleted.

    Long-distance trails (with stages) are never touched here. Own uploads
    (non-Commons photos) are user data: they are kept, so the trail delete
    fails loudly on the photos FK instead of silently dropping them."""
    is_day_hike = " and exists (select 1 from trails where id = %s and kind = 'day_hike')"
    conn.execute(
        "delete from photos where trail_id = %s and source = 'commons'" + is_day_hike,
        [trail_id, trail_id],
    )
    conn.execute(
        "delete from trail_lodgings where trail_id = %s" + is_day_hike,
        [trail_id, trail_id],
    )
    conn.execute(
        "delete from trail_pois where trail_id = %s" + is_day_hike,
        [trail_id, trail_id],
    )
    cur = conn.execute("delete from trails where id = %s and kind = 'day_hike'", [trail_id])
    return cur.rowcount > 0


def upsert_lodging(conn: psycopg.Connection, lodging: Lodging, source_id: str) -> None:
    conn.execute(
        """
        insert into lodgings (id, name, kind, website, geom, source_id)
        values (%(id)s, %(name)s, %(kind)s, %(website)s,
                st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326), %(src)s)
        on conflict (id) do update set
            name = excluded.name, kind = excluded.kind, website = excluded.website,
            geom = excluded.geom, source_id = excluded.source_id
        """,
        {**lodging.model_dump(), "src": source_id},
    )


def upsert_place(conn: psycopg.Connection, place: Place, source_id: str) -> None:
    conn.execute(
        """
        insert into places (id, name, kind, geom, source_id)
        values (%(id)s, %(name)s, %(kind)s,
                st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326), %(src)s)
        on conflict (id) do update set
            name = excluded.name, kind = excluded.kind,
            geom = excluded.geom, source_id = excluded.source_id
        """,
        {**place.model_dump(), "src": source_id},
    )


def upsert_poi(conn: psycopg.Connection, poi: Poi, source_id: str) -> None:
    conn.execute(
        """
        insert into pois (id, name, kind, geom, source_id)
        values (%(id)s, %(name)s, %(kind)s,
                st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326), %(src)s)
        on conflict (id) do update set
            name = excluded.name, kind = excluded.kind,
            geom = excluded.geom, source_id = excluded.source_id
        """,
        {**poi.model_dump(), "src": source_id},
    )


def upsert_photo(
    conn: psycopg.Connection,
    *,
    trail_id: str,
    stage_id: str | None,
    url: str,
    thumb_url: str,
    author: str,
    license: str,
    license_url: str | None,
    page_url: str,
) -> None:
    """Commons photo, keyed by unique(trail_id, url); author and licence are mandatory."""
    if not author or not license:
        raise ValueError(f"photo {url}: author and license are required")
    conn.execute(
        """
        insert into photos (trail_id, stage_id, source, url, thumb_url, author, license,
                            license_url, page_url)
        values (%(trail)s, %(stage)s, 'commons', %(url)s, %(thumb)s, %(author)s, %(license)s,
                %(license_url)s, %(page)s)
        on conflict (trail_id, url) do update set
            stage_id = excluded.stage_id, thumb_url = excluded.thumb_url,
            author = excluded.author, license = excluded.license,
            license_url = excluded.license_url, page_url = excluded.page_url
        """,
        {
            "trail": trail_id,
            "stage": stage_id,
            "url": url,
            "thumb": thumb_url,
            "author": author,
            "license": license,
            "license_url": license_url,
            "page": page_url,
        },
    )


def delete_stale_commons_photos(
    conn: psycopg.Connection, trail_id: str, stage_id: str | None, keep_urls: Sequence[str]
) -> int:
    """Drop Commons photos of one stage (or of a day hike, stage_id None) that a fresh import
    no longer returns; other stages of the trail are left alone."""
    cur = conn.execute(
        "delete from photos where trail_id = %s and stage_id is not distinct from %s"
        " and source = 'commons' and url <> all(%s)",
        [trail_id, stage_id, list(keep_urls)],
    )
    return cur.rowcount
