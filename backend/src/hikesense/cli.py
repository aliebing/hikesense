"""Command line: `hikesense import-trails [--only ID]`, `scan-day-hikes`, `import-day-hikes`, `import-groups`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from pydantic import ValidationError

from hikesense.adapters.commons import CommonsClient
from hikesense.adapters.dem import CopernicusDem
from hikesense.adapters.http import make_http_client
from hikesense.adapters.osm_pbf import extract_paths, pbf_timestamp
from hikesense.adapters.overpass import OverpassClient
from hikesense.config import Settings, export_langsmith_env
from hikesense.db import connect
from hikesense.errors import HikeSenseError
from hikesense.ingest.day_hikes import (
    final_decision,
    import_day_hikes,
    read_candidates,
    scan,
    write_candidates,
)
from hikesense.ingest.groups import import_groups, read_groups
from hikesense.ingest.lodgings import collect_lodgings, import_lodgings
from hikesense.ingest.names import name_numbered_trails
from hikesense.ingest.photos import import_photos, load_targets
from hikesense.ingest.places import collect_places, import_places
from hikesense.ingest.shares import import_shares
from hikesense.ingest.stages import load_trail_sources, load_trail_specs
from hikesense.ingest.trails import import_trail
from hikesense.knowledge.corpus import chunk, fetch_articles, load_own_texts, load_sources
from hikesense.knowledge.search import FastEmbedder, KnowledgeIndex
from hikesense.regions import REGIONS, get_region
from hikesense.tags.vocabulary import FEATURES_YAML, TagVocabulary, compute_trail_tags

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
        settings = Settings()
    except ValidationError:
        print("Fehler: SUPABASE_DB_URL ist nicht gesetzt (.env oder Umgebung).", file=sys.stderr)
        return None
    export_langsmith_env(settings)  # optional LangSmith tracing (chat/eval runs)
    return settings


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
            except (HikeSenseError, ValueError) as e:
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


def scan_day_hikes(csv_path: Path, region_id: str | None = None) -> int:
    settings = _settings()
    if settings is None:
        return 2
    if region_id is None:
        regions = REGIONS
    else:
        try:
            regions = (get_region(region_id),)
        except KeyError:
            names = ", ".join(r.id for r in REGIONS)
            print(f"Fehler: unbekannte Region {region_id!r} (verfügbar: {names}).", file=sys.stderr)
            return 2
    with make_http_client(240) as http:
        overpass = OverpassClient(http, url=settings.overpass_url)
        try:
            res = scan(overpass, regions)
        except HikeSenseError as e:
            print(f"Scan abgebrochen, CSV unverändert – {type(e).__name__}: {e}", file=sys.stderr)
            return 1
    found = res.candidates
    scanned = {r.id for r in regions}
    before = {c.osm_relation_id for c in read_candidates(csv_path) if c.region in scanned}
    write_candidates(csv_path, found, None if region_id is None else {region_id})
    rows = read_candidates(csv_path)
    auto = sum(c.auto_decision == "accepted" for c in found)
    final = sum(final_decision(c)[0] == "accepted" for c in rows)
    new = len({c.osm_relation_id for c in found} - before)
    gone = len(before - {c.osm_relation_id for c in found})
    print(
        f"{len(found)} Wanderrelationen als Kandidaten ({new} neu, {gone} nicht mehr in OSM); "
        f"{res.skipped_segments} Wegenetz-Abschnitte (network:type=node_network) übergangen"
    )
    for r in regions:
        in_region = [c for c in found if c.region == r.id]
        acc = sum(c.auto_decision == "accepted" for c in in_region)
        print(f"  {r.name}: {len(in_region)} Kandidaten, automatisch accepted: {acc}")
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
            # the import writes OSM names; numbered ones get their village again (needs places)
            name_numbered_trails(conn)
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
    except (HikeSenseError, OSError) as e:
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
    long_distance = {s.id: s.relation_ids for s in load_trail_specs(TRAILS_YAML)}
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
    join trails t on t.id = s.trail_id and t.kind = 'long_distance'
    left join lodgings l on l.geom && st_expand(s.geom, 0.015)  -- index prefilter, > 1 km
      and st_dwithin(s.geom::geography, l.geom::geography, 1000)
    group by s.id, s.trail_id, s.seq
    order by s.trail_id, s.seq
"""


def _pbf_dir(pbf_dir: Path | None) -> Path | None:
    """Repo-relative extract directory; prints which regions come from which files."""
    if pbf_dir is None:
        return None
    pbf_dir = _repo_path(pbf_dir)
    for region in REGIONS:
        paths = extract_paths(pbf_dir, region)
        if paths is None:
            print(f"{region.name}: Extrakte fehlen in {pbf_dir}, Overpass")
        else:
            stamps = ", ".join(f"{p.name} ({pbf_timestamp(p) or 'Stand unbekannt'})" for p in paths)
            print(f"{region.name}: aus {stamps}")
    return pbf_dir


def import_lodgings_cmd(pbf_dir: Path | None = None) -> int:
    settings = _settings()
    if settings is None:
        return 2
    pbf_dir = _pbf_dir(pbf_dir)
    source = load_trail_sources(TRAILS_YAML)[OSM_SOURCE_ID]
    with (
        make_http_client(240) as http,
        connect(settings.supabase_db_url) as conn,
    ):
        overpass = OverpassClient(http, url=settings.overpass_url)
        try:
            lodgings = collect_lodgings(
                overpass,
                REGIONS,
                lambda r, n: print(f"{r.name}: {n} Unterkünfte in OSM"),
                pbf_dir=pbf_dir,
            )
            links = import_lodgings(conn, lodgings, source)
        except BaseException as e:
            conn.rollback()
            if isinstance(e, (HikeSenseError, ValueError)):
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
        "Fernweg-Etappen: Unterkünfte mit Abstand <= 1000 m zur Etappe (ST_DWithin auf stages.geom)"
    )
    for sid, _trail, _seq, n in rows:
        print(f"  {sid}: {n}")
    for sid, _trail, _seq, n in rows:
        if n == 0:
            print(f"  Warnung: {sid} hat keine Unterkunft im Umkreis von 1 km")
    return 0


def import_places_cmd(pbf_dir: Path | None = None) -> int:
    settings = _settings()
    if settings is None:
        return 2
    pbf_dir = _pbf_dir(pbf_dir)
    source = load_trail_sources(TRAILS_YAML)[OSM_SOURCE_ID]
    with (
        make_http_client(240) as http,
        connect(settings.supabase_db_url) as conn,
    ):
        overpass = OverpassClient(http, url=settings.overpass_url)
        try:
            places, pois = collect_places(
                overpass,
                REGIONS,
                pbf_dir,
                lambda r, n, m: print(f"{r.name}: {n} Orte, {m} POIs in OSM"),
            )
            links = import_places(conn, places, pois, source)
            named = name_numbered_trails(conn)  # needs the places
        except BaseException as e:
            conn.rollback()
            if isinstance(e, (HikeSenseError, ValueError)):
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
    print(f"{named} Nummern-Touren mit Ortsnamen versehen (z. B. „Rundweg A1 (Ahausen)“)")
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
    "HIKESENSE_USER_AGENT",
    "HikeSense/0.1 (student project; https://github.com/TuringCollegeSubmissions/alliebi-AE.CAP.AFA.1.1)",
)


def photo_summary(counts: dict[str, int], long_distance: set[str]) -> list[str]:
    """Photos per long-distance trail, then one total line (day hikes summed)."""
    fern = {k: v for k, v in counts.items() if k in long_distance}
    lines = [f"{tid}: {n} Bilder" for tid, n in sorted(fern.items())]
    lines.append(
        f"{sum(counts.values())} Bilder, {len(fern)} Fernwege, {len(counts) - len(fern)} "
        f"Tagestouren ({sum(v for k, v in counts.items() if k not in fern)} Bilder an Tagestouren)"
    )
    return lines


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
            except (HikeSenseError, ValueError) as e:
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
        long_distance = {
            r[0] for r in conn.execute("select id from trails where kind = 'long_distance'")
        }
    for line in photo_summary(counts, long_distance):
        print(line)
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
    except HikeSenseError as e:
        print(f"Wissensindex abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    for src in missing:
        print(f"Warnung: Artikel fehlt: {src.site} / {src.title}", file=sys.stderr)
    chunks = [c for doc in [*articles, *own] for c in chunk(doc)]
    try:
        KnowledgeIndex.build(chunks, CHROMA_DIR, FastEmbedder())
    except HikeSenseError as e:
        print(f"Wissensindex abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(
        f"{len(articles)} Artikel, {len(own)} eigene Texte, {len(chunks)} Chunks, "
        f"{len(missing)} Artikel fehlen -> {CHROMA_DIR}"
    )
    return 0


def smoke_cmd() -> int:
    from hikesense import smoke as sm
    from hikesense.api.chat import default_deps_factory

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
    except (HikeSenseError, psycopg.Error) as e:  # e.g. database down: a message, no traceback
        print(f"Smoke abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
        return 2


def eval_cmd(
    cases: Path | None = None, model: str | None = None, temperature: float | None = None
) -> int:
    from hikesense import evaluation as ev
    from hikesense import smoke as sm
    from hikesense.api import chat

    settings = _settings()
    if settings is None:
        return 2
    if model is not None:
        settings.hikesense_model = model
    if temperature is not None:
        settings.hikesense_temperature = temperature
    try:
        user_hash = sm.authorize(settings)  # signs in as the smoke user, like `hikesense smoke`
        weather = ev.FixtureWeather(ev.WEATHER_PATH)  # stored forecasts, never live
        return ev.evaluate(
            chat.default_deps_factory(settings, weather_client=weather),
            cases or ev.CASES_PATH,
            ev.OUT_DIR,
            user_hash=user_hash,
        )
    except (HikeSenseError, psycopg.Error) as e:  # e.g. database down: a message, no traceback
        print(f"Eval abgebrochen – {type(e).__name__}: {e}", file=sys.stderr)
        return 2


def smoke_user_cmd() -> int:
    from hikesense import smoke as sm

    settings = _settings()
    if settings is None:
        return 2
    try:
        with make_http_client(sm.AUTH_TIMEOUT_S) as http:
            state = sm.create_user(http, settings)
    except HikeSenseError as e:
        print(f"Smoke-Nutzer – {e}", file=sys.stderr)
        return 2
    print(f"Smoke-Nutzer {sm.SMOKE_EMAIL} {state}")
    return 0


def admin_user_cmd() -> int:
    from hikesense import admin

    settings = _settings()
    if settings is None:
        return 2
    if settings.hikesense_admin_password_hash is None:
        print("Admin – HIKESENSE_ADMIN_PASSWORD_HASH in .env eintragen (siehe .env.example)", file=sys.stderr)
        return 2
    try:
        with connect(settings.supabase_db_url) as conn:
            state = admin.ensure_admin(conn, settings.hikesense_admin_password_hash.get_secret_value())
    except (ValueError, psycopg.Error) as e:
        print(f"Admin – {e}", file=sys.stderr)
        return 2
    print(f"Admin {admin.ADMIN_EMAIL} {state}, Rolle admin (Anmeldename: admin)")
    return 0


def users_migrate_cmd() -> int:
    from hikesense.supabase_admin import SupabaseAdmin, SupabaseAdminError
    from hikesense.users import migrate_accounts

    settings = _settings()
    if settings is None:
        return 2
    try:
        with make_http_client(10.0) as http, connect(settings.supabase_db_url) as conn:
            lines = migrate_accounts(conn, SupabaseAdmin(settings, http))
    except (SupabaseAdminError, psycopg.Error) as e:
        print(f"Konten-Umstellung – {e}", file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    print(f"Konten-Umstellung fertig ({len(lines)} Änderungen)")
    return 0


def prune_photos_cmd() -> int:
    from hikesense.ingest.photos import prune_rejected_photos

    settings = _settings()
    if settings is None:
        return 2
    with connect(settings.supabase_db_url) as conn:
        n = prune_rejected_photos(conn)
    print(f"{n} unpassende Fotos entfernt")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hikesense")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import-trails", help="Fernwege aus OSM importieren (trails.yaml)")
    p.add_argument("--only", metavar="ID", help="nur diesen Weg importieren")
    p = sub.add_parser(
        "import-shares", help="Belag- und Wegtyp-Anteile der vorhandenen Touren berechnen"
    )
    p.add_argument("--only", metavar="ID", help="nur diese Tour")
    pbf_help = (
        "Ordner mit Geofabrik-Extrakten (<name>-latest.osm.pbf); Regionen, deren Extrakte "
        "alle da sind, kommen daraus, die übrigen über Overpass"
    )
    p = sub.add_parser(
        "import-lodgings", help="Unterkünfte aus OSM importieren und mit Wegen verknüpfen"
    )
    p.add_argument("--pbf-dir", type=Path, help=pbf_help)
    p = sub.add_parser(
        "import-places", help="Orte und POIs aus OSM importieren, POIs mit Wegen verknüpfen"
    )
    p.add_argument("--pbf-dir", type=Path, help=pbf_help)
    sub.add_parser(
        "build-knowledge", help="Wissensindex (ChromaDB + BM25) aus Wikipedia und eigenen Texten"
    )
    sub.add_parser("smoke", help="Chat-Fälle gegen das echte Modell (kostet wenig, braucht Key)")
    p = sub.add_parser("eval", help="Eval-Testsatz gegen das echte Modell, Kennzahlen und Bericht")
    p.add_argument("--cases", type=Path, help="Fall-Datei (Standard: data/eval/cases.yaml)")
    p.add_argument("--model", help="Modell statt HIKESENSE_MODEL (OpenRouter-Slug)")
    p.add_argument("--temperature", type=float, help="Temperatur für alle Aufrufe (Standard: fest)")
    sub.add_parser("smoke-user", help="Testkonto smoke@hikesense.local in der lokalen Supabase-Auth")
    sub.add_parser("prune-photos", help="Unpassende Commons-Fotos (Bankkarte, ISS, Bahnhof, …) aus der DB entfernen")
    sub.add_parser(
        "users-migrate", help="Einmalig: bestehende Konten bestätigen, altes Admin-Konto löschen"
    )
    sub.add_parser("admin-user", help="Admin admin@hikesense.local mit Hash aus HIKESENSE_ADMIN_PASSWORD_HASH")
    sub.add_parser("build-tags", help="Merkmal- und Belag-Tags je Tour berechnen")
    p = sub.add_parser("import-photos", help="Wikimedia-Commons-Bilder mit Attribution importieren")
    p.add_argument("--only", metavar="ID", help="nur diesen Weg importieren")
    for name, help_text in (
        ("scan-day-hikes", "Tagestour-Kandidaten aus OSM in die Kurations-CSV schreiben"),
        ("import-day-hikes", "akzeptierte Tagestouren aus der CSV importieren"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--csv", type=Path, default=DAY_HIKES_CSV, help="Kurations-CSV")
        if name == "scan-day-hikes":
            p.add_argument("--region", help="nur diese Region neu scannen (Region-ID)")
    p = sub.add_parser("import-groups", help="Gruppenliste aus der Kurations-CSV importieren")
    p.add_argument("--csv", type=Path, default=GROUPS_CSV, help="Gruppen-CSV")
    args = parser.parse_args(argv)
    if args.command == "import-trails":
        return import_trails(args.only)
    if args.command == "import-shares":
        return import_shares_cmd(args.only)
    if args.command == "import-lodgings":
        return import_lodgings_cmd(args.pbf_dir)
    if args.command == "import-places":
        return import_places_cmd(args.pbf_dir)
    if args.command == "build-knowledge":
        return build_knowledge_cmd()
    if args.command == "smoke":
        return smoke_cmd()
    if args.command == "eval":
        return eval_cmd(
            _repo_path(args.cases) if args.cases else None, args.model, args.temperature
        )
    if args.command == "smoke-user":
        return smoke_user_cmd()
    if args.command == "prune-photos":
        return prune_photos_cmd()
    if args.command == "users-migrate":
        return users_migrate_cmd()
    if args.command == "admin-user":
        return admin_user_cmd()
    if args.command == "build-tags":
        return build_tags_cmd()
    if args.command == "import-photos":
        return import_photos_cmd(args.only)
    if args.command == "scan-day-hikes":
        return scan_day_hikes(_repo_path(args.csv), args.region)
    if args.command == "import-day-hikes":
        return import_day_hikes_cmd(_repo_path(args.csv))
    if args.command == "import-groups":
        return import_groups_cmd(_repo_path(args.csv))
    return 2


if __name__ == "__main__":
    sys.exit(main())
