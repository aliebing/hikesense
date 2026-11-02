"""Controlled tag vocabulary: every tag has a rule that derives it from data.

Feature and surface tags come from data/tags/features.yaml and are stored per trail
(`trail_tags`). Place tags (from `places`) and area tags are checked spatially at query time.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Annotated, Literal

import psycopg
import yaml
from pydantic import BaseModel, Field

from hikeall.config import data_root
from hikeall.models import BBox
from hikeall.regions import REGIONS

FEATURES_YAML = data_root() / "tags" / "features.yaml"

TagCategory = Literal["feature", "surface", "place", "area", "trail"]
# municipality last: same-name collisions keep the existing bare ids of towns, peaks and lakes
PLACE_KINDS = ("town", "village", "peak", "lake", "municipality")
PLACE_RADIUS_KM = 15.0
STORED_CATEGORIES = ("feature", "surface")

# Latitude bands from HikeAI data/regions.yaml (boundaries 48.30 and 47.95).
_BF = (7.55, 8.80)  # = BLACK_FOREST_BBOX west/east
AREAS = (
    ("area:nord", "Nordschwarzwald", ["Nordschwarzwald", "Nord", "Norden"], 48.30, 48.95),
    (
        "area:mitte",
        "Mittelschwarzwald",
        ["Mittelschwarzwald", "Mitte", "Mittlerer Schwarzwald"],
        47.95,
        48.30,
    ),
    (
        "area:sued",
        "Südschwarzwald",
        ["Südschwarzwald", "Süden", "Südlicher Schwarzwald"],
        47.55,
        47.95,
    ),
)


class PoiNear(BaseModel):
    type: Literal["poi_near"] = "poi_near"
    kinds: list[str] = Field(min_length=1)
    within_m: int = Field(gt=0)


class ShareAtLeast(BaseModel):
    type: Literal["share_at_least"] = "share_at_least"
    field: Literal["surface", "way_type"]
    keys: list[str] = Field(min_length=1)
    share: float = Field(ge=0, le=1)


class ShareAtMost(BaseModel):
    type: Literal["share_at_most"] = "share_at_most"
    field: Literal["surface", "way_type"]
    keys: list[str] = Field(min_length=1)
    share: float = Field(ge=0, le=1)


class Attribute(BaseModel):
    type: Literal["attribute"] = "attribute"
    roundtrip: bool


class NearPlace(BaseModel):
    type: Literal["near_place"] = "near_place"
    place_id: int
    radius_km: float = Field(gt=0)
    lat: float | None = None
    lon: float | None = None
    kind: str | None = None


class Area(BaseModel):
    type: Literal["area"] = "area"
    bbox: BBox


class LongTrail(BaseModel):
    """A long-distance trail (trails.id); resolved by name, never checked spatially."""

    type: Literal["trail"] = "trail"
    trail_id: str = Field(min_length=1)


TagRule = Annotated[
    PoiNear | ShareAtLeast | ShareAtMost | Attribute | NearPlace | Area | LongTrail,
    Field(discriminator="type"),
]


class Tag(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+:[a-z0-9_\-]+$")
    label: str = Field(min_length=1)
    category: TagCategory
    synonyms: list[str] = Field(default_factory=list)
    rule: TagRule


_FOLD_TABLE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "œ": "oe", "æ": "ae"})
_NON_WORD = re.compile(r"[^\w\s]")


def fold(text: str) -> str:
    """Casefold, transliterate umlauts (ä→ae), strip other accents, punctuation to spaces."""
    text = text.casefold().translate(_FOLD_TABLE)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(_NON_WORD.sub(" ", text.replace("_", " ")).split())


def slugify(text: str) -> str:
    return fold(text).replace(" ", "-").encode("ascii", "ignore").decode("ascii")


class TagVocabulary:
    def __init__(self, tags: list[Tag]):
        self._tags: dict[str, Tag] = {}
        for tag in tags:
            if tag.id in self._tags:
                raise ValueError(f"duplicate tag id: {tag.id}")
            self._tags[tag.id] = tag
        self._terms = {
            t.id: sorted({f for term in [t.label, *t.synonyms] if (f := fold(term))}) for t in tags
        }

    @classmethod
    def from_features(cls, features_path: Path) -> TagVocabulary:
        """Feature/surface tags from YAML plus the three area tags (no database needed)."""
        raw = yaml.safe_load(features_path.read_text(encoding="utf-8")) or []
        tags = [Tag.model_validate(item) for item in raw]
        return cls(tags + _area_tags() + _trail_tags())

    @classmethod
    def load(cls, conn: psycopg.Connection, features_path: Path) -> TagVocabulary:
        base = cls.from_features(features_path)
        return cls(base.all() + _place_tags(conn))

    def __len__(self) -> int:
        return len(self._tags)

    def __contains__(self, tag_id: object) -> bool:
        return tag_id in self._tags

    def get(self, tag_id: str) -> Tag | None:
        return self._tags.get(tag_id)

    def all(self) -> list[Tag]:
        return list(self._tags.values())

    def search(self, text: str, limit: int = 20) -> list[Tag]:
        """Folded match against labels and synonyms; exact, then prefix, then inner matches."""
        needle = fold(text)
        if not needle:
            return []
        exact, prefix, inner = [], [], []
        for t in self._tags.values():
            terms = self._terms[t.id]
            if needle in terms:
                exact.append(t)
            elif any(x.startswith(needle) for x in terms):
                prefix.append(t)
            elif any(needle in x for x in terms):
                inner.append(t)
        return (exact + prefix + inner)[:limit]


# Region-wide area tags: id, extra synonyms (the label is searched anyway)
_REGION_AREAS = {
    "black_forest": ("area:schwarzwald", []),
    "palatinate": ("area:pfaelzerwald", ["Pfälzer Wald", "Pfalz"]),
    "lake_constance": ("area:bodensee", ["am Bodensee", "Schwäbisches Meer"]),
}
REGION_LABELS = frozenset(fold(r.name) for r in REGIONS)


def _area_tags() -> list[Tag]:
    regions = [
        Tag(
            id=_REGION_AREAS[r.id][0],
            label=r.name,
            category="area",
            synonyms=_REGION_AREAS[r.id][1],
            rule=Area(bbox=r.bbox),
        )
        for r in REGIONS
    ]
    return regions + [
        Tag(
            id=tid,
            label=label,
            category="area",
            synonyms=syn,
            rule=Area(bbox=BBox(south=south, west=_BF[0], north=north, east=_BF[1])),
        )
        for tid, label, syn, south, north in AREAS
    ]


# "Westweg" alone is the west variant (understand says so in the echo)
TRAILS = (
    (
        "trail:westweg-west",
        "Westweg",
        ["Westweg Westvariante", "Westweg West", "Westweg West Variante"],
        "westweg-west",
    ),
    (
        "trail:westweg-ost",
        "Westweg Ostvariante",
        ["Westweg Ost", "Westweg Ost Variante"],
        "westweg-ost",
    ),
    ("trail:mittelweg", "Mittelweg", [], "mittelweg"),
    ("trail:ostweg", "Ostweg", [], "ostweg"),
    (
        "trail:pfaelzer-weinsteig",
        "Pfälzer Weinsteig",
        ["Weinsteig"],
        "pfaelzer-weinsteig",
    ),
    (
        "trail:pfaelzer-waldpfad",
        "Pfälzer Waldpfad",
        ["Waldpfad"],
        "pfaelzer-waldpfad",
    ),
    (
        "trail:jubilaeumsweg-bodenseekreis",
        "Jubiläumsweg Bodenseekreis",
        ["Jubiläumsweg", "Bodensee Jubiläumsweg"],
        "jubilaeumsweg-bodenseekreis",
    ),
    (
        "trail:seegang",
        "Premiumweg SeeGang",
        ["SeeGang", "Premiumweg Seegang"],
        "seegang",
    ),
)


def _trail_tags() -> list[Tag]:
    return [
        Tag(id=tid, label=label, category="trail", synonyms=syn, rule=LongTrail(trail_id=trail_id))
        for tid, label, syn, trail_id in TRAILS
    ]


def _place_tags(conn: psycopg.Connection) -> list[Tag]:
    rows = conn.execute(
        """
        select id, name, kind, st_y(geom), st_x(geom) from places
        where kind = any(%s)
        order by array_position(%s::text[], kind), id
        """,
        (list(PLACE_KINDS), list(PLACE_KINDS)),
    ).fetchall()
    tags: list[Tag] = []
    used: set[str] = set()
    for pid, name, kind, lat, lon in rows:
        slug = slugify(name)
        if not slug or fold(name) in REGION_LABELS:  # the area wins over a place of that name
            continue
        tid = f"place:{slug}"
        if tid in used:  # same name twice (e.g. Feldberg peak and town): keep both, id-suffixed
            tid = f"place:{slug}-{_osm_ref(pid)}"
        used.add(tid)
        tags.append(
            Tag(
                id=tid,
                label=name,
                category="place",
                rule=NearPlace(
                    place_id=pid, radius_km=PLACE_RADIUS_KM, lat=lat, lon=lon, kind=kind
                ),
            )
        )
    return tags


def _osm_ref(pid: int) -> str:
    """Unambiguous OSM reference from the signed id scheme: n<node>, w<way>, r<relation>."""
    if pid > 0:
        return f"n{pid}"
    if -pid >= 10**12:
        return f"r{-pid - 10**12}"
    return f"w{-pid}"


MAX_UNKNOWN_SHARE = 0.5  # more unknown than this: the share says nothing, no tag


def _share(shares: dict | None, keys: list[str]) -> float | None:
    if shares is None:
        return None
    return round(sum(float(shares.get(k, 0)) for k in keys), 3)


def compute_trail_tags(conn: psycopg.Connection, vocab: TagVocabulary) -> int:
    """Rewrite `trail_tags` (feature and surface tags only); returns the number of rows.

    A tag whose data is missing (shares or roundtrip null) or mostly unknown (> 50 % of a
    share field) is never granted.
    """
    trails = conn.execute(
        "select id, roundtrip, surface_shares, way_type_shares from trails"
    ).fetchall()
    poi_kinds: dict[str, dict[str, int]] = {}  # trail -> kind -> min dist_m
    for tid, kind, dist in conn.execute(
        """
        select tp.trail_id, p.kind, min(tp.dist_m)
        from trail_pois tp join pois p on p.id = tp.poi_id
        group by tp.trail_id, p.kind
        """
    ):
        poi_kinds.setdefault(tid, {})[kind] = dist if dist is not None else 10**9
    rows: list[tuple[str, str]] = []
    for trail_id, roundtrip, surface, way_type in trails:
        shares = {"surface": surface, "way_type": way_type}
        for tag in vocab.all():
            if tag.category not in STORED_CATEGORIES:
                continue
            rule = tag.rule
            ok = False
            if isinstance(rule, PoiNear):
                near = poi_kinds.get(trail_id, {})
                ok = any(near.get(k, 10**9) <= rule.within_m for k in rule.kinds)
            elif isinstance(rule, Attribute):
                ok = roundtrip is not None and roundtrip == rule.roundtrip
            elif isinstance(rule, (ShareAtLeast, ShareAtMost)):
                data = shares[rule.field]
                value = _share(data, rule.keys)
                if value is not None and _share(data, ["unknown"]) <= MAX_UNKNOWN_SHARE:
                    ok = (
                        value >= rule.share
                        if isinstance(rule, ShareAtLeast)
                        else value <= rule.share
                    )
            if ok:
                rows.append((trail_id, tag.id))
    conn.execute("delete from trail_tags")
    with conn.cursor() as cur:
        cur.executemany("insert into trail_tags (trail_id, tag_id) values (%s, %s)", rows)
    return len(rows)
