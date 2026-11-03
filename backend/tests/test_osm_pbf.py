from pathlib import Path

import pytest

from hikesense.adapters.osm_pbf import pbf_timestamp, read_elements
from hikesense.ingest.places import RELATION_ID_OFFSET, parse_places, parse_pois
from hikesense.models import BLACK_FOREST_BBOX

FIXTURE = Path(__file__).parent / "fixtures" / "places_small.osm"


def _data():
    return read_elements(FIXTURE, BLACK_FOREST_BBOX)


def test_places_kinds_and_ids():
    places = {p.name: p for p in parse_places(_data())}
    assert set(places) == {
        "Hinterzarten",
        "Feldberg",
        "Titisee",
        "Schluchsee",
        "Feldberg (Schwarzwald)",
    }
    assert (places["Hinterzarten"].kind, places["Hinterzarten"].id) == ("village", 1)
    assert (places["Feldberg"].kind, places["Feldberg"].id) == ("peak", 2)
    assert (places["Titisee"].kind, places["Titisee"].id) == ("lake", -100)
    assert (places["Schluchsee"].kind, places["Schluchsee"].id) == (
        "lake",
        -(RELATION_ID_OFFSET + 300),
    )


def test_lake_centers_are_inside_the_geometry():
    places = {p.name: p for p in parse_places(_data())}
    assert places["Titisee"].lat == pytest.approx(47.905, abs=1e-6)
    assert places["Titisee"].lon == pytest.approx(8.205, abs=1e-6)
    # square 8.30-8.31 x 47.80-47.81 minus a hole in its lower-left part: centroid shifts up-right
    s = places["Schluchsee"]
    assert 47.805 < s.lat < 47.81
    assert 8.305 < s.lon < 8.31


def test_pois_kinds_and_ids():
    pois = {p.id: p for p in parse_pois(_data())}
    assert {i: p.kind for i, p in pois.items()} == {
        2: "peak",
        3: "viewpoint",
        4: "waterfall",
        5: "food",
        6: "station",
        -101: "hut",
    }
    assert (round(pois[-101].lat, 4), round(pois[-101].lon, 4)) == (47.9305, 8.4005)


def test_outside_bbox_and_non_matching_excluded():
    ids = {el["id"] for el in _data()["elements"]}
    assert 7 not in ids  # Berlin, outside bbox
    assert 8 not in ids  # amenity=bench
    assert 102 not in ids  # plain path way
    assert 200 not in ids and 201 not in ids  # member ways of the relation


def test_timestamp_absent_in_xml_is_none():
    assert pbf_timestamp(FIXTURE) is None


def test_municipality_from_admin_level_8_relation():
    places = {p.name: p for p in parse_places(_data())}
    m = places["Feldberg (Schwarzwald)"]
    assert (m.kind, m.id) == ("municipality", -(RELATION_ID_OFFSET + 400))
    assert m.lat == pytest.approx(47.85, abs=1e-4)
    assert m.lon == pytest.approx(8.05, abs=1e-4)
    assert "Landkreis" not in places  # admin_level=6 is not a municipality


def test_read_lodgings_named_tourism_kinds_only():
    from hikesense.ingest.lodgings import parse_lodgings

    data = read_elements(FIXTURE, BLACK_FOREST_BBOX, what="lodgings")
    assert [x["id"] for x in data["elements"]] == [40, 101]  # hotel node, alpine hut way
    assert sorted(x.name for x in parse_lodgings(data)) == ["Hotel Adler", "Huette"]


def test_read_regions_reads_each_file_once_and_splits_by_region(tmp_path, monkeypatch):
    from hikesense.adapters import osm_pbf
    from hikesense.regions import REGIONS, get_region

    for name in ("baden-wuerttemberg", "rheinland-pfalz"):
        (tmp_path / f"{name}-latest.osm.pbf").write_bytes(b"")
    reads = []

    def fake_read(path, bbox, what="places"):
        reads.append((path.name, what))
        return {
            "elements": [
                {"type": "node", "id": 1, "lat": 48.0, "lon": 8.0, "tags": {}},  # Black Forest
                {"type": "node", "id": 2, "lat": 49.3, "lon": 7.9, "tags": {}},  # Palatinate
            ]
        }

    monkeypatch.setattr(osm_pbf, "read_elements", fake_read)
    out = osm_pbf.read_regions(tmp_path, REGIONS, "lodgings")
    # Lake Constance needs schwaben/switzerland/austria too: not complete -> not read from PBF
    assert set(out) == {"black_forest", "palatinate"}
    assert sorted(reads) == [
        ("baden-wuerttemberg-latest.osm.pbf", "lodgings"),
        ("rheinland-pfalz-latest.osm.pbf", "lodgings"),
    ]
    assert [e["id"] for e in out["black_forest"]["elements"]] == [1]
    assert {e["id"] for e in out["palatinate"]["elements"]} == {2}
    assert get_region("lake_constance").extracts[-1] == "austria"
