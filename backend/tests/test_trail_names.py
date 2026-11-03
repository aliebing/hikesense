import pytest
from test_agent_tools import SRC, add_trail, shifted

from hikesense.db import upsert_source
from hikesense.ingest.names import is_numbered_name, name_numbered_trails


@pytest.mark.parametrize(
    "name",
    [
        "Rundweg A1",
        "Rundwanderweg 4",
        "Rundwanderweg S1",
        "Rundweg 5",
        "Wanderweg 12",
        "rundweg b6",
    ],
)
def test_numbered_names_say_nothing_without_a_place(name):
    assert is_numbered_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "Rundweg A1 (Ahausen)",  # already named
        "Rundwanderweg Iggelbach 5",  # carries its place
        "Genießerpfad Säbelthomaweg",
        "Gutach 4: Fuchsloch-Route",
        "",
    ],
)
def test_names_with_a_place_stay(name):
    assert not is_numbered_name(name)


def _place(conn, pid, name, kind, lat, lon):
    conn.execute(
        "insert into places (id, name, kind, geom, source_id) "
        "values (%s, %s, %s, st_setsrid(st_makepoint(%s, %s), 4326), %s)",
        (pid, name, kind, lon, lat, SRC.id),
    )


def _rename(conn, trail_id, name):
    conn.execute("update trails set name = %s where id = %s", (name, trail_id))


def _name(conn, trail_id):
    return conn.execute("select name from trails where id = %s", (trail_id,)).fetchone()[0]


@pytest.mark.db
def test_numbered_trails_get_the_village_at_their_start(conn):
    upsert_source(conn, SRC)
    start_lat, start_lon = shifted(0.0)[0]
    add_trail(conn, "test-nm-a1")
    _rename(conn, "test-nm-a1", "Rundweg A1")
    add_trail(conn, "test-nm-named")
    _rename(conn, "test-nm-named", "Genießerpfad Zzz")
    # nearest village wins; a hamlet right at the start does not count
    _place(conn, -9_100_001, "Zzzhausen", "village", start_lat + 0.003, start_lon)
    _place(conn, -9_100_002, "Zzzweiler", "hamlet", start_lat, start_lon)
    _place(conn, -9_100_003, "Zzzstadt", "town", start_lat + 0.02, start_lon)

    assert name_numbered_trails(conn) >= 1
    assert _name(conn, "test-nm-a1") == "Rundweg A1 (Zzzhausen)"
    assert _name(conn, "test-nm-named") == "Genießerpfad Zzz"
    # running it again changes nothing
    name_numbered_trails(conn)
    assert _name(conn, "test-nm-a1") == "Rundweg A1 (Zzzhausen)"


@pytest.mark.db
def test_no_village_within_5_km_keeps_the_name(conn):
    upsert_source(conn, SRC)
    start_lat, start_lon = shifted(0.0)[0]
    add_trail(conn, "test-nm-far")
    _rename(conn, "test-nm-far", "Rundweg B9")
    _place(conn, -9_100_011, "Zzzfern", "village", start_lat + 0.1, start_lon)  # ~11 km
    name_numbered_trails(conn)
    assert _name(conn, "test-nm-far") == "Rundweg B9"
