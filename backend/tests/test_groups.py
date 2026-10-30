"""Curated groups list: CSV validation, import, find_groups, and the agent's groups intent."""

from datetime import date
from pathlib import Path

import psycopg
import pytest
from test_agent_graph import (  # noqa: F401 (vocab, settings are fixtures)
    FakeTools,
    make,
    one,
    raw,
    run,
    settings,
    text_of,
    types,
    vocab,
)

from hikeall.agent.request import RawRequest
from hikeall.agent.tools import STALE_DAYS, GroupBrief, find_groups, is_stale
from hikeall.ingest.groups import GroupRow, GroupsError, import_groups, parse_row, read_groups

CSV_DIR = Path(__file__).resolve().parents[2] / "data" / "curated"
GOOD = {
    "id": "g-test", "name": "Testgruppe", "kind": "lauftreff", "place": "Titisee-Neustadt",
    "lat": "47.93", "lon": "8.19", "url": "https://example.org/g", "source_url": "https://example.org/g",
    "checked_at": "2026-10-30", "status": "vorschlag", "note": "Vorschlag Claude: Test",
}  # fmt: skip


def test_csv_rejects_unknown_kind():
    with pytest.raises(GroupsError, match="unbekannte Art"):
        parse_row(GOOD | {"kind": "kegelclub"}, 2)


def test_csv_rejects_missing_field_and_bad_link():
    with pytest.raises(GroupsError, match="Pflichtfeld"):
        parse_row(GOOD | {"name": ""}, 2)
    with pytest.raises(GroupsError, match="http"):
        parse_row(GOOD | {"url": "ftp://x"}, 2)


def test_stale_after_180_days():
    today = date(2026, 10, 30)
    assert STALE_DAYS == 180
    assert not is_stale(date(2026, 5, 3), today)  # exactly 180 days
    assert is_stale(date(2026, 5, 2), today)  # 181 days


def test_curated_csv_is_valid():
    rows = read_groups(CSV_DIR / "groups.csv")
    assert 20 <= len(rows) <= 40
    assert all(r.status == "vorschlag" and r.note.startswith("Vorschlag Claude:") for r in rows)


def _row(i: str, lat: float, lon: float, checked=date(2026, 10, 1)) -> GroupRow:
    return GroupRow(
        id=f"zz-test-{i}", name=f"Gruppe {i}", kind="wanderverein", place="Test", lat=lat,
        lon=lon, url="https://example.org", source_url="https://example.org",
        checked_at=checked, status="vorschlag",
    )  # fmt: skip


@pytest.mark.db
def test_find_groups_sorted_by_distance(conn):
    # the query point sits on the test rows (0 / ~1.1 / ~5.5 km away); real rows are filtered by name
    here = (48.9, 8.7)
    import_rows = [_row("c", 48.95, 8.7), _row("a", 48.9, 8.7), _row("b", 48.91, 8.7)]
    for r in import_rows:
        conn.execute("delete from groups where id = %s", (r.id,))
    import_groups_keep(conn, import_rows)
    got = find_groups(conn, *here, radius_km=25, today=date(2026, 10, 30))
    names = [g.name for g in got if g.name.startswith("Gruppe ")]
    assert names == ["Gruppe a", "Gruppe b", "Gruppe c"]
    assert got[0].dist_km == 0.0 and not got[0].stale
    only = find_groups(conn, *here, radius_km=2, today=date(2026, 10, 30))
    assert [g.name for g in only if g.name.startswith("Gruppe ")] == ["Gruppe a", "Gruppe b"]
    runners = find_groups(conn, *here, kind="lauftreff", today=date(2026, 10, 30))
    assert not [g for g in runners if g.name.startswith("Gruppe ")]  # the test rows are not runners


def import_groups_keep(conn, rows):
    """import_groups drops rows missing from its input; tests must not touch the real list."""
    for r in rows:
        conn.execute(
            "insert into groups (id, name, kind, place, geom, url, source_url, checked_at, status)"
            " values (%s, %s, %s, %s, st_setsrid(st_makepoint(%s, %s), 4326), %s, %s, %s, %s)",
            (r.id, r.name, r.kind, r.place, r.lon, r.lat, r.url, r.source_url, r.checked_at,
             r.status),
        )  # fmt: skip


@pytest.mark.db
def test_find_groups_marks_stale(conn):
    old = _row("old", 48.9, 8.7, checked=date(2025, 1, 1))
    conn.execute("delete from groups where id = %s", (old.id,))
    import_groups_keep(conn, [old])
    got = find_groups(conn, 48.9, 8.7, radius_km=1, today=date(2026, 10, 30))
    assert [(g.name, g.stale) for g in got if g.name == "Gruppe old"] == [("Gruppe old", True)]


def test_import_groups_needs_rows():
    with pytest.raises(GroupsError):
        import_groups(None, [])  # type: ignore[arg-type]


# --- agent: intent groups --------------------------------------------------------------------


class GroupTools(FakeTools):
    def __init__(self, groups):
        super().__init__()
        self.groups = groups
        self.group_calls = []

    def find_groups(self, lat, lon, radius_km=25.0, kind=None, today=None):
        self.group_calls.append((lat, lon, radius_km, kind))
        return self.groups


def _brief(name, checked, stale=False, dist=3.2):
    return GroupBrief(
        name=name, kind="wanderverein", place="Hinterzarten", url="https://example.org/" + name,
        checked_at=checked, stale=stale, dist_km=dist,
    )  # fmt: skip


def test_groups_intent_flow(vocab, settings):  # noqa: F811
    tools = GroupTools([_brief("A", date(2026, 10, 2)), _brief("B", date(2026, 3, 1), stale=True)])
    deps = make(
        vocab, settings, tools=tools,
        structured={RawRequest: [raw(intent="groups", start_text="Hausach")]},
    )  # fmt: skip
    events = run(deps, "Gibt es eine Wandergruppe in Hausach?")
    groups = one(events, "groups")
    assert [g.name for g in groups.groups] == ["A", "B"]
    assert groups.checked_note == "Stand: 01.03.2026"  # the oldest check date
    assert tools.group_calls and tools.group_calls[0][2] == 25.0
    assert deps.gateway.calls["answer"] == 0  # code-written answer, grounding cannot be bypassed
    text = text_of(events)
    assert "2 Gruppen" in text and "Hausach" in text and "Stand: 01.03.2026" in text
    assert types(events)[-1] == "done"


def test_groups_intent_without_place_asks(vocab, settings):  # noqa: F811
    deps = make(vocab, settings, tools=GroupTools([]), structured={RawRequest: [raw(intent="groups")]})
    events = run(deps, "Lauftreff?")
    assert "clarify" in types(events) and "groups" not in types(events)


def test_groups_intent_nothing_found_is_said(vocab, settings):  # noqa: F811
    deps = make(
        vocab, settings, tools=GroupTools([]),
        structured={RawRequest: [raw(intent="groups", start_text="Hausach")]},
    )  # fmt: skip
    events = run(deps, "Gruppe in Hausach?")
    assert "groups" not in types(events)
    assert "keine Gruppe" in text_of(events)


# --- grants and import_groups ---------------------------------------------------------------


@pytest.mark.db
def test_groups_and_view_are_select_only_for_anon_and_authenticated(conn):
    rows = conn.execute(
        "select grantee, table_name, privilege_type from information_schema.role_table_grants "
        "where table_name in ('groups', 'groups_geo') and grantee in ('anon', 'authenticated')"
    ).fetchall()
    assert rows and {r[2] for r in rows} == {"SELECT"}
    assert {(r[0], r[1]) for r in rows} == {
        (g, t) for g in ("anon", "authenticated") for t in ("groups", "groups_geo")
    }


@pytest.mark.db
def test_anon_cannot_write_through_groups_geo(conn):
    conn.execute("set local role anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("update groups_geo set name = 'x'")


@pytest.mark.db
def test_import_groups_upserts_and_drops_rows_missing_from_the_csv(conn):
    # inside the rolled-back test transaction: the real list is replaced, then rolled back
    a, b = _row("imp-a", 48.9, 8.7), _row("imp-b", 48.91, 8.7)
    assert import_groups(conn, [a, b]) == 2
    a.name = "Geändert"
    assert import_groups(conn, [a]) == 1  # b is missing from the "CSV": removed
    got = conn.execute("select id, name from groups order by id").fetchall()
    assert got == [("zz-test-imp-a", "Geändert")]
