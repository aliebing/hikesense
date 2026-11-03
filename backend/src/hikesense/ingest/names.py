"""Display names for day hikes whose OSM name is only a sign number.

Local networks name their routes after the sign ("Rundweg A1", "Rundwanderweg 4"): useful on
site, meaningless in a list, and "Rundwanderweg 4" exists eight times. Such a name gets the
village or town nearest to the trail's start: "Rundweg A1 (Ahausen)".
"""

import re

import psycopg

# A route word and a sign number (optionally one or two letters before it), nothing else.
NUMBERED = re.compile(
    r"^(rundweg|rundwanderweg|wanderweg|weg|runde|tour)\s*[a-z]{0,2}\s*\d+[a-z]?$", re.IGNORECASE
)
PLACE_KINDS = ("city", "town", "village")
MAX_PLACE_KM = 5.0


def is_numbered_name(name: str | None) -> bool:
    return bool(name) and NUMBERED.match(name.strip()) is not None


def name_numbered_trails(conn: psycopg.Connection) -> int:
    """Append the nearest village/town (within 5 km of the start) to numbered day-hike names.
    Idempotent: a named trail no longer matches. Returns the number of renamed trails."""
    rows = conn.execute(
        "select id, name from trails where kind = 'day_hike' and geom is not null"
    ).fetchall()
    renamed = 0
    for trail_id, name in rows:
        if not is_numbered_name(name):
            continue
        place = conn.execute(
            """
            select pl.name from trails t,
              lateral (select name, geom from places where kind = any(%(kinds)s)
                       order by geom <-> st_startpoint(t.geom) limit 1) pl
            where t.id = %(id)s
              and st_dwithin(pl.geom::geography, st_startpoint(t.geom)::geography, %(m)s)
            """,
            {"id": trail_id, "kinds": list(PLACE_KINDS), "m": MAX_PLACE_KM * 1000},
        ).fetchone()
        if place:
            conn.execute(
                "update trails set name = %s where id = %s",
                (f"{name.strip()} ({place[0]})", trail_id),
            )
            renamed += 1
    return renamed
