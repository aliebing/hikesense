"""Smoke run against the real model: 6 fixed cases, expectations checked on the chat events.

`hikeall smoke` runs them with the real deps (see api.chat.default_deps_factory), writes a CSV and
exits 1 if an expectation is not met. Expectations are never loosened to make a case pass.
"""

from __future__ import annotations

import csv
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from hikeall.agent.graph import AgentDeps, ChatEvent, run_chat
from hikeall.agent.prompts import OTHER_REPLY
from hikeall.guard import INJECTION_REPLY

EXPECT_KINDS = {
    "min_results",
    "all_constraints_ok",
    "clarify_options_include",
    "fallback_single_violation",
    "activity",
    "no_duration_without_pace",
    "no_pace",
    "sources",
    "reply",
    "no_model_calls",
    "plan_days",
}
REPLIES = {"injection": INJECTION_REPLY, "other": OTHER_REPLY}
CSV_FIELDS = ["Fall", "ok", "unsupported", "cost_usd", "Fehler"]


@dataclass
class Turn:
    expect: dict[str, Any]
    message: str | None = None
    answer_option_containing: str | None = None


@dataclass
class Case:
    id: str
    turns: list[Turn]


@dataclass
class CaseResult:
    case: str
    ok: bool
    unsupported: int = 0
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)


def load_cases(path: Path) -> list[Case]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases: list[Case] = []
    for raw in data["cases"]:
        turns = []
        for i, t in enumerate(raw["turns"]):
            expect = t.get("expect") or {}
            unknown = set(expect) - EXPECT_KINDS
            if unknown:
                raise ValueError(f"{raw['id']}: unbekannte Erwartung {sorted(unknown)}")
            if expect.get("reply") not in (None, *REPLIES):
                raise ValueError(f"{raw['id']}: unbekannte Antwort '{expect['reply']}'")
            msg, opt = t.get("message"), t.get("answer_option_containing")
            if (msg is None) == (opt is None):
                raise ValueError(f"{raw['id']} Runde {i + 1}: genau eines von message/option")
            if opt is not None and i == 0:
                raise ValueError(f"{raw['id']}: erste Runde braucht eine message")
            turns.append(Turn(expect=expect, message=msg, answer_option_containing=opt))
        cases.append(Case(id=raw["id"], turns=turns))
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("doppelte Fall-IDs")
    return cases


def _first(events: list[ChatEvent], kind: str) -> Any | None:
    return next((e for e in events if e.type == kind), None)


def _text(events: list[ChatEvent]) -> str:
    return "".join(e.text for e in events if e.type == "token")


def check(events: list[ChatEvent], expect: dict[str, Any]) -> list[str]:
    """The unmet expectations of one turn (empty: all met)."""
    errors: list[str] = []
    results = _first(events, "results")
    cards = results.cards if results else []
    for e in events:
        if e.type == "error":
            errors.append(f"Fehler-Ereignis: {e.message}")
    for kind, want in expect.items():
        if kind == "min_results":
            if len(cards) < want:
                errors.append(f"{len(cards)} Treffer, erwartet mindestens {want}")
        elif kind == "all_constraints_ok":
            bad = [c.trail_id for c in cards if any(r.ok is not True for r in c.results)]
            if not cards or bad:
                errors.append(f"nicht alle Bedingungen erfüllt: {bad or 'keine Treffer'}")
        elif kind == "clarify_options_include":
            clarify = _first(events, "clarify")
            options = clarify.options if clarify else None
            if options is None:
                errors.append("keine Rückfrage")
            else:
                for part in want:
                    if not any(part in o for o in options):
                        errors.append(f"Rückfrage ohne Option mit „{part}“: {options}")
        elif kind == "fallback_single_violation":
            if not results or not results.fallback_reason:
                errors.append("kein fallback_reason")
            for c in cards if results and results.fallback_reason else []:
                n = sum(r.ok is False for r in c.results)
                if n != 1:
                    errors.append(f"{c.trail_id}: {n} verletzte Bedingungen statt genau 1")
            if results and results.fallback_reason and not cards:
                errors.append("keine Ausweichtouren")
        elif kind == "activity":
            u = _first(events, "understood")
            got = u.request.activity if u else None
            if got != want:
                errors.append(f"activity={got}, erwartet {want}")
        elif kind == "no_duration_without_pace":
            u = _first(events, "understood")
            if u is None:
                errors.append("keine Verständnis-Meldung")
            elif u.request.pace_min_per_km is None:
                timed = [c.trail_id for c in cards if c.duration_h is not None]
                if timed:
                    errors.append(f"Zeit ohne Tempo: {timed}")
        elif kind == "no_pace":
            u = _first(events, "understood")
            if u is None or u.request.pace_min_per_km is not None:
                got = u.request.pace_min_per_km if u else "keine Meldung"
                errors.append(f"Tempo gesetzt: {got}")
        elif kind == "sources":
            s = _first(events, "sources")
            if not (s and s.sources):
                errors.append("keine Quelle")
        elif kind == "reply":
            if _text(events) != REPLIES[want]:
                errors.append(f"Antwort ist nicht der feste Text '{want}'")
        elif kind == "plan_days":
            plan = _first(events, "plan")
            if plan is None:
                errors.append(f"kein Plan, erwartet {want} Tage")
            elif len(plan.plan.days) != want:
                errors.append(f"Plan mit {len(plan.plan.days)} Tagen, erwartet {want}")
        elif kind == "no_model_calls":
            d = _first(events, "done")
            if d is None:
                errors.append("kein done-Ereignis")
            elif d.usage.calls != 0 or d.usage.cost_usd:
                errors.append(f"{d.usage.calls} Modellaufrufe, Kosten {d.usage.cost_usd}")
    return errors


def run_case(deps: AgentDeps, case: Case) -> CaseResult:
    thread = f"smoke-{uuid.uuid4()}"
    res = CaseResult(case=case.id, ok=False)
    prev: list[ChatEvent] = []
    for turn in case.turns:
        message = turn.message
        if message is None:
            clarify = _first(prev, "clarify")
            part = turn.answer_option_containing or ""
            pick = [o for o in (clarify.options if clarify else []) if part in o]
            if not pick:
                res.errors.append(f"keine Option mit „{part}“ zum Antworten")
                return res
            message = pick[0]
        try:
            events = list(run_chat(deps, thread, message))
        except Exception as exc:  # noqa: BLE001 - one failing case must not stop the run
            res.errors.append(f"{type(exc).__name__}: {exc}")
            return res
        done = _first(events, "done")
        if done:
            res.unsupported += done.unsupported
            res.cost_usd += done.usage.cost_usd
        res.errors += check(events, turn.expect)
        prev = events
    if res.unsupported:
        res.errors.append(f"{res.unsupported} unbelegte Zahlen")
    res.ok = not res.errors
    return res


def run_all(deps: AgentDeps, cases: list[Case]) -> list[CaseResult]:
    return [run_case(deps, c) for c in cases]


def write_csv(path: Path, results: list[CaseResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for r in results:
            w.writerow(
                [r.case, str(r.ok).lower(), r.unsupported, f"{r.cost_usd:.6f}", "; ".join(r.errors)]
            )


def smoke(
    deps_factory: Callable[[], AgentDeps], prompts: Path, out_dir: Path, today: date | None = None
) -> int:
    cases = load_cases(prompts)
    results = run_all(deps_factory(), cases)
    out = out_dir / f"result-{(today or date.today()).isoformat()}.csv"
    write_csv(out, results)
    for r in results:
        errors = "; ".join(r.errors)
        print(f"{'ok  ' if r.ok else 'FAIL'} {r.case}" + (f": {errors}" if errors else ""))
    print(f"Kosten gesamt: {sum(r.cost_usd for r in results):.4f} USD -> {out}")
    return 0 if all(r.ok for r in results) else 1
