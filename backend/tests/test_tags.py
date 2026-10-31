from pathlib import Path

import pytest
from conftest import LINE

from hikeall.db import upsert_source, upsert_trail
from hikeall.models import Source
from hikeall.tags.vocabulary import (
    FEATURES_YAML,
    Area,
    NearPlace,
    PoiNear,
    ShareAtMost,
    Tag,
    TagVocabulary,
    compute_trail_tags,
    fold,
)

FEATURE_IDS = {
    "feature:aussicht",
    "feature:gipfel",
    "feature:wasserfall",
    "feature:einkehr",
    "feature:bahnhof",
    "feature:rundweg",
    "surface:wenig_asphalt",
    "surface:naturweg",
    "surface:gut_laufbar",
}


def feature_vocab() -> TagVocabulary:
    return TagVocabulary.from_features(FEATURES_YAML)


@pytest.fixture
def vocab():
    return feature_vocab()


def test_features_yaml_loads_and_ids_unique(vocab):
    ids = [t.id for t in vocab.all() if t.category in ("feature", "surface")]
    assert set(ids) == FEATURE_IDS and len(ids) == len(set(ids))
    assert isinstance(vocab.get("feature:aussicht").rule, PoiNear)
    assert vocab.get("feature:aussicht").rule.within_m == 300
    assert isinstance(vocab.get("surface:wenig_asphalt").rule, ShareAtMost)
    assert "feature:aussicht" in vocab and "feature:nope" not in vocab


def test_duplicate_ids_rejected(tmp_path: Path):
    p = tmp_path / "f.yaml"
    entry = (
        '- {id: "feature:x", label: X, category: feature, '
        "rule: {type: attribute, roundtrip: true}}\n"
    )
    p.write_text(entry * 2)
    with pytest.raises(ValueError, match="feature:x"):
        TagVocabulary.from_features(p)


def test_fold():
    assert fold("Schönwald-Ürzig ß") == "schoenwald uerzig ss"


def test_search_folds_umlauts(vocab):
    assert vocab.search("aussicht")[0].id == "feature:aussicht"
    assert vocab.search("Ausblick")[0].id == "feature:aussicht"
    assert vocab.search("Suedschwarzwald")[0].id == "area:sued"
    assert vocab.search("Südschwarzwald")[0].id == "area:sued"
    assert vocab.search("") == []
    assert len(vocab.search("a", limit=2)) == 2


def test_area_bands(vocab):
    nord, mitte, sued = (vocab.get(f"area:{n}") for n in ("nord", "mitte", "sued"))
    assert all(isinstance(t.rule, Area) for t in (nord, mitte, sued))
    assert nord.rule.bbox.south == 48.30 and sued.rule.bbox.north == 47.95
    assert nord.category == "area"


SRC = Source(
    id="test-tags-src",
    name="t",
    url="https://example.org",
    license="ODbL",
    retrieved_at="2026-10-29",
)


def _trail(conn, tid, **kw):
    upsert_trail(
        conn,
        id=tid,
        name=tid,
        kind="day_hike",
        roundtrip=kw.get("roundtrip"),
        osm_relation_id=None,
        length_km=7.0,
        ascent_m=100,
        descent_m=100,
        profile=[[0, 0], [7, 100]],
        line=LINE,
        source_id=SRC.id,
    )


def _shares(conn, tid, surface, way_type):
    from psycopg.types.json import Jsonb

    conn.execute(
        "update trails set surface_shares=%s, way_type_shares=%s where id=%s",
        (
            None if surface is None else Jsonb(surface),
            None if way_type is None else Jsonb(way_type),
            tid,
        ),
    )


def _tags(conn, tid):
    return {r[0] for r in conn.execute("select tag_id from trail_tags where trail_id=%s", (tid,))}


@pytest.mark.db
def test_share_tag_not_given_without_shares(conn):
    upsert_source(conn, SRC)
    _trail(conn, "test-tags-null")
    _shares(conn, "test-tags-null", None, None)
    compute_trail_tags(conn, feature_vocab())
    assert not {t for t in _tags(conn, "test-tags-null") if t.startswith("surface:")}


@pytest.mark.db
def test_share_tags_from_shares(conn):
    upsert_source(conn, SRC)
    _trail(conn, "test-tags-shares", roundtrip=True)
    _shares(
        conn,
        "test-tags-shares",
        {"paved": 0.1, "gravel": 0.5, "unknown": 0.5},
        {"path": 0.45, "track": 0.55},
    )
    n = compute_trail_tags(conn, feature_vocab())
    assert n >= 4
    assert _tags(conn, "test-tags-shares") == {
        "surface:wenig_asphalt",
        "surface:naturweg",
        "surface:gut_laufbar",
        "feature:rundweg",
    }
    _shares(conn, "test-tags-shares", {"paved": 0.4, "gravel": 0.1}, {"path": 0.1})
    compute_trail_tags(conn, feature_vocab())
    assert _tags(conn, "test-tags-shares") == {"feature:rundweg"}


@pytest.mark.db
def test_mostly_unknown_shares_grant_no_tag(conn):
    upsert_source(conn, SRC)
    _trail(conn, "test-tags-unk")
    _shares(conn, "test-tags-unk", {"unknown": 0.9, "paved": 0.1}, {"unknown": 0.6, "path": 0.4})
    compute_trail_tags(conn, feature_vocab())
    assert _tags(conn, "test-tags-unk") == set()
    # unknown exactly 0.5 is still allowed (wenig_asphalt, naturweg)
    _shares(conn, "test-tags-unk", {"unknown": 0.5, "paved": 0.1}, {"unknown": 0.5, "path": 0.5})
    compute_trail_tags(conn, feature_vocab())
    assert _tags(conn, "test-tags-unk") == {"surface:wenig_asphalt", "surface:naturweg"}


@pytest.mark.db
def test_poi_tag_given_within_300m(conn):
    upsert_source(conn, SRC)
    _trail(conn, "test-tags-poi", roundtrip=False)
    for pid, kind in ((-9_000_001, "viewpoint"), (-9_000_002, "waterfall")):
        conn.execute(
            "insert into pois (id, name, kind, geom, source_id) "
            "values (%s, 'x', %s, st_setsrid(st_makepoint(8.0, 48.0), 4326), %s)",
            (pid, kind, SRC.id),
        )
    conn.execute(
        "insert into trail_pois (trail_id, poi_id, dist_m, along_km) values "
        "('test-tags-poi', -9000001, 120, 1.0), ('test-tags-poi', -9000002, 280, 2.0)"
    )
    compute_trail_tags(conn, feature_vocab())
    assert _tags(conn, "test-tags-poi") == {"feature:aussicht", "feature:wasserfall"}


@pytest.mark.db
def test_load_adds_places_and_areas(conn):
    upsert_source(conn, SRC)
    for pid, name, kind in (
        (-9_000_011, "Zzzortstadt", "town"),
        (-9_000_012, "Zzzhamlet", "hamlet"),
    ):
        conn.execute(
            "insert into places (id, name, kind, geom, source_id) "
            "values (%s, %s, %s, st_setsrid(st_makepoint(8.0, 48.0), 4326), %s)",
            (pid, name, kind, SRC.id),
        )
    v = TagVocabulary.load(conn, FEATURES_YAML)
    tag = v.get("place:zzzortstadt")
    assert tag is not None and tag.category == "place"
    assert isinstance(tag.rule, NearPlace) and tag.rule.place_id == -9_000_011
    assert v.get("place:zzzhamlet") is None  # hamlets are not tags
    assert v.search("zzzortstadt")[0].id == "place:zzzortstadt"
    assert isinstance(v.get("area:mitte").rule, Area)


@pytest.mark.db
def test_place_tags_carry_coordinates(conn):
    upsert_source(conn, SRC)
    conn.execute(
        "insert into places (id, name, kind, geom, source_id) "
        "values (-9000031, 'Zzzkoord', 'town', st_setsrid(st_makepoint(8.25, 47.75), 4326), %s)",
        (SRC.id,),
    )
    rule = TagVocabulary.load(conn, FEATURES_YAML).get("place:zzzkoord").rule
    assert (rule.lat, rule.lon) == (pytest.approx(47.75), pytest.approx(8.25))
    assert rule.kind == "town"


@pytest.mark.db
def test_duplicate_place_names_get_unambiguous_ids(conn):
    upsert_source(conn, SRC)
    for pid, kind in ((-9_000_021, "town"), (9_000_022, "peak"), (-(10**12 + 9_000_023), "lake")):
        conn.execute(
            "insert into places (id, name, kind, geom, source_id) "
            "values (%s, 'Zzzdup', %s, st_setsrid(st_makepoint(8.0, 48.0), 4326), %s)",
            (pid, kind, SRC.id),
        )
    v = TagVocabulary.load(conn, FEATURES_YAML)
    assert v.get("place:zzzdup").rule.place_id == -9_000_021  # town ranks first
    assert v.get("place:zzzdup-n9000022").rule.place_id == 9_000_022
    assert v.get("place:zzzdup-r9000023").rule.place_id == -(10**12 + 9_000_023)
    assert isinstance(v.get("place:zzzdup-r9000023"), Tag)


def test_search_exact_match_ranks_first(vocab):
    assert vocab.search("Gipfel")[0].id == "feature:gipfel"
    assert vocab.search("Bahn")[0].id == "feature:bahnhof"  # synonym "Bahn" beats prefix "Bahnhof"


def test_trail_tags_cover_all_long_distance_trails(vocab):
    ids = {t.rule.trail_id for t in vocab.all() if t.category == "trail"}
    assert ids == {"westweg-west", "westweg-ost", "mittelweg", "ostweg"}
