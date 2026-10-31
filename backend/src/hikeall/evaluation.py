"""Evaluation run: the eval cases (data/eval/cases.yaml) against the real model, with metrics
for the four SMART targets and a Markdown report under docs/evaluation/.

`hikeall eval` signs in as the smoke user like `hikeall smoke`, builds the real deps with the
STORED weather (`FixtureWeather`, data/eval/weather.json) and a fixed "today" (`EVAL_TODAY`), so
weather-dependent cases never ask Open-Meteo live. Expectations are checked by `smoke.check` and
are never loosened to make a case pass. Exit code 1 if any case fails.

Metrics (README and presentation use exactly these definitions):

- Number rate (target ≤ 2 % unsupported numbers): over every turn of every case,
  numerator = `DoneEvent.unsupported` (numbers the grounding check could not back up),
  denominator = numbers with a unit still in the answer text (`grounding.numbers_in_text`) PLUS
  `unsupported` – the replaced numbers stand as "?" in the text and are no longer found there.
- Invented tours (target 0 %): `tours_total` = distinct trail ids shown per case (result cards and
  plans of all turns), summed over cases; `unknown_tours` = those not in `select id from trails`.
  `names_unsupported` = tour names in the answer that do not occur in the round's results
  (`DoneEvent.unsupported_names`). The target is reached only if both counts are 0.
- Unsatisfiability named openly (target 100 %): `unsat_cases` = cases of group `unerfuellbar`;
  `unsat_named` = those whose LAST turn meets `unsatisfiable_named` (fallback_reason set and the
  answer starts with "Keine Tour erfüllt alle Wünsche").
- Recall@5 (target ≥ 0,8): `recall_cases` = cases of group `wissen` with a `sources_include`
  expectation; `recall_hits` = those where every such turn finds each wanted string in the id or
  url of one of the first five sources. A case without a sources event, or one that never ran,
  is a miss and stays in the denominator.
- OSM comparison (`osm_rows`): every distinct tour shown as a card (key = trail id) is compared
  three ways: length on the card, `trails.length_km` in the database, and the length of the
  stored OSM line (`ST_Length(geom::geography)/1000`); ascent: card vs `trails.ascent_m`. Every
  day of a multi-day plan (key = `<trail id> Tag <n> km <start>–<end>`, km as in the plan) is one
  row of its own: the walking length on the trail (`walk_km`; the access path `access_km` to a
  far lodging is shown separately and not compared) against the length of the line between the
  day's km positions (`ST_LineSubstring` on the line in metres, `geo.METRIC_SRID`, km / `trails.length_km`
  as fraction – the same measure the km positions are made with). A row deviates if the card/day length or the database
  length is more than `OSM_TOLERANCE` (2 %) away from the line length. One row per key.
- A target with denominator 0 is "nicht erreicht" (not measured is not reached).

Weather fixture lookup: a request (lat, lon) maps to the NEAREST stored place (great-circle
distance) if it lies within `FIXTURE_RADIUS_KM`; else, or if a requested date is missing, the
fixture raises `HikeAllError("keine Wetterdaten für …")`. That is not a `WeatherUnavailable`, so
the agent does not turn it into "Wetterdienst nicht erreichbar": the case fails with the message
and the run goes on with the next case. The stored places are the stage places of all
long-distance trails (stages ≤ ~30 km, so every point of a trail is within ~15–20 km of one).
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import Any

from hikeall.adapters.open_meteo import DayWeather, weather_text
from hikeall.agent.graph import AgentDeps
from hikeall.agent.grounding import numbers_in_text
from hikeall.errors import HikeAllError
from hikeall.geo import METRIC_SRID
from hikeall.smoke import (
    Case,
    CaseResult,
    _first,
    _text,
    check,
    load_cases,
    run_all,
)

__all__ = [
    "EVAL_TODAY",
    "OSM_TOLERANCE",
    "EvalResult",
    "FixtureWeather",
    "Metrics",
    "OsmRow",
    "compute_metrics",
    "evaluate",
    "numbers_in_text",
    "osm_rows",
    "run_eval",
    "write_report",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_PATH = REPO_ROOT / "data" / "eval" / "cases.yaml"
WEATHER_PATH = REPO_ROOT / "data" / "eval" / "weather.json"
OUT_DIR = REPO_ROOT / "docs" / "evaluation"
EVAL_TODAY = date(2026, 11, 2)  # the weather fixture starts here
FIXTURE_RADIUS_KM = 25.0
EARTH_RADIUS_KM = 6371.0
CSV_FIELDS = ["Fall", "group", "ok", "unsupported", "unsupported_names", "cost_usd", "Fehler"]
TRAIL_IDS_SQL = "select id from trails"

# SMART targets (spec §9), worded exactly as in the plan's Global Constraints
TARGET_TOURS = "0 % erfundene Touren"
TARGET_NUMBERS = "≤ 2 % nicht belegte Zahlen"
TARGET_UNSAT = "100 % offen benannte Unerfüllbarkeit"
TARGET_RECALL = "Recall@5 ≥ 0,8"
MAX_UNSUPPORTED_RATE = 0.02
MIN_RECALL = 0.8
OSM_TOLERANCE = 0.02
TRAIL_OSM_SQL = (
    "select length_km, ST_Length(geom::geography) / 1000, ascent_m from trails where id = %s"
)
# km positions are fractions of the line in metres times trails.length_km (geo.METRIC_SRID),
# so the section is cut with the same fractions and measured on the ellipsoid
SEGMENT_OSM_SQL = (
    "select ST_Length(ST_Transform(ST_LineSubstring(g, least(greatest(%(a)s / L, 0), 1), "
    "least(greatest(%(b)s / L, 0), 1)), 4326)::geography) / 1000 "
    f"from (select ST_Transform(geom, {METRIC_SRID}) as g, length_km as L "
    "from trails where id = %(id)s) t"
)


# --- stored weather ----------------------------------------------------------------------------


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class FixtureWeather:
    """Stored Open-Meteo daily values with the interface of OpenMeteoClient; never goes live."""

    def __init__(self, path: Path) -> None:
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.source: str = doc.get("source", "")
        self._places: list[tuple[str, float, float, dict[date, DayWeather]]] = [
            (p["name"], p["lat"], p["lon"], {w.date: w for w in map(_day, p["days"])})
            for p in doc["places"]
        ]

    def _place(self, lat: float, lon: float) -> dict[date, DayWeather]:
        best = min(self._places, key=lambda p: _km(lat, lon, p[1], p[2]), default=None)
        if best is None or _km(lat, lon, best[1], best[2]) > FIXTURE_RADIUS_KM:
            raise HikeAllError(
                f"keine Wetterdaten für {lat:.4f}, {lon:.4f} "
                f"(kein gespeicherter Ort ≤ {FIXTURE_RADIUS_KM:.0f} km)"
            )
        return best[3]

    def daily(self, lat: float, lon: float, start: date, end: date) -> list[DayWeather]:
        by_date = self._place(lat, lon)
        out = []
        for n in range((end - start).days + 1):
            day = date.fromordinal(start.toordinal() + n)
            if day not in by_date:
                raise HikeAllError(f"keine Wetterdaten für {day.isoformat()}")
            out.append(by_date[day])
        return out

    def daily_many(
        self, points: list[tuple[float, float]], start: date, end: date
    ) -> list[list[DayWeather]]:
        return [self.daily(lat, lon, start, end) for lat, lon in points]


def _day(raw: dict[str, Any]) -> DayWeather:
    code = raw.get("code")
    return DayWeather(
        date=date.fromisoformat(raw["date"]),
        code=code,
        text=weather_text(code),
        t_min_c=raw.get("t_min_c"),
        t_max_c=raw.get("t_max_c"),
        precip_mm=raw.get("precip_mm"),
        precip_prob_pct=raw.get("precip_prob_pct"),
    )


# --- results and metrics -----------------------------------------------------------------------


@dataclass
class EvalResult(CaseResult):
    """A smoke CaseResult (incl. `all_events`, every turn's events) plus the case's group and
    expectations per turn (for recall)."""

    group: str = ""
    expects: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Metrics:
    cases: int
    passed: int
    by_group: dict[str, tuple[int, int]]  # group -> (passed, total)
    numbers_total: int
    numbers_unsupported: int
    unknown_tours: int
    names_unsupported: int
    unsat_cases: int
    unsat_named: int
    recall_cases: int
    recall_hits: int
    cost_usd: float
    tours_total: int = 0


def run_eval(
    deps: AgentDeps | None, cases: list[Case], user_hash: str | None = None
) -> list[EvalResult]:
    by_id = {c.id: c for c in cases}
    out = []
    for r in run_all(deps, cases, user_hash):  # type: ignore[arg-type]
        case = by_id[r.case]
        base = {f.name: getattr(r, f.name) for f in fields(r)}
        out.append(
            EvalResult(**base, group=case.group or "", expects=[t.expect for t in case.turns])
        )
    return out


def _shown_tours(r: EvalResult) -> set[str]:
    ids: set[str] = set()
    for events in r.all_events:
        results, plan = _first(events, "results"), _first(events, "plan")
        ids |= {c.trail_id for c in (results.cards if results else [])}
        if plan is not None:
            ids.add(plan.plan.trail_id)
    return ids


def _recall_hit(r: EvalResult) -> bool:
    wanted = [(i, e["sources_include"]) for i, e in enumerate(r.expects) if "sources_include" in e]
    return all(
        i < len(r.all_events) and not check(r.all_events[i], {"sources_include": want})
        for i, want in wanted
    )


def compute_metrics(results: list[EvalResult], trail_ids: set[str] | None = None) -> Metrics:
    """Metrics as defined in the module docstring; `trail_ids` = ids in the trails table
    (None: tours are not checked against the database)."""
    by_group: dict[str, list[int]] = {}
    m = Metrics(0, 0, {}, 0, 0, 0, 0, 0, 0, 0, 0, 0.0)
    for r in results:
        m.cases += 1
        m.passed += r.ok
        g = by_group.setdefault(r.group, [0, 0])
        g[0] += r.ok
        g[1] += 1
        m.cost_usd += r.cost_usd
        for events in r.all_events:
            done = _first(events, "done")
            unsupported = done.unsupported if done else 0
            m.numbers_unsupported += unsupported
            m.numbers_total += len(numbers_in_text(_text(events))) + unsupported
            m.names_unsupported += len(done.unsupported_names) if done else 0
        shown = _shown_tours(r)
        m.tours_total += len(shown)
        if trail_ids is not None:
            m.unknown_tours += len(shown - trail_ids)
        if r.group == "unerfuellbar":
            m.unsat_cases += 1
            last = r.all_events[-1] if r.all_events else []
            m.unsat_named += not check(last, {"unsatisfiable_named": True})
        if r.group == "wissen" and any("sources_include" in e for e in r.expects):
            m.recall_cases += 1
            m.recall_hits += _recall_hit(r)
    m.by_group = {k: (v[0], v[1]) for k, v in by_group.items()}
    return m


# --- OSM comparison ----------------------------------------------------------------------------


@dataclass
class OsmRow:
    """One compared tour (key = trail id) or plan day (key = `<trail id> Tag <n> km <a>–<b>`).
    For a day, `db_km` is the line section too (the database has no per-day value), `db_hm` is
    None and `access_km` is the access path that is not part of the comparison."""

    trail_id: str
    answer_km: float
    db_km: float
    line_km: float
    answer_hm: int | None
    db_hm: int | None
    access_km: float = 0.0

    @property
    def deviates(self) -> bool:
        limit = OSM_TOLERANCE * self.line_km
        return abs(self.answer_km - self.line_km) > limit or abs(self.db_km - self.line_km) > limit


def _fmt_km(x: float) -> str:
    return f"{x:.1f}".replace(".", ",").removesuffix(",0")


def osm_rows(
    results: Sequence[CaseResult],
    lookup: Callable[[str], tuple[float, float, int | None] | None],
    segment_lookup: Callable[[str, float, float], float] | None = None,
) -> list[OsmRow]:
    """Rows as defined in the module docstring. `lookup(trail_id)` -> (db_km, line_km, db_hm) or
    None (unknown id: no row, `unknown_tours` counts it); `segment_lookup(trail_id, start_km,
    end_km)` -> line section km (None: plan days are not compared)."""
    rows: dict[str, OsmRow] = {}
    for r in results:
        for events in r.all_events:
            shown = _first(events, "results")
            for c in shown.cards if shown else []:
                found = None if c.trail_id in rows or c.length_km is None else lookup(c.trail_id)
                if found:
                    db_km, line_km, db_hm = found
                    rows[c.trail_id] = OsmRow(
                        c.trail_id, float(c.length_km), float(db_km), float(line_km),
                        c.ascent_m, db_hm,
                    )  # fmt: skip
            plan = _first(events, "plan")
            for d in plan.plan.days if plan and segment_lookup else []:
                tid = plan.plan.trail_id
                key = f"{tid} Tag {d.day} km {_fmt_km(d.start_km)}–{_fmt_km(d.end_km)}"
                if key not in rows:
                    line = float(segment_lookup(tid, d.start_km, d.end_km))  # type: ignore[misc]
                    rows[key] = OsmRow(
                        key, d.walk_km, line, line, d.ascent_m, None, access_km=d.access_km
                    )
    return list(rows.values())


def _osm_section(osm: Sequence[OsmRow]) -> list[str]:
    bad = [o for o in osm if o.deviates]
    lines = [
        "## Abgleich mit OSM",
        "",
        (
            f"{len(osm)} Touren verglichen (Tourkarten und Mehrtagesplan-Tage; Karte gegen "
            f"Datenbank gegen gespeicherte OSM-Linie), {len(bad)} mit Abweichung > "
            f"{OSM_TOLERANCE * 100:.0f} %."
        ),
        "",
    ]
    if bad:
        lines += [
            "| Tour | Antwort km | Datenbank km | OSM-Linie km | Zuweg km | Antwort hm | DB hm |",
            "|---|---|---|---|---|---|---|",
        ]

        def n(v: int | None) -> str:
            return "–" if v is None else str(v)

        lines += [
            f"| {o.trail_id} | {_fmt_km(o.answer_km)} | {_fmt_km(o.db_km)} | "
            f"{_fmt_km(o.line_km)} | {_fmt_km(o.access_km)} | {n(o.answer_hm)} | {n(o.db_hm)} |"
            for o in bad
        ]
        lines.append("")
    return lines


# --- report ------------------------------------------------------------------------------------


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:.1f} %".replace(".", ",")


def _targets(m: Metrics) -> list[tuple[str, str, bool]]:
    """(target, actual value, reached) per SMART target."""
    tours = (
        f"{_pct(m.unknown_tours, m.tours_total) if m.tours_total else 'keine Touren gezeigt'} "
        f"({m.unknown_tours} von {m.tours_total} Tour-IDs nicht in der Datenbank, "
        f"{m.names_unsupported} unbelegte Tournamen im Text)"
    )
    if m.numbers_total:
        numbers = f"{_pct(m.numbers_unsupported, m.numbers_total)} ({m.numbers_unsupported} von "
        numbers += f"{m.numbers_total} Zahlen)"
    else:
        numbers = "keine Zahlen in den Antworten"
    unsat = (
        f"{_pct(m.unsat_named, m.unsat_cases)} ({m.unsat_named} von {m.unsat_cases} Fällen)"
        if m.unsat_cases
        else "keine Fälle"
    )
    recall = (
        f"{m.recall_hits / m.recall_cases:.2f} ({m.recall_hits} von {m.recall_cases} Fällen)"
        .replace(".", ",")
        if m.recall_cases
        else "keine Fälle"
    )  # fmt: skip
    return [
        (
            TARGET_TOURS,
            tours,
            m.tours_total > 0 and m.unknown_tours == 0 and m.names_unsupported == 0,
        ),
        (
            TARGET_NUMBERS,
            numbers,
            m.numbers_total > 0 and m.numbers_unsupported <= MAX_UNSUPPORTED_RATE * m.numbers_total,
        ),
        (TARGET_UNSAT, unsat, m.unsat_cases > 0 and m.unsat_named == m.unsat_cases),
        (
            TARGET_RECALL,
            recall,
            m.recall_cases > 0 and m.recall_hits >= MIN_RECALL * m.recall_cases,
        ),
    ]


def write_report(
    path: Path,
    metrics: Metrics,
    results: Sequence[CaseResult],
    model: str,
    osm: Sequence[OsmRow],
    day: date | None = None,
) -> None:
    m = metrics
    lines = [
        f"# Evaluation {model} – {(day or date.today()).isoformat()}",
        "",
        f"- Modell: `{model}`",
        (
            f"- Datum des Laufs: {(day or date.today()).isoformat()}; festes „heute“ im Chat: "
            f"{EVAL_TODAY.isoformat()} (Wetter aus data/eval/weather.json, Open-Meteo.com, "
            "CC BY 4.0)"
        ),
        f"- Fälle: {m.passed} / {m.cases} bestanden",
        f"- Gesamtkosten: {m.cost_usd:.4f} USD".replace(".", ","),
        "",
        "## SMART-Ziele",
        "",
        "| Ziel | Ist-Wert | Ergebnis |",
        "|---|---|---|",
        *[
            f"| {name} | {actual} | {'erreicht' if ok else 'nicht erreicht'} |"
            for name, actual, ok in _targets(m)
        ],
        "",
        "## Gruppen",
        "",
        "| Gruppe | bestanden / gesamt |",
        "|---|---|",
        *[f"| {g} | {p} / {n} |" for g, (p, n) in m.by_group.items()],
        "",
        *_osm_section(osm),
        "## Nicht bestandene Fälle",
        "",
    ]
    failed = [r for r in results if not r.ok]
    lines += [f"- {r.case}: {'; '.join(r.errors) or 'ohne Fehlertext'}" for r in failed] or [
        "Keine."
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, results: Sequence[EvalResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for r in results:
            w.writerow(
                [
                    r.case,
                    r.group,
                    str(r.ok).lower(),
                    r.unsupported,
                    "; ".join(r.unsupported_names),
                    f"{r.cost_usd:.6f}",
                    "; ".join(r.errors),
                ]
            )


# --- run ---------------------------------------------------------------------------------------


def _slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def _db_trail_ids(deps: AgentDeps) -> set[str]:
    from hikeall.db import connect

    with connect(deps.settings.supabase_db_url) as conn:
        return {row[0] for row in conn.execute(TRAIL_IDS_SQL)}


def _osm_lookups(
    deps: AgentDeps,
) -> tuple[
    Callable[[str], tuple[float, float, int | None] | None], Callable[[str, float, float], float]
]:
    from hikeall.db import connect

    conns: list[Any] = []  # opened on the first lookup: a run without tours needs no database

    class _Conn:
        def execute(self, *a: Any) -> Any:
            if not conns:
                conns.append(connect(deps.settings.supabase_db_url))
            return conns[0].execute(*a)

    conn = _Conn()

    def lookup(trail_id: str) -> tuple[float, float, int | None] | None:
        row = conn.execute(TRAIL_OSM_SQL, (trail_id,)).fetchone()
        if row is None or row[0] is None or row[1] is None:
            return None
        return float(row[0]), float(row[1]), row[2]

    def segment(trail_id: str, a: float, b: float) -> float:
        row = conn.execute(SEGMENT_OSM_SQL, {"id": trail_id, "a": a, "b": b}).fetchone()
        return float(row[0])

    return lookup, segment


def evaluate(
    deps_factory: Callable[[], AgentDeps],
    cases_path: Path,
    out_dir: Path,
    today: date | None = None,
    user_hash: str | None = None,
    trail_ids: set[str] | None = None,
    osm_lookups: tuple[Any, Any] | None = None,
) -> int:
    """Runs the eval cases and writes results-<date>-<model>.csv and bericht-<date>-<model>.md
    to `out_dir`; `today` = run date for file names and report (the chat itself always sees
    EVAL_TODAY). `trail_ids` None: read from the database; `osm_lookups` = (lookup, segment_lookup) for
    `osm_rows`, None: SQL on the database. Returns 1 if a case failed."""
    cases = load_cases(cases_path, require_group=True)
    deps = deps_factory()
    deps.today = lambda: EVAL_TODAY
    results = run_eval(deps, cases, user_hash)
    metrics = compute_metrics(results, _db_trail_ids(deps) if trail_ids is None else trail_ids)
    day, model = today or date.today(), deps.settings.hikeall_model
    stem = f"{day.isoformat()}-{_slug(model)}"
    csv_path, report = out_dir / f"results-{stem}.csv", out_dir / f"bericht-{stem}.md"
    write_csv(csv_path, results)
    lookup, segment = osm_lookups or _osm_lookups(deps)
    write_report(report, metrics, results, model, osm_rows(results, lookup, segment), day=day)
    for r in results:
        errors = "; ".join(r.errors)
        print(f"{'ok  ' if r.ok else 'FAIL'} {r.case}" + (f": {errors}" if errors else ""))
    print(f"{metrics.passed}/{metrics.cases} bestanden, Kosten {metrics.cost_usd:.4f} USD")
    print(f"Ergebnisse -> {csv_path}\nBericht -> {report}")
    return 0 if all(r.ok for r in results) else 1
