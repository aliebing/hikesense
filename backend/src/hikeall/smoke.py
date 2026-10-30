"""Smoke run against the real model: fixed cases, expectations checked on the chat events.

`hikeall smoke` signs in as the smoke user (`make smoke-user`), checks the access token like
POST /chat does, runs the cases with the real deps (see api.chat.default_deps_factory), writes a
CSV and exits 1 if an expectation is not met. Expectations are never loosened to make a case pass.
"""

from __future__ import annotations

import csv
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml

from hikeall.adapters.http import make_http_client
from hikeall.agent.events import FIELDS
from hikeall.agent.graph import AgentDeps, ChatEvent, run_chat
from hikeall.agent.multiday import FAR_M, NEAR_M
from hikeall.agent.prompts import OTHER_REPLY
from hikeall.auth import AuthError, verify_token
from hikeall.chatlog import hash_user
from hikeall.config import Settings
from hikeall.errors import HikeAllError
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
    "plan_lodgings_near",
    "plan_band_or_named",
    "days_unchanged",
    "day_shorter",
    "min_groups",
    "no_groups",
    "events_quoted",
}
REPLIES = {"injection": INJECTION_REPLY, "other": OTHER_REPLY}
CSV_FIELDS = ["Fall", "ok", "unsupported", "cost_usd", "Fehler"]
SMOKE_EMAIL = "smoke@hikeall.local"
NO_GROUP_TEXT = "keine Gruppe"
AUTH_TIMEOUT_S = 10.0


class SmokeAuthError(HikeAllError):
    """The smoke user could not be signed in or its token was rejected."""


@dataclass
class Turn:
    expect: dict[str, Any]
    message: str | None = None
    answer_option_containing: str | None = None


@dataclass
class Case:
    id: str
    turns: list[Turn]
    continues: str | None = None  # id of an earlier case whose thread this one continues


@dataclass
class CaseResult:
    case: str
    ok: bool
    unsupported: int = 0
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    thread: str = ""
    last: list[ChatEvent] = field(default_factory=list, repr=False)  # events of the last turn


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
        cont = raw.get("continues")
        if cont is not None and cont not in {c.id for c in cases}:
            raise ValueError(f"{raw['id']}: continues '{cont}' ist kein früherer Fall")
        cases.append(Case(id=raw["id"], turns=turns, continues=cont))
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("doppelte Fall-IDs")
    return cases


def _first(events: list[ChatEvent], kind: str) -> Any | None:
    return next((e for e in events if e.type == kind), None)


def _text(events: list[ChatEvent]) -> str:
    return "".join(e.text for e in events if e.type == "token")


def _plan_days(events: list[ChatEvent] | None) -> list[Any] | None:
    plan = _first(events or [], "plan")
    return plan.plan.days if plan else None


def _lodging_errors(events: list[ChatEvent]) -> list[str]:
    """Each day ends at a lodging <= 1000 m, or the access path (<= 2000 m) or the gap is named;
    only the last day may end without a lodging (the trail end)."""
    plan = _first(events, "plan")
    if plan is None:
        return ["kein Plan"]
    days, notes = plan.plan.days, plan.plan.notes
    errors = []
    for d in days:
        if d.gap:
            continue
        if d.stop is None:
            if d is not days[-1]:
                errors.append(f"Tag {d.day} endet ohne Unterkunft vor dem Wegende")
        elif d.stop.dist_m > FAR_M:
            errors.append(f"Tag {d.day}: Unterkunft {d.stop.dist_m} m vom Weg, keine Lücke genannt")
        elif d.stop.dist_m > NEAR_M and not (
            d.access_km > 0
            and any(
                f"Unterkunft {d.stop.name or 'ohne Namen'} " in n and "Zuweg" in n for n in notes
            )
        ):
            errors.append(f"Tag {d.day}: Unterkunft {d.stop.dist_m} m vom Weg, Zuweg nicht genannt")
    return errors


def _band_errors(events: list[ChatEvent]) -> list[str]:
    """Each day within +-20 % of the target, or its gap is in the answer text."""
    days = _plan_days(events)
    if days is None:
        return ["kein Plan"]
    text = _text(events)
    return [
        f"Tag {d.day}: {d.length_km} km außerhalb des Bands, nicht benannt"
        for d in days
        if not d.within_band and not (d.gap and d.gap.split(";")[0] in text)
    ]


def _change_errors(
    events: list[ChatEvent], prev: list[ChatEvent] | None, unchanged: list[int], shorter: int | None
) -> list[str]:
    before, after = _plan_days(prev), _plan_days(events)
    if before is None or after is None:
        return ["kein Plan zum Vergleichen" if before is None else "kein geänderter Plan"]
    errors = []
    for n in unchanged:
        if n > min(len(before), len(after)) or before[n - 1] != after[n - 1]:
            errors.append(f"Tag {n} verändert")
    if shorter is not None:
        if shorter > min(len(before), len(after)):
            errors.append(f"Tag {shorter} fehlt")
        elif not after[shorter - 1].length_km < before[shorter - 1].length_km:
            old, new = before[shorter - 1].length_km, after[shorter - 1].length_km
            errors.append(f"Tag {shorter} nicht kürzer ({old} -> {new} km)")
    return errors


def _event_errors(events: list[ChatEvent]) -> list[str]:
    """Races with every given field quoted, or calendar links; never a field without a quote."""
    ev = _first(events, "events")
    if ev is None:
        return ["keine Lauf-Antwort"]
    if not ev.events and not ev.fallback:
        return ["weder Läufe noch Kalender-Links"]
    return [
        f"{race.source_url}: Feld {name} ohne Zitat"
        for race in ev.events
        for name in FIELDS
        if getattr(race, name).value is not None and not (getattr(race, name).quote or "").strip()
    ]


def check(
    events: list[ChatEvent], expect: dict[str, Any], prev: list[ChatEvent] | None = None
) -> list[str]:
    """The unmet expectations of one turn (empty: all met); `prev` = the thread's previous turn."""
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
        elif kind == "plan_lodgings_near":
            errors += _lodging_errors(events)
        elif kind == "plan_band_or_named":
            errors += _band_errors(events)
        elif kind == "days_unchanged":
            errors += _change_errors(events, prev, want, None)
        elif kind == "day_shorter":
            errors += _change_errors(events, prev, [], want)
        elif kind == "min_groups":
            g = _first(events, "groups")
            n = len(g.groups) if g else 0
            if n < want:
                errors.append(f"{n} Gruppen, erwartet mindestens {want}")
            elif not g.checked_note.startswith("Stand: "):
                errors.append(f"kein Prüfdatum: '{g.checked_note}'")
        elif kind == "no_groups":
            g = _first(events, "groups")
            if g and g.groups:
                errors.append(f"Gruppen gezeigt: {[x.name for x in g.groups]}")
            if NO_GROUP_TEXT not in _text(events):
                errors.append(f"Antwort ohne „{NO_GROUP_TEXT}“")
        elif kind == "events_quoted":
            errors += _event_errors(events)
        elif kind == "no_model_calls":
            d = _first(events, "done")
            if d is None:
                errors.append("kein done-Ereignis")
            elif d.usage.calls != 0 or d.usage.cost_usd:
                errors.append(f"{d.usage.calls} Modellaufrufe, Kosten {d.usage.cost_usd}")
    return errors


def run_case(
    deps: AgentDeps,
    case: Case,
    user_hash: str | None = None,
    thread: str | None = None,
    prev: list[ChatEvent] | None = None,
) -> CaseResult:
    """Runs the turns of one case; `thread`/`prev` continue an earlier case's conversation."""
    thread = thread or f"smoke-{uuid.uuid4()}"
    res = CaseResult(case=case.id, ok=False, thread=thread)
    prev = prev or []
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
            events = list(run_chat(deps, thread, message, user_hash))
        except Exception as exc:  # noqa: BLE001 - one failing case must not stop the run
            res.errors.append(f"{type(exc).__name__}: {exc}")
            return res
        done = _first(events, "done")
        if done:
            res.unsupported += done.unsupported
            res.cost_usd += done.usage.cost_usd
        res.errors += check(events, turn.expect, prev)
        prev = events
        res.last = events
    if res.unsupported:
        res.errors.append(f"{res.unsupported} unbelegte Zahlen")
    res.ok = not res.errors
    return res


def run_all(deps: AgentDeps, cases: list[Case], user_hash: str | None = None) -> list[CaseResult]:
    done: dict[str, CaseResult] = {}
    out = []
    for c in cases:
        if c.continues is not None and c.continues not in done:
            out.append(CaseResult(case=c.id, ok=False, errors=[f"Fall {c.continues} lief nicht"]))
            continue
        before = done.get(c.continues or "")
        r = run_case(
            deps, c, user_hash, before.thread if before else None, before.last if before else None
        )
        done[c.id] = r
        out.append(r)
    return out


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
    deps_factory: Callable[[], AgentDeps],
    prompts: Path,
    out_dir: Path,
    today: date | None = None,
    user_hash: str | None = None,
) -> int:
    cases = load_cases(prompts)
    results = run_all(deps_factory(), cases, user_hash)
    out = out_dir / f"result-{(today or date.today()).isoformat()}.csv"
    write_csv(out, results)
    for r in results:
        errors = "; ".join(r.errors)
        print(f"{'ok  ' if r.ok else 'FAIL'} {r.case}" + (f": {errors}" if errors else ""))
    print(f"Kosten gesamt: {sum(r.cost_usd for r in results):.4f} USD -> {out}")
    return 0 if all(r.ok for r in results) else 1


# --- smoke user: local Supabase auth ---------------------------------------------------------


def _auth_call(http: httpx.Client, settings: Settings, path: str, **params: str) -> httpx.Response:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise SmokeAuthError("SUPABASE_URL und SUPABASE_ANON_KEY in .env eintragen")
    if settings.hikeall_smoke_password is None:
        raise SmokeAuthError("HIKEALL_SMOKE_PASSWORD in .env eintragen")
    body = {"email": SMOKE_EMAIL, "password": settings.hikeall_smoke_password.get_secret_value()}
    try:
        return http.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/{path}",
            params=params,
            headers={"apikey": settings.supabase_anon_key},
            json=body,
            timeout=AUTH_TIMEOUT_S,
        )
    except httpx.HTTPError as exc:
        raise SmokeAuthError(f"Supabase-Auth nicht erreichbar ({type(exc).__name__})") from exc


def sign_in(http: httpx.Client, settings: Settings) -> str:
    """Access token of the smoke user (password grant)."""
    r = _auth_call(http, settings, "token", grant_type="password")
    token = r.json().get("access_token") if r.status_code == 200 else None
    if not isinstance(token, str) or not token:
        raise SmokeAuthError(
            f"Anmeldung als {SMOKE_EMAIL} fehlgeschlagen (HTTP {r.status_code}) – "
            "erst `make smoke-user` ausführen"
        )
    return token


def create_user(http: httpx.Client, settings: Settings) -> str:
    """Signs the smoke user up ("angelegt") or confirms an existing one can sign in
    ("vorhanden"). Local Supabase confirms e-mail addresses automatically."""
    r = _auth_call(http, settings, "signup")
    if r.status_code == 200:
        return "angelegt"
    if r.status_code in (400, 422) and "already" in r.text:
        sign_in(http, settings)  # an existing user with a different password fails here
        return "vorhanden"
    raise SmokeAuthError(f"Konto {SMOKE_EMAIL} nicht angelegt (HTTP {r.status_code})")


def authorize(settings: Settings) -> str:
    """Signs in and checks the token exactly like POST /chat; returns the hashed user id that
    /chat passes to the graph (the e-mail and the id itself never go further)."""
    with make_http_client(AUTH_TIMEOUT_S) as http:
        token = sign_in(http, settings)
    try:
        user = verify_token(token, settings)
    except AuthError as exc:
        raise SmokeAuthError(f"Anmeldung: Token abgelehnt ({exc.reason})") from exc
    return hash_user(user.user_id)
