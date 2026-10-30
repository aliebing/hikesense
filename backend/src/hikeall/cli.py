"""Command line: `hikeall import-trails [--only ID]`, `scan-day-hikes`, `import-day-hikes`, `import-groups`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from pydantic import ValidationError

from hikeall.adapters.commons import CommonsClient
from hikeall.adapters.dem import CopernicusDem
from hikeall.adapters.http import make_http_client
from hikeall.adapters.osm_pbf import pbf_timestamp, read_elements
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
from hikeall.ingest.groups import import_groups, read_groups
from hikeall.ingest.lodgings import fetch_lodgings, import_lodgings
from hikeall.ingest.photos import import_photos, load_targets
from hikeall.ingest.places import (
    fetch_places,
    fetch_pois,
    import_places,
    parse_places,
    parse_pois,
)
from hikeall.ingest.shares import import_shares
from hikeall.ingest.stages import load_trail_sources, load_trail_specs
from hikeall.ingest.trails import import_trail
from hikeall.knowledge.corpus import chunk, fetch_articles, load_own_texts, load_sources
from hikeall.knowledge.search import FastEmbedder, KnowledgeIndex
from hikeall.models import BLACK_FOREST_BBOX
from hikeall.tags.vocabulary import FEATURES_YAML, TagVocabulary, compute_trail_tags

REPO_ROOT = Path(__file__).resolve().parents[3]
TRAILS_YAML = REPO_ROOT / "data" / "curated" / "trails.yaml"
DAY_HIKES_CSV = REPO_ROOT / "data" / "curated" / "day_hikes.csv"
GROUPS_CSV = REPO_ROOT / "data" / "curated" / "groups.csv"
KNOWLEDGE_DIR = REPO_ROOT / "data" / "knowledge"
CHROMA_DIR = REPO_ROOT / "data" / "chroma"
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


def import_groups_cmd(csv_path: Path) -> int:
    settings = _settings()
    if settings is None:
        return 2
    try:
        rows = read_groups(csv_path)
    except (HikeAllError, OSError) as e:
        print(f"Fehler: {csv_path}: {e}", file=sys.stderr)
        return 2
    with connect(settings.supabase_db_url) as conn:
        try:
            n = import_groups(conn, rows)
        except BaseException:
            conn.rollback()
            raise
        conn.commit()
    print(f"{n} Gruppen importiert ({sum(r.status == 'vorschlag' for r in rows)} Vorschläge)")
    return 0


def import_shares_cmd(only: str | None) -> int:
    settings = _settings()
    if settings is None:
        return 2
    long_distance = {s.id: s.osm_relation_ids for s in load_trail_specs(TRAILS_YAML)}
    with (
        make_http_client(240) as http,
        connect(settings.supabase_db_url) as conn,
    ):
        rows = conn.execute("select id, kind, osm_relation_id from trails order by id").fetchall()
        targets: dict[str, list[int]] = {}
        skipped: list[str] = []
        for tid, kind, rel in rows:
            if kind == "long_distance" and tid in long_distance:
                targets[tid] = long_distance[tid]
            elif kind == "day_hike" and rel is not None:
                targets[tid] = [int(rel)]
            else:
                skipped.append(tid)
        if only:
            if only not in targets:
                print(f"Fehler: Weg '{only}' nicht in der DB oder ohne Relation.", file=sys.stderr)
                return 2
            targets = {only: targets[only]}
            skipped = []
        overpass = OverpassClient(http, url=settings.overpass_url)
        try:
            rep = import_shares(conn, overpass, targets)
        except BaseException:
            conn.rollback()
            raise
        conn.commit()
    for tid, share in sorted(rep.updated.items()):
        print(f"{tid}: " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(share.items())))
    for tid, unknown in rep.mostly_unknown():
        print(f"  Warnung: {tid}: Belag zu {unknown:.0%} unbekannt")
    for tid in skipped:
        print(f"{tid}: übersprungen (keine OSM-Relation bekannt)", file=sys.stderr)
    for tid, err in rep.failed:
        print(f"{tid}: Anteile fehlgeschlagen – {err}", file=sys.stderr)
    print(
        f"{len(rep.updated)} Touren mit Anteilen, {len(rep.mostly_unknown())} mit Belag "
        f"> 50 % unbekannt, {len(rep.failed)} fehlgeschlagen, {len(skipped)} übersprungen"
    )
    return 1 if rep.failed or skipped else 0


STAGE_COUNT_SQL = """
    select s.id, s.trail_id, s.seq, count(distinct l.id)
    from (select id, trail_id, seq, st_subdivide(geom, 64) as geom from stages) s
    left join lodgings l on l.geom && st_expand(s.geom, 0.015)  -- index prefilter, > 1 km
      and st_dwithin(s.geom::geography, l.geom::geography, 1000)
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


def import_places_cmd(pbf: Path | None = None) -> int:
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
            if pbf is not None:
                pbf = _repo_path(pbf)
                if not pbf.is_file():
                    print(f"Fehler: OSM-Extrakt nicht gefunden: {pbf}", file=sys.stderr)
                    return 2
                data = read_elements(pbf, BLACK_FOREST_BBOX)
                places, pois = parse_places(data), parse_pois(data)
                print(f"OSM-Extrakt {pbf.name}, Stand {pbf_timestamp(pbf) or 'unbekannt'}")
            else:
                places = fetch_places(overpass, BLACK_FOREST_BBOX)
                pois = fetch_pois(overpass, BLACK_FOREST_BBOX)
            links = import_places(conn, places, pois, source)
        except BaseException as e:
            conn.rollback()
            if isinstance(e, (HikeAllError, ValueError)):
                print(f"Import abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
                return 1
            raise
        conn.commit()
        place_rows = conn.execute(
            "select kind, count(*) from places group by kind order by kind"
        ).fetchall()
        poi_rows = conn.execute(
            "select kind, count(*) from pois group by kind order by kind"
        ).fetchall()
        linked = conn.execute("select count(distinct poi_id) from trail_pois").fetchone()[0]
    print("Orte: " + ", ".join(f"{k} {n}" for k, n in place_rows))
    print("POIs (<= 300 m von einem Weg): " + ", ".join(f"{k} {n}" for k, n in poi_rows))
    print(f"{len(pois)} POIs in OSM, {linked} mit Weg verknüpft, {links} Weg-Verknüpfungen")
    return 0


def build_tags_cmd() -> int:
    settings = _settings()
    if settings is None:
        return 2
    with connect(settings.supabase_db_url) as conn:
        vocab = TagVocabulary.load(conn, FEATURES_YAML)
        rows = compute_trail_tags(conn, vocab)
        conn.commit()
        counts = dict(
            conn.execute("select tag_id, count(*) from trail_tags group by tag_id").fetchall()
        )
        trails = conn.execute("select count(*) from trails").fetchone()[0]
    stored = [t for t in vocab.all() if t.category in ("feature", "surface")]
    print(f"{trails} Touren, {rows} Tag-Zuordnungen, {len(vocab)} Tags im Vokabular")
    for t in stored:
        print(f"{t.id}: {counts.get(t.id, 0)} Touren")
    for t in stored:
        if counts.get(t.id, 0) == 0:
            print(f"  Warnung: {t.id} hat 0 Touren")
    return 0


# Wikimedia rejects (403) user agents without a usable contact URL.
COMMONS_USER_AGENT = os.environ.get(
    "HIKEALL_USER_AGENT",
    "HikeAllAbout/0.1 (student project; https://github.com/aliebing/HikeAllAbout)",
)


def import_photos_cmd(only: str | None) -> int:
    settings = _settings()
    if settings is None:
        return 2
    with (
        make_http_client(60, COMMONS_USER_AGENT) as http,
        connect(settings.supabase_db_url) as conn,
    ):
        client = CommonsClient(
            http, backoff_s=1.0, api_error_retries=25
        )  # Commons search is often busy
        targets = load_targets(conn)
        if not targets:
            print(
                "Fehler: keine Etappen/Tagestouren in der DB (erst import-trails).",
                file=sys.stderr,
            )
            return 2
        if only:
            targets = [t for t in targets if t.trail_id == only]
            if not targets:
                print(
                    f"Fehler: Weg '{only}' hat keine Etappen/Tagestour in der DB.", file=sys.stderr
                )
                return 2
        by_trail: dict[str, list] = {}
        for t in targets:
            by_trail.setdefault(t.trail_id, []).append(t)
        counts: dict[str, int] = {}
        empty: list[str] = []
        failed: list[str] = []
        done = 0
        # One transaction per trail: a trail is replaced completely or not at all, and a failing
        # Commons request never leaves a half-written trail. Re-running is idempotent.
        for tid, group in by_trail.items():

            def progress(_n, _total, t, photos):
                print(f"{t.stage_id or t.trail_id}: {len(photos)}", file=sys.stderr)

            try:
                rep = import_photos(conn, client, group, on_progress=progress)
            except (HikeAllError, ValueError) as e:
                conn.rollback()
                print(
                    f"{tid}: Import abgebrochen, nichts geschrieben – {type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                failed.append(tid)
                continue
            except BaseException:
                conn.rollback()
                raise
            conn.commit()
            done += 1
            counts.update(rep.counts)
            empty += rep.empty
    westweg = {k: v for k, v in counts.items() if k.startswith("westweg")}
    for tid, n in sorted(westweg.items()):
        print(f"{tid}: {n} Bilder")
    hikes = len(counts) - len(westweg)
    print(
        f"{sum(counts.values())} Bilder, {len(westweg)} Fernwege, {hikes} Tagestouren "
        f"({sum(v for k, v in counts.items() if k not in westweg)} Bilder an Tagestouren)"
    )
    if empty:
        print("Ohne Bild: " + ", ".join(empty))
    if failed:
        print("Fehlgeschlagen (nichts geschrieben): " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


def build_knowledge_cmd() -> int:
    missing = []
    try:
        with make_http_client(60, COMMONS_USER_AGENT) as http:
            articles = fetch_articles(
                http, load_sources(KNOWLEDGE_DIR / "sources.yaml"), on_missing=missing.append
            )
        own = load_own_texts(KNOWLEDGE_DIR)
    except HikeAllError as e:
        print(f"Wissensindex abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    for src in missing:
        print(f"Warnung: Artikel fehlt: {src.site} / {src.title}", file=sys.stderr)
    chunks = [c for doc in [*articles, *own] for c in chunk(doc)]
    try:
        KnowledgeIndex.build(chunks, CHROMA_DIR, FastEmbedder())
    except HikeAllError as e:
        print(f"Wissensindex abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(
        f"{len(articles)} Artikel, {len(own)} eigene Texte, {len(chunks)} Chunks, "
        f"{len(missing)} Artikel fehlen -> {CHROMA_DIR}"
    )
    return 0


def smoke_cmd() -> int:
    from hikeall import smoke as sm
    from hikeall.api.chat import default_deps_factory

    settings = _settings()
    if settings is None:
        return 2
    try:
        user_hash = sm.authorize(settings)  # the same token check as POST /chat
        return sm.smoke(
            default_deps_factory(settings),
            REPO_ROOT / "data" / "smoke" / "prompts.yaml",
            REPO_ROOT / "data" / "smoke",
            user_hash=user_hash,
        )
    except (HikeAllError, psycopg.Error) as e:  # e.g. database down: a message, no traceback
        print(f"Smoke abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
        return 2


def smoke_user_cmd() -> int:
    from hikeall import smoke as sm

    settings = _settings()
    if settings is None:
        return 2
    try:
        with make_http_client(sm.AUTH_TIMEOUT_S) as http:
            state = sm.create_user(http, settings)
    except HikeAllError as e:
        print(f"Smoke-Nutzer – {e}", file=sys.stderr)
        return 2
    print(f"Smoke-Nutzer {sm.SMOKE_EMAIL} {state}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hikeall")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import-trails", help="Fernwege aus OSM importieren (trails.yaml)")
    p.add_argument("--only", metavar="ID", help="nur diesen Weg importieren")
    p = sub.add_parser(
        "import-shares", help="Belag- und Wegtyp-Anteile der vorhandenen Touren berechnen"
    )
    p.add_argument("--only", metavar="ID", help="nur diese Tour")
    sub.add_parser(
        "import-lodgings", help="Unterkünfte aus OSM importieren und mit Wegen verknüpfen"
    )
    p = sub.add_parser(
        "import-places", help="Orte und POIs aus OSM importieren, POIs mit Wegen verknüpfen"
    )
    p.add_argument("--pbf", type=Path, help="lokaler Geofabrik-Extrakt statt Overpass")
    sub.add_parser(
        "build-knowledge", help="Wissensindex (ChromaDB + BM25) aus Wikipedia und eigenen Texten"
    )
    sub.add_parser("smoke", help="Chat-Fälle gegen das echte Modell (kostet wenig, braucht Key)")
    sub.add_parser("smoke-user", help="Testkonto smoke@hikeall.local in der lokalen Supabase-Auth")
    sub.add_parser("build-tags", help="Merkmal- und Belag-Tags je Tour berechnen")
    p = sub.add_parser("import-photos", help="Wikimedia-Commons-Bilder mit Attribution importieren")
    p.add_argument("--only", metavar="ID", help="nur diesen Weg importieren")
    for name, help_text in (
        ("scan-day-hikes", "Tagestour-Kandidaten aus OSM in die Kurations-CSV schreiben"),
        ("import-day-hikes", "akzeptierte Tagestouren aus der CSV importieren"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--csv", type=Path, default=DAY_HIKES_CSV, help="Kurations-CSV")
    p = sub.add_parser("import-groups", help="Gruppenliste aus der Kurations-CSV importieren")
    p.add_argument("--csv", type=Path, default=GROUPS_CSV, help="Gruppen-CSV")
    args = parser.parse_args(argv)
    if args.command == "import-trails":
        return import_trails(args.only)
    if args.command == "import-shares":
        return import_shares_cmd(args.only)
    if args.command == "import-lodgings":
        return import_lodgings_cmd()
    if args.command == "import-places":
        return import_places_cmd(args.pbf)
    if args.command == "build-knowledge":
        return build_knowledge_cmd()
    if args.command == "smoke":
        return smoke_cmd()
    if args.command == "smoke-user":
        return smoke_user_cmd()
    if args.command == "build-tags":
        return build_tags_cmd()
    if args.command == "import-photos":
        return import_photos_cmd(args.only)
    if args.command == "scan-day-hikes":
        return scan_day_hikes(_repo_path(args.csv))
    if args.command == "import-day-hikes":
        return import_day_hikes_cmd(_repo_path(args.csv))
    if args.command == "import-groups":
        return import_groups_cmd(_repo_path(args.csv))
    return 2


if __name__ == "__main__":
    sys.exit(main())
