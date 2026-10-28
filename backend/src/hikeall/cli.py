"""Command line: `hikeall import-trails [--only ID]`, `scan-day-hikes`, `import-day-hikes`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from hikeall.adapters.dem import CopernicusDem
from hikeall.adapters.http import make_http_client
from hikeall.adapters.overpass import OverpassClient
from hikeall.config import Settings
from hikeall.db import connect
from hikeall.errors import HikeAllError
from hikeall.ingest.day_hikes import (
    final_decision,
    import_day_hikes,
    read_candidates,
    scan,
    write_candidates,
)
from hikeall.ingest.lodgings import fetch_lodgings, import_lodgings
from hikeall.ingest.stages import load_trail_sources, load_trail_specs
from hikeall.ingest.trails import import_trail
from hikeall.models import BLACK_FOREST_BBOX

REPO_ROOT = Path(__file__).resolve().parents[3]
TRAILS_YAML = REPO_ROOT / "data" / "curated" / "trails.yaml"
DAY_HIKES_CSV = REPO_ROOT / "data" / "curated" / "day_hikes.csv"
OSM_SOURCE_ID = "osm"


def _repo_path(p: Path) -> Path:
    return p if p.is_absolute() else REPO_ROOT / p


def _settings() -> Settings | None:
    try:
        return Settings()
    except ValidationError:
        print("Fehler: SUPABASE_DB_URL ist nicht gesetzt (.env oder Umgebung).", file=sys.stderr)
        return None


def import_trails(only: str | None) -> int:
    settings = _settings()
    if settings is None:
        return 2
    specs = load_trail_specs(TRAILS_YAML)
    if only:
        specs = [s for s in specs if s.id == only]
        if not specs:
            print(f"Fehler: Weg '{only}' steht nicht in {TRAILS_YAML.name}.", file=sys.stderr)
            return 2

    failed = False
    with (
        make_http_client(240) as overpass_http,
        make_http_client(120) as dem_http,
        connect(settings.supabase_db_url) as conn,
    ):
        overpass = OverpassClient(overpass_http, url=settings.overpass_url)
        dem = CopernicusDem(dem_http, _repo_path(settings.dem_cache_dir), max_tiles=4)
        for spec in specs:
            try:
                rep = import_trail(conn, spec, overpass, dem)
            except (HikeAllError, ValueError) as e:
                conn.rollback()
                print(f"{spec.id}: Import abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
                failed = True
                continue
            conn.commit()
            print(f"{rep.trail_id}: {rep.length_km:.1f} km, {rep.stages} Etappen")
            print("  Etappen km: " + ", ".join(f"{km:.1f}" for km in rep.stage_km))
            if all(s.official_km is None for s in spec.stages):
                print(
                    "  Hinweis: keine offiziellen Etappenlängen in trails.yaml, "
                    "Abweichungsprüfung (> 5 %) übersprungen"
                )
            for w in rep.warnings:
                print(f"  Warnung: {w}")
    return 1 if failed else 0


def scan_day_hikes(csv_path: Path) -> int:
    settings = _settings()
    if settings is None:
        return 2
    with make_http_client(240) as http:
        overpass = OverpassClient(http, url=settings.overpass_url)
        try:
            res = scan(overpass, BLACK_FOREST_BBOX)
        except HikeAllError as e:
            print(f"Scan abgebrochen, CSV unverändert – {type(e).__name__}: {e}", file=sys.stderr)
            return 1
    found = res.candidates
    before = {c.osm_relation_id for c in read_candidates(csv_path)}
    write_candidates(csv_path, found)
    rows = read_candidates(csv_path)
    auto = sum(c.auto_decision == "accepted" for c in found)
    final = sum(final_decision(c)[0] == "accepted" for c in rows)
    new = len({c.osm_relation_id for c in found} - before)
    gone = len(before - {c.osm_relation_id for c in found})
    print(
        f"{len(found)} Wanderrelationen als Kandidaten ({new} neu, {gone} nicht mehr in OSM); "
        f"{res.skipped_segments} Wegenetz-Abschnitte (network:type=node_network) übergangen"
    )
    print(f"automatisch accepted: {auto}, nach manueller Entscheidung accepted: {final}")
    print(f"geschrieben: {csv_path}")
    return 0


def import_day_hikes_cmd(csv_path: Path) -> int:
    settings = _settings()
    if settings is None:
        return 2
    candidates = read_candidates(csv_path)
    if not candidates:
        print(f"Fehler: keine Kandidaten in {csv_path} (erst scan-day-hikes).", file=sys.stderr)
        return 2
    source = load_trail_sources(TRAILS_YAML)[OSM_SOURCE_ID]
    with (
        make_http_client(240) as overpass_http,
        make_http_client(120) as dem_http,
        connect(settings.supabase_db_url) as conn,
    ):
        overpass = OverpassClient(overpass_http, url=settings.overpass_url)
        dem = CopernicusDem(dem_http, _repo_path(settings.dem_cache_dir), max_tiles=4)
        try:
            rep = import_day_hikes(conn, candidates, overpass, dem, source=source)
        except BaseException:
            conn.rollback()
            raise
        conn.commit()
    for r in rep.imported:
        kind = "Rundweg" if r.roundtrip else "Strecke"
        print(f"{r.trail_id}: {r.name} – {r.length_km:.1f} km, {r.ascent_m} Hm, {kind}")
        for w in r.warnings:
            print(f"  Warnung: {w}")
    for tid in rep.removed:
        print(f"{tid}: entfernt (Entscheidung rejected)")
    for rid, err in rep.failed:
        print(f"Relation {rid}: Import fehlgeschlagen – {err}", file=sys.stderr)
    print(
        f"{len(rep.imported)} Tagestouren importiert, {len(rep.removed)} entfernt, "
        f"{len(rep.failed)} fehlgeschlagen"
    )
    return 1 if rep.failed else 0


STAGE_COUNT_SQL = """
    select s.id, s.trail_id, s.seq, count(l.id)
    from stages s
    left join lodgings l on st_dwithin(s.geom::geography, l.geom::geography, 1000)
    where s.trail_id like 'westweg%%'
    group by s.id, s.trail_id, s.seq
    order by s.trail_id, s.seq
"""


def import_lodgings_cmd() -> int:
    settings = _settings()
    if settings is None:
        return 2
    source = load_trail_sources(TRAILS_YAML)[OSM_SOURCE_ID]
    with (
        make_http_client(240) as http,
        connect(settings.supabase_db_url) as conn,
    ):
        overpass = OverpassClient(http, url=settings.overpass_url)
        try:
            lodgings = fetch_lodgings(overpass, BLACK_FOREST_BBOX)
            links = import_lodgings(conn, lodgings, source)
        except BaseException as e:
            conn.rollback()
            if isinstance(e, (HikeAllError, ValueError)):
                print(f"Import abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
                return 1
            raise
        conn.commit()
        total = conn.execute("select count(*) from lodgings").fetchone()[0]
        rows = conn.execute(STAGE_COUNT_SQL).fetchall()
    print(
        f"{len(lodgings)} Unterkünfte in OSM gefunden, {total} innerhalb 2 km eines Wegs "
        f"importiert, {links} Weg-Verknüpfungen"
    )
    print(
        "Westweg-Etappen: Unterkünfte mit Abstand <= 1000 m zur Etappe (ST_DWithin auf stages.geom)"
    )
    for sid, _trail, _seq, n in rows:
        print(f"  {sid}: {n}")
    for sid, _trail, _seq, n in rows:
        if n == 0:
            print(f"  Warnung: {sid} hat keine Unterkunft im Umkreis von 1 km")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hikeall")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import-trails", help="Fernwege aus OSM importieren (trails.yaml)")
    p.add_argument("--only", metavar="ID", help="nur diesen Weg importieren")
    sub.add_parser(
        "import-lodgings", help="Unterkünfte aus OSM importieren und mit Wegen verknüpfen"
    )
    for name, help_text in (
        ("scan-day-hikes", "Tagestour-Kandidaten aus OSM in die Kurations-CSV schreiben"),
        ("import-day-hikes", "akzeptierte Tagestouren aus der CSV importieren"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--csv", type=Path, default=DAY_HIKES_CSV, help="Kurations-CSV")
    args = parser.parse_args(argv)
    if args.command == "import-trails":
        return import_trails(args.only)
    if args.command == "import-lodgings":
        return import_lodgings_cmd()
    if args.command == "scan-day-hikes":
        return scan_day_hikes(_repo_path(args.csv))
    if args.command == "import-day-hikes":
        return import_day_hikes_cmd(_repo_path(args.csv))
    return 2


if __name__ == "__main__":
    sys.exit(main())
