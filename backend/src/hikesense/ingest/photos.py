"""Wikimedia Commons photos for stages and day hikes (panorama background, with attribution).

Quality filter ported from HikeAI `ingest/photo_quality.py` (`title_score`: reject signposts,
memorials, maps, interiors etc. by file title, rank by landscape words). The POI-kind scoring
there is not used: here photos come from geosearch along the route, not from POIs.
"""

from __future__ import annotations

import re
import time
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import unquote

import psycopg

from hikesense import geo
from hikesense.adapters.commons import CommonsClient, ImageInfo
from hikesense.db import delete_stale_commons_photos, upsert_photo, upsert_source
from hikesense.geo import Point
from hikesense.models import Source

MIN_ASPECT = 1.2  # landscape only: the photo is a wide panorama background
LARGE_PX = 1600
STAGE = {"every_km": 3.0, "limit": 8}
DAY_HIKE = {"every_km": 2.0, "limit": 5}
RADIUS_M = 1000
GEOSEARCH_LIMIT = 10
PAUSE_S = 0.3  # between Commons requests: sequential and polite

COMMONS_SOURCE_ID = "commons"
COMMONS_URL = "https://commons.wikimedia.org/"

_REJECT = re.compile(
    r"wegweiser|guidepost|wegtafel|stolperstein|gedenk|memorial|grab\b|grabstein|friedhof|"
    r"\bdop\b|luftbild|aerial|orthophoto|karte|\bmap\b|stadtplan|\bplan\b|logo|wappen|"
    r"innen|interior|orgel|altar|fenster|schild|tafel|haltestelle|parkplatz|rathaus|"
    r"stra(ß|ss)e|hausnummer|postkarte|urkunde|"
    # off topic for hiking: space, street-view series, trains, power lines, cards, documents, …
    r"\biss\d|view_of_earth|mapillary|streetview|bahnhof|vossloh|lokomotive|locomotive|"
    r"freileitung|strommast|unfall|klinik|gemeindeblatt|geblitzt|maestro|\bn26\b|kreditkarte|"
    r"bankkarte|girocard",
    re.IGNORECASE,
)
_LANDSCAPE = re.compile(
    r"blick|aussicht|\bview|panorama|wasserfall|waterfall|schlucht|gorge|klamm|gipfel|summit|"
    r"\bsee\b|lake|weiher|moor|wald|forest|fels|rock|turm|tower|h(ü|u)tte|\bhut\b|\btal\b|valley|"
    r"landschaft|landscape|winter|herbst|autumn|sonnenuntergang|sunset|nebel|wanderweg|pfad|steig",
    re.IGNORECASE,
)


def title_score(title: str) -> int | None:
    """None rejects the photo; otherwise the number of landscape words in the file title."""
    if _REJECT.search(title):
        return None
    return len(_LANDSCAPE.findall(title))


def prune_rejected_photos(conn: psycopg.Connection) -> int:
    """Removes stored Commons photos whose file title the filter now rejects; returns how many.
    Own uploads are never touched. Commits."""
    rows = conn.execute(
        "select id, page_url from photos where source = %s and page_url is not null", [COMMONS_SOURCE_ID]
    ).fetchall()
    ids = [i for i, url in rows if title_score(unquote(url.split("File:")[-1]).replace(" ", "_")) is None]
    if ids:
        conn.execute("delete from photos where id = any(%s)", [ids])
    conn.commit()
    return len(ids)


@dataclass(frozen=True)
class Photo:
    url: str
    thumb_url: str
    page_url: str
    author: str
    license: str
    license_url: str | None = None


def sample_points(line: Sequence[Point], every_km: float) -> list[Point]:
    """Start, then a vertex every `every_km` along the line (end point not forced)."""
    return geo.sample_points([line], step_km=every_km, max_points=10**9, keep_last=False)


def select_photos(
    infos: Sequence[ImageInfo], limit: int, exclude: Collection[str] = ()
) -> list[Photo]:
    """Licensed, attributed, wide (>= 1.2:1), scenic, unique photos; best titles first."""
    seen = set(exclude)
    ranked: list[tuple[int, int, Photo]] = []
    for i in infos:
        score = title_score(i.title)
        if not i.author or not i.license or not i.url or not i.thumb_url or score is None:
            continue
        if i.height <= 0 or i.width / i.height < MIN_ASPECT or i.url in seen:
            continue
        seen.add(i.url)
        photo = Photo(i.url, i.thumb_url, i.page_url, i.author, i.license, i.license_url)
        ranked.append((-score, len(ranked), photo))
    ranked.sort(key=lambda r: r[:2])
    return [p for _, _, p in ranked[:limit]]


def fetch_photos(
    client: CommonsClient,
    line: Sequence[Point],
    *,
    every_km: float,
    limit: int,
    exclude: Collection[str] = (),
    radius_m: int = RADIUS_M,
    pause_s: float = PAUSE_S,
) -> list[Photo]:
    """Geosearch at every sample point, then one batched info call. Raises ImageFetchError."""
    titles: dict[str, None] = {}  # ordered, de-duplicated across sample points
    for lat, lon in sample_points(line, every_km):
        if pause_s:
            time.sleep(pause_s)
        for t in client.geosearch(lat, lon, radius_m, GEOSEARCH_LIMIT):
            if title_score(t) is not None:
                titles[t] = None
    infos: list[ImageInfo] = []
    names = list(titles)
    for k in range(0, len(names), 50):
        if pause_s:
            time.sleep(pause_s)
        infos += client.image_infos(names[k : k + 50], width=400, large_width=LARGE_PX)
    return select_photos(infos, limit, exclude)


@dataclass(frozen=True)
class Target:
    trail_id: str
    stage_id: str | None
    line: list[Point]
    every_km: float
    limit: int


@dataclass
class PhotoReport:
    counts: dict[str, int] = field(default_factory=dict)  # photos per trail
    stage_counts: dict[str, int] = field(default_factory=dict)  # photos per stage
    empty: list[str] = field(default_factory=list)  # trail ids / stage ids without photos


def load_targets(conn: psycopg.Connection) -> list[Target]:
    """Every stage of long-distance trails and every day hike, in stable order."""

    def line(geojson: dict) -> list[Point]:
        return [(lat, lon) for lon, lat in geojson["coordinates"]]

    targets = []
    for sid, tid, gj in conn.execute(
        "select s.id, s.trail_id, st_asgeojson(s.geom)::json from stages s"
        " order by s.trail_id, s.seq"
    ).fetchall():
        targets.append(Target(tid, sid, line(gj), **STAGE))
    for tid, gj in conn.execute(
        "select id, st_asgeojson(geom)::json from trails where kind = 'day_hike' order by id"
    ).fetchall():
        targets.append(Target(tid, None, line(gj), **DAY_HIKE))
    return targets


def import_photos(
    conn: psycopg.Connection,
    client: CommonsClient,
    targets: Sequence[Target],
    *,
    pause_s: float = PAUSE_S,
    on_progress=None,
) -> PhotoReport:
    """Fetch everything first (ImageFetchError aborts with nothing written), then upsert.

    A photo is stored once per trail (unique(trail_id, url)); stages of a trail are processed
    in order, so an earlier stage keeps a photo that also lies near a later one. Photos a
    re-run no longer returns are removed, so the import is idempotent."""
    found: list[tuple[Target, list[Photo]]] = []
    used: dict[str, set[str]] = {}
    for n, t in enumerate(targets, 1):
        seen = used.setdefault(t.trail_id, set())
        photos = fetch_photos(
            client, t.line, every_km=t.every_km, limit=t.limit, exclude=seen, pause_s=pause_s
        )
        seen.update(p.url for p in photos)
        found.append((t, photos))
        if on_progress:
            on_progress(n, len(targets), t, photos)

    upsert_source(
        conn,
        Source(
            id=COMMONS_SOURCE_ID,
            name="Wikimedia Commons",
            url=COMMONS_URL,
            license="per image (stored on the photo row)",
            retrieved_at=date.today(),
        ),
    )
    rep = PhotoReport()
    for t, photos in found:
        for p in photos:
            upsert_photo(
                conn,
                trail_id=t.trail_id,
                stage_id=t.stage_id,
                url=p.url,
                thumb_url=p.thumb_url,
                author=p.author,
                license=p.license,
                license_url=p.license_url,
                page_url=p.page_url,
            )
        rep.counts[t.trail_id] = rep.counts.get(t.trail_id, 0) + len(photos)
        if t.stage_id:
            rep.stage_counts[t.stage_id] = len(photos)
            if not photos:
                rep.empty.append(t.stage_id)
        delete_stale_commons_photos(conn, t.trail_id, t.stage_id, [p.url for p in photos])
    for tid in used:
        if not rep.counts.get(tid):
            rep.empty.append(tid)
    return rep
