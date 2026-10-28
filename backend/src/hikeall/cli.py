"""Command line: `hikeall import-trails [--only ID]`."""

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
from hikeall.ingest.stages import load_trail_specs
from hikeall.ingest.trails import import_trail

REPO_ROOT = Path(__file__).resolve().parents[3]
TRAILS_YAML = REPO_ROOT / "data" / "curated" / "trails.yaml"


def _repo_path(p: Path) -> Path:
    return p if p.is_absolute() else REPO_ROOT / p


def import_trails(only: str | None) -> int:
    try:
        settings = Settings()
    except ValidationError:
        print("Fehler: SUPABASE_DB_URL ist nicht gesetzt (.env oder Umgebung).", file=sys.stderr)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hikeall")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import-trails", help="Fernwege aus OSM importieren (trails.yaml)")
    p.add_argument("--only", metavar="ID", help="nur diesen Weg importieren")
    args = parser.parse_args(argv)
    if args.command == "import-trails":
        return import_trails(args.only)
    return 2


if __name__ == "__main__":
    sys.exit(main())
