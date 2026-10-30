"""Groups: the hand-curated CSV (data/curated/groups.csv) into the `groups` table.

Only name, kind, place, link, source and check date – no persons, no dates or events (spec §3
exception). `import_groups` validates every row first; one bad row imports nothing.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import psycopg

from hikeall.errors import HikeAllError
from hikeall.models import BLACK_FOREST_BBOX

KINDS = ("wanderverein", "lauftreff", "alpenverein", "sonstige")
STATUSES = ("vorschlag", "geprüft")


class GroupsError(HikeAllError):
    """A groups row is incomplete or invalid."""


@dataclass
class GroupRow:
    id: str
    name: str
    kind: str
    place: str
    lat: float
    lon: float
    url: str
    source_url: str
    checked_at: date
    status: str
    note: str = ""


COLUMNS = [f.name for f in fields(GroupRow)]  # CSV header, in this order


def _is_http(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.netloc)


def parse_row(raw: dict[str, str], line: int) -> GroupRow:
    """One CSV record -> GroupRow; GroupsError names the line and the problem."""

    def bad(msg: str) -> GroupsError:
        return GroupsError(f"Zeile {line}: {msg}")

    r = {k: (v or "").strip() for k, v in raw.items() if k}
    for col in ("id", "name", "kind", "place", "lat", "lon", "url", "source_url", "checked_at"):
        if not r.get(col):
            raise bad(f"Pflichtfeld „{col}“ fehlt")
    if r["kind"] not in KINDS:
        raise bad(f"unbekannte Art „{r['kind']}“ (erlaubt: {', '.join(KINDS)})")
    status = r.get("status") or "vorschlag"
    if status not in STATUSES:
        raise bad(f"unbekannter Status „{status}“ (erlaubt: {', '.join(STATUSES)})")
    for col in ("url", "source_url"):
        if not _is_http(r[col]):
            raise bad(f"„{col}“ ist keine http(s)-Adresse")
    try:
        lat, lon = float(r["lat"]), float(r["lon"])
        checked = date.fromisoformat(r["checked_at"])
    except ValueError as e:
        raise bad(f"ungültiger Wert ({e})") from e
    box = BLACK_FOREST_BBOX
    if not (box.south <= lat <= box.north and box.west <= lon <= box.east):
        raise bad("Koordinate liegt außerhalb des Schwarzwalds")
    return GroupRow(
        id=r["id"], name=r["name"], kind=r["kind"], place=r["place"], lat=lat, lon=lon,
        url=r["url"], source_url=r["source_url"], checked_at=checked, status=status,
        note=r.get("note", ""),
    )  # fmt: skip


def read_groups(path: Path) -> list[GroupRow]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [parse_row(rec, i) for i, rec in enumerate(csv.DictReader(f), start=2)]
    ids = [r.id for r in rows]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise GroupsError(f"doppelte id: {', '.join(dup)}")
    return rows


def import_groups(conn: psycopg.Connection, rows: list[GroupRow]) -> int:
    """Upsert all rows and drop table rows that left the CSV; returns the number of rows."""
    if not rows:
        raise GroupsError("keine Gruppen zum Importieren")
    for row in rows:  # re-validate: rows can come from code, not only from read_groups
        parse_row({k: str(v) for k, v in vars(row).items()}, 0)
    for r in rows:
        conn.execute(
            """
            insert into groups (id, name, kind, place, geom, url, source_url, checked_at,
                                status, note)
            values (%(id)s, %(name)s, %(kind)s, %(place)s,
                    st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326),
                    %(url)s, %(source_url)s, %(checked_at)s, %(status)s, %(note)s)
            on conflict (id) do update set
                name = excluded.name, kind = excluded.kind, place = excluded.place,
                geom = excluded.geom, url = excluded.url, source_url = excluded.source_url,
                checked_at = excluded.checked_at, status = excluded.status, note = excluded.note
            """,
            vars(r) | {"note": r.note or None},
        )
    conn.execute("delete from groups where not (id = any(%s))", ([r.id for r in rows],))
    return len(rows)
