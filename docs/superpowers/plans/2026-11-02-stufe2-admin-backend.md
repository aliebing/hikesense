# Stufe 2: Admin-Backend – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Admin sieht unter `/admin` jede Suche aus `data/logs/chat.jsonl` mit Suchtext, verstandener Anfrage, Antwort, Begründung je Tour (gezeigt / Ausweich / verworfen), Tool-Aufrufen, Prompts, Tokens, Kosten und Dauer – nach Benutzer gefiltert.

**Architecture:** Ein pro Anfrage laufender Trace (ContextVar, wie `llm/usage.metered`) sammelt LLM-Aufrufe (Gateway) und Tool-Aufrufe (Proxy um `AgentTools`). Der `log`-Knoten des Graphen schreibt Trace, Suchtext, verstandene Anfrage, Antwort und die Kandidaten-Begründung zusätzlich in die bestehende JSONL-Zeile. Ein Leser (`admin_log.py`) ordnet Zeilen Profilen zu (`user_id`, sonst `user_hash`), drei Admin-Endpunkte liefern Benutzer, Suchenliste und Detail, und die Next-Seite `/admin` zeigt sie im Layout A mit Tabelle.

**Tech Stack:** FastAPI, LangGraph, psycopg, pydantic, pytest (backend, `uv run pytest`); Next.js app router, React, Tailwind, Vitest (web, `npx vitest run`).

**Spec:** `docs/superpowers/specs/2026-11-02-rollen-backend-regionen-wetter-design.md`, Abschnitt „Stufe 2: Admin-Backend“ und „Für alle Stufen“. Entwurf des Layouts: `.superpowers/brainstorm/133811-1793610352/content/backend-layout-v2.html`.

**Branch:** `stufe2-admin-backend` von `main`.

## Global Constraints

- Oberfläche und Fehlertexte deutsch; Stil wie bestehende Seiten (`PageFrame`, `schrift-feld`, `bg-papier/95`, `text-wald-dunkel`).
- Kosten nur wie von OpenRouter gemeldet (`usage.cost`); fehlende Kosten als „–“, nie geschätzt.
- Nur Admin: jeder `/admin/*`-Endpunkt antwortet ohne Login 401, ohne Admin-Rolle 403 `{"detail":"Kein Zugriff"}`, bei DB-Fehler der Rollenprüfung 503 – vor jedem Lesen des Logs.
- Der Log enthält nie Passwörter, JWTs oder API-Keys und nie Exception-Meldungstexte (nur Klassennamen, wie bisher).
- Eine Log-Zeile bleibt eine Anfrage; alle bisherigen Felder bleiben mit gleichem Namen und Typ.
- Keine neue Datenbanktabelle; keine Bearbeitung von Benutzern/Rollen; keine Grafiken.
- Verworfene Kandidaten: höchstens **20** je Suche.
- Desktop-Layout genügt.

## Review Focus

1. **Alte Log-Zeilen** (ohne `message`, `llm_calls`, `candidates` …) – Liste und Detail zeigen sie ohne Absturz; fehlende Werte als „–“, Detail mit Hinweis „Ältere Suche – nur Kennzahlen gespeichert“. Test in Task 4 und Task 6.
2. **Kaputte oder halb geschriebene Zeile** (gleichzeitiges Schreiben, Abbruch) – wird übersprungen, kein 500. Test in Task 4.
3. **Log-Datei fehlt** (frische Installation) – leere Listen, Benutzer mit 0 Suchen, kein 500. Test in Task 4.
4. **Nicht-Admin oder ohne Login fragt ein Detail direkt an** (`/admin/searches/<id>`) – 403/401 ohne jeden Logwert in der Antwort; unbekannte `request_id` → 404. Test in Task 5.
5. **Riesige Tool-Ergebnisse** (Wissenssuche, Mehrtagesplan) – im Log auf 20.000 Zeichen gekürzt mit `truncated: true`, in der Seite 300 Zeichen Vorschau und aufklappbar. Test in Task 1 und Task 6.

---

### Task 1: Trace pro Anfrage – LLM- und Tool-Aufrufe aufzeichnen

**Files:**
- Create: `backend/src/hikeall/trace.py`
- Modify: `backend/src/hikeall/llm/usage.py` (Helfer `call_usage`)
- Modify: `backend/src/hikeall/llm/gateway.py` (`OpenRouterGateway` und `FakeGateway` zeichnen auf)
- Test: `backend/tests/test_trace.py`

**Interfaces:**
- Produces:
  - `call_usage(message: Any) -> tuple[int, int, float | None]` in `llm/usage.py` – Eingabe-Tokens, Ausgabe-Tokens, gemeldete Kosten (None wenn nicht gemeldet). `record_usage` nutzt ihn (Verhalten unverändert).
  - In `trace.py`:
    - `TOOL_RESULT_MAX_CHARS = 20_000`
    - `@dataclass class Trace: started: float (time.monotonic()); llm_calls: list[dict]; tool_calls: list[dict]` (Listen default leer)
    - `@contextmanager def traced() -> Iterator[Trace]` (ContextVar setzen/zurücksetzen wie `metered`)
    - `def current() -> Trace | None`
    - `def record_llm(step: str, model: str | None, messages: list[dict], output: Any, reply: Any, duration_ms: int) -> None` – no-op ohne aktiven Trace. Hängt an: `{"step", "model", "messages", "output", "input_tokens", "output_tokens", "cost_usd", "duration_ms"}`; Tokens/Kosten über `call_usage(reply)`.
    - `def message_dicts(messages: Sequence[BaseMessage]) -> list[dict]` – je Nachricht `{"role": "system"|"user"|"assistant"|"tool", "content": str}`, bei AIMessage mit Tool-Aufrufen zusätzlich `"tool_calls": [{"name", "args"}]`.
    - `def to_jsonable(obj: Any) -> Any` – pydantic → `model_dump(mode="json")`, Dataclass → `asdict`, `set` → sortierte Liste, `date/time` → ISO-String, rekursiv; Unbekanntes → `str(obj)`.
    - `class TracedTools:` – `__init__(self, inner: Any)`; `__getattr__(name)` liefert für aufrufbare öffentliche Attribute einen Wrapper, der aufruft und (bei aktivem Trace) anhängt: `{"name", "args": to_jsonable(kwargs + positionale als "arg0", "arg1" …), "result": <JSON-Text, gekürzt>, "truncated": bool, "duration_ms": int, "error": str | None}`. Bei Exception: `error = type(exc).__name__`, `result = None`, dann weiterwerfen. Nicht-aufrufbare Attribute werden unverändert durchgereicht.
- Step-Namen der LLM-Aufrufe (fest): `structured` mit Schema `RawRequest` → `"understand"`, sonst `"structured:<SchemaName>"`; `answer` → `"answer"`; `tool_round` → `"react"`; `web_completion` → `"web_search"`.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_trace.py`

```python
def test_record_llm_without_trace_is_noop():
    trace.record_llm("answer", "m", [], "x", None, 1)  # no error, nothing to see

def test_traced_collects_llm_call_with_usage():
    reply = AIMessage(content="Hallo", usage_metadata={"input_tokens": 10, "output_tokens": 3, "total_tokens": 13},
                      response_metadata={"token_usage": {"cost": 0.0012}})
    with trace.traced() as t:
        trace.record_llm("answer", "gpt-x", [{"role": "user", "content": "hi"}], "Hallo", reply, 42)
    assert t.llm_calls == [{"step": "answer", "model": "gpt-x", "messages": [{"role": "user", "content": "hi"}],
                            "output": "Hallo", "input_tokens": 10, "output_tokens": 3, "cost_usd": 0.0012, "duration_ms": 42}]

def test_cost_missing_stays_none():
    reply = AIMessage(content="x", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
    with trace.traced() as t:
        trace.record_llm("answer", None, [], "x", reply, 0)
    assert t.llm_calls[0]["cost_usd"] is None

def test_traced_tools_records_call_and_result():
    class T:
        def add(self, a, b=0): return {"sum": a + b}
    with trace.traced() as t:
        assert trace.TracedTools(T()).add(1, b=2) == {"sum": 3}
    call = t.tool_calls[0]
    assert call["name"] == "add" and call["args"] == {"arg0": 1, "b": 2}
    assert json.loads(call["result"]) == {"sum": 3} and call["truncated"] is False and call["error"] is None

def test_traced_tools_truncates_large_result():
    class T:
        def big(self): return "x" * 50_000
    with trace.traced() as t:
        trace.TracedTools(T()).big()
    assert len(t.tool_calls[0]["result"]) == trace.TOOL_RESULT_MAX_CHARS and t.tool_calls[0]["truncated"] is True

def test_traced_tools_records_error_class_and_reraises():
    class T:
        def bad(self): raise ValueError("geheim")
    with trace.traced() as t, pytest.raises(ValueError):
        trace.TracedTools(T()).bad()
    assert t.tool_calls[0]["error"] == "ValueError" and "geheim" not in json.dumps(t.tool_calls)

def test_to_jsonable_handles_sets_dates_dataclasses():
    assert trace.to_jsonable({"t": {"b", "a"}, "d": date(2026, 11, 2)}) == {"t": ["a", "b"], "d": "2026-11-02"}

def test_fake_gateway_records_steps():
    gw = FakeGateway(structured={RawRequest: [RawRequest(intent="other")]}, answers=["A"])
    with trace.traced() as t:
        gw.structured(RawRequest, "SYS", "USER")
        gw.answer("SYS2", "USER2")
    assert [c["step"] for c in t.llm_calls] == ["understand", "answer"]
    assert t.llm_calls[0]["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]
    assert t.llm_calls[1]["output"] == "A"
```

(`RawRequest(intent="other")` – falls das Modell weitere Pflichtfelder hat, die minimal gültige Instanz bauen, wie in `tests/test_agent_graph.py`.)

- [ ] **Step 2: Run** `cd backend && uv run pytest tests/test_trace.py -q` – Expected: FAIL (module `hikeall.trace` fehlt).

- [ ] **Step 3: Implement** `trace.py`, `call_usage` und das Aufzeichnen im Gateway.
  - `OpenRouterGateway`: in `structured`, `answer`, `tool_round`, `web_completion` Zeit messen (`time.monotonic()`), nach `record_usage` `trace.record_llm(...)` mit `model.model_name`. Output: `structured` → `parsed.model_dump(mode="json")` (bei ungültiger Ausgabe nicht aufzeichnen, Exception bleibt); `answer` → Text; `tool_round` → `{"content": text, "tool_calls": [{"name","args"}]}`; `web_completion` → `data["choices"][0]["message"]["content"]` falls vorhanden, sonst `None`; Nachrichten bei `web_completion`: `[{"role":"user","content": user}]`.
  - `FakeGateway`: dieselben Steps, `model="fake"`, `reply=None` (Tokens 0, Kosten None), `duration_ms=0`; Exceptions aus der Queue werden nicht aufgezeichnet.
  - Aufzeichnen darf nie die Anfrage abbrechen: Fehler in `record_llm` werden geloggt (`log.exception`) und verschluckt.

- [ ] **Step 4: Run** `uv run pytest tests/test_trace.py tests/test_llm.py -q` – Expected: PASS.

- [ ] **Step 5: Commit** `git commit -m "feat: Trace je Anfrage – LLM- und Tool-Aufrufe"`

---

### Task 2: Begründung je Kandidat (gezeigt / Ausweich / verworfen)

**Files:**
- Modify: `backend/src/hikeall/agent/constraints.py` (`Selection.rejected`)
- Create: `backend/src/hikeall/agent/explain.py`
- Test: `backend/tests/test_constraints.py`, `backend/tests/test_explain.py`

**Interfaces:**
- Produces:
  - `MAX_REJECTED = 20` in `constraints.py`.
  - `Selection.rejected: list[Scored] = field(default_factory=list)` (letztes Feld, Default; bestehende Konstruktoren bleiben gültig). `select()` füllt es mit allen bewerteten Kandidaten, die weder in `matches` noch in `fallbacks` landen, sortiert nach `(Anzahl Ergebnisse mit ok is not True, Summe deviation_rel der ok is False, -preference.score, distance_km, trail_id)`, gekürzt auf `MAX_REJECTED`. Bei Widerspruch bleibt es leer. Überzählige Treffer (mehr als `MAX_MATCHES`) gehören zu `rejected`.
  - `candidate_rows(sel: Selection) -> list[dict]` in `explain.py`. Reihenfolge: matches, dann fallbacks, dann rejected. Jede Zeile:
    `{"trail_id", "name", "status": "shown"|"fallback"|"rejected", "note": str|None, "distance_km", "length_km", "ascent_m", "roundtrip", "duration_h", "score", "met": [...], "missing": [...], "avoided": [...], "results": [{"kind", "ok", "actual", "bound"}]}`
    - `note` für `fallback`: `format_deviation(violated)`; für `rejected` mit allen Bedingungen erfüllt: `f"nur die besten {MAX_MATCHES} gezeigt"`; für `rejected` sonst: `"; ".join(format_deviation(r) for r in results if r.ok is not True)`; `shown`: None.
    - Zahlen auf 1 Nachkommastelle gerundet (`score` auf 2), `ok` bleibt `True/False/None`.

- [ ] **Step 1: Write the failing tests**
  - `test_constraints.py::test_rejected_holds_the_rest_sorted_and_capped` – 30 Kandidaten, 2 passen, alle anderen verletzen 1–2 Bedingungen: `len(sel.matches) == 2`, `len(sel.rejected) == 20`, alle mit genau einer verletzten Bedingung stehen vor denen mit zwei, kein `trail_id` doppelt über matches+rejected.
  - `test_constraints.py::test_rejected_includes_matches_beyond_max` – 7 passende Kandidaten: `len(sel.matches) == 5`, die 2 übrigen in `sel.rejected`.
  - `test_constraints.py::test_rejected_empty_on_contradiction`.
  - `test_explain.py::test_rows_status_and_notes` – eine Auswahl mit Ausweich (keine matches) und verworfenen: erster Status `"fallback"` mit `note == format_deviation(violated)`, ein verworfener mit Länge 22,3 statt höchstens 15 hat `note` mit `"22,3 km statt"`; `results[0] == {"kind": "length_km", "ok": False, "actual": 22.3, "bound": ...}`.
  - `test_explain.py::test_rows_note_for_surplus_match` – `"nur die besten 5 gezeigt"`.

- [ ] **Step 2: Run** `uv run pytest tests/test_constraints.py tests/test_explain.py -q` – Expected: FAIL.
- [ ] **Step 3: Implement** `Selection.rejected`, `MAX_REJECTED`, `candidate_rows`.
- [ ] **Step 4: Run** `uv run pytest tests/test_constraints.py tests/test_explain.py tests/test_agent_tools.py -q` – Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: Begründung je Kandidat inkl. verworfener"`

---

### Task 3: Log erweitern (Graph und Chat-API)

**Files:**
- Modify: `backend/src/hikeall/chatlog.py`
- Modify: `backend/src/hikeall/agent/graph.py`
- Modify: `backend/src/hikeall/api/chat.py`
- Test: `backend/tests/test_chatlog.py`, `backend/tests/test_agent_graph.py`, `backend/tests/test_api_chat.py`

**Interfaces:**
- Consumes: `trace.traced`, `trace.TracedTools` (Task 1); `explain.candidate_rows`, `Selection.rejected` (Task 2).
- Produces – neue Felder in `ChatLogEntry` (alle mit Default, alte Zeilen bleiben lesbar):
  - `user_id: str | None = None`
  - `message: str | None = None` (bereinigte aktuelle Nachricht)
  - `previous_messages: list[str] = []` (bis zu 5 vorherige Nachrichten derselben Unterhaltung, älteste zuerst)
  - `request: dict | None = None` (verstandene Anfrage, `HikeRequest` JSON = `state["current"]`)
  - `answer: str | None = None` (der Text, den der Nutzer sah: Antwort, Rückfrage oder feste Antwort)
  - `fallback_reason: str | None = None` (`state["reason"]`)
  - `candidates: list[dict] = []` (`candidate_rows`)
  - `plan: dict | None = None` (bei Route `multiday`: `state["plan"]`)
  - `llm_calls: list[dict] = []`, `tools: list[dict] = []` (aus dem Trace; `tool_calls: int` bleibt die bisherige Zählung)
  - `duration_ms: int | None = None`
- `run_chat(deps, thread_id, message, user_hash=None, user_id=None)` – neuer Keyword-Parameter; der Thread-Schlüssel bleibt hash-basiert.
- Neue State-Felder in `graph.State`: `history: list[str]` (persistiert je Thread), `final_text: str | None`, `candidates: list[dict]` (beide in `_turn` zurückgesetzt). Kein State-Key darf wie ein Knoten heißen (`answer` ist ein Knoten, daher `final_text`).

- [ ] **Step 1: Write the failing tests**
  - `test_chatlog.py::test_old_line_still_parses` – `ChatLogEntry.model_validate_json` auf die erste echte Zeile aus `data/logs/chat.jsonl` (als String im Test): `message is None`, `candidates == []`.
  - `test_agent_graph.py::test_log_has_search_details` – Feldberg-Flow mit `RecordingGateway`: letzte Zeile hat `message == FELDBERG_MSG`, `request["intent"] == "day_hike"`, `answer` enthält den gezeigten Text, `candidates[0]["status"] in ("shown", "fallback")`, `[c["step"] for c in llm_calls] == ["understand", "answer"]`, `tools[0]["name"] == "search_day_hikes"`, `duration_ms >= 0`.
  - `test_agent_graph.py::test_log_previous_messages` – zwei Nachrichten im selben Thread („…Feldberg…“, dann „kürzer“): zweite Zeile `previous_messages == [FELDBERG_MSG]`, `message == "kürzer"`.
  - `test_agent_graph.py::test_log_user_id` – `run_chat(deps, "t", FELDBERG_MSG, "hash", user_id="u-1")`: Zeile hat `user_id == "u-1"` und `user_hash == "hash"`.
  - `test_agent_graph.py::test_error_log_keeps_trace_but_no_exception_text` – ersetzt die Assertion `"Feldberg" not in raw_log` im bestehenden Fehlertest (Seite 430ff.): der Suchtext darf jetzt drin sein, `"boom"` weiterhin nicht; `line["error"] == name`.
  - Den bestehenden Test `test_log_has_no_message_text_and_counts` umbenennen in `test_log_counts` und die Text-Assertion entfernen (Ali hat Text im Log freigegeben).
  - `test_agent_graph.py::test_log_plan_for_multiday` – bestehender Mehrtages-Flow: `line["plan"]["trail_id"]` gesetzt, `candidates == []`.
  - `test_api_chat.py::test_chat_passes_user_id_and_logs_no_token` – Chat-Anfrage mit Bearer-Token über den Test-Client mit echtem `run_chat` und Fake-Deps (wie im bestehenden Modul aufgebaut): Log enthält `user_id` des Tokens, aber weder den Token-String noch `settings.openrouter_api_key`.

- [ ] **Step 2: Run** `uv run pytest tests/test_chatlog.py tests/test_agent_graph.py tests/test_api_chat.py -q` – Expected: FAIL.

- [ ] **Step 3: Implement**
  - `build_graph`: `tools = TracedTools(deps.tools)` (statt `deps.tools`).
  - `guard`: `history` = bisherige `history` + bereinigte Nachricht, auf die letzten 6 gekürzt.
  - `search`: `candidates = candidate_rows(sel)` in den zurückgegebenen State (auch wenn keine Karten).
  - `ground`: `final_text = text`; `reply`: `final_text = state["reply"]`; `clarify`: `final_text = question`.
  - `_run`: `with metered(...) as usage, traced() as tr:`; `tr` in `config["configurable"]["trace"]`, `user_id` ebenso.
  - `_write_log(settings, request_id, state, usage, error, user_hash, user_id=None, tr=None)` füllt die neuen Felder; `previous_messages = history[:-1][-5:]`; `plan` nur wenn `state.get("route") == "multiday"`; `duration_ms = int((time.monotonic() - tr.started) * 1000)`.
  - `api/chat.py`: `run_chat(..., user_hash, user_id=user.user_id)`; `_failure_log` bekommt `user_id` und setzt es.
  - Modul-Docstring von `chatlog.py` anpassen („Suchtext, Prompts und Tool-Aufrufe für das Admin-Backend; nie Passwörter, Tokens oder Exception-Texte“).

- [ ] **Step 4: Run** `uv run pytest -q` (ganzes Backend) – Expected: PASS (auch `test_smoke.py`, `test_evaluation.py`; deren `fake_run_chat` bekommt `**kw`, falls nötig).
- [ ] **Step 5: Commit** `git commit -m "feat: Log mit Suchtext, Anfrage, Antwort, Kandidaten, Prompts und Tools"`

---

### Task 4: Log-Leser mit Benutzerzuordnung

**Files:**
- Create: `backend/src/hikeall/admin_log.py`
- Modify: `backend/src/hikeall/roles.py` (`list_profiles`)
- Test: `backend/tests/test_admin_log.py`, `backend/tests/test_roles.py`

**Interfaces:**
- Produces:
  - `@dataclass class Profile: user_id: str; email: str | None; role: Role`
  - `list_profiles(conn) -> list[Profile]` in `roles.py` – `select p.user_id::text, coalesce(u.email, p.email), p.role from profiles p left join auth.users u on u.id = p.user_id order by 2` (aktuelle E-Mail aus `auth.users`; löst die veraltete `profiles.email` aus Stufe 1).
  - In `admin_log.py`:
    - `UNKNOWN = "unknown"`
    - `class LogReader: __init__(self, path: Path)`; `entries(self) -> list[dict]` – liest die JSONL-Datei, Zeilen, die kein JSON-Objekt sind oder keine `request_id` haben, werden übersprungen; fehlende Datei → `[]`; Ergebnis gecacht, neu gelesen wenn `(st_mtime_ns, st_size)` sich ändert; Reihenfolge: neueste zuerst (nach `ts`, dann umgekehrte Dateireihenfolge).
    - `owner_of(entry: dict, profiles: list[Profile]) -> str` – `entry["user_id"]` wenn es ein Profil mit dieser ID gibt; sonst Profil, dessen `chatlog.hash_user(user_id) == entry["user_hash"]`; sonst `UNKNOWN`.
    - `summary(entry: dict, owner: str, email: str | None) -> dict` – `{"request_id", "ts", "owner", "email", "message", "intent", "hits": int|None, "fallback": bool, "tool_calls", "tokens", "cost_usd": float|None, "duration_ms", "error", "detailed": bool}`. `hits` = Anzahl `candidates` mit Status `shown` oder `fallback`, wenn die Zeile ein Feld `message` hat und `intent in ("day_hike", "change")` (das ist `graph.TOUR_INTENTS`; als eigene Konstante in `admin_log.py`, um den Graphen nicht zu importieren), sonst None (alte Zeilen, Wissensfragen, Mehrtagespläne); `fallback` = `fallback_reason` gesetzt oder Status `fallback` vorhanden; `tokens = input_tokens + output_tokens`; `cost_usd` None wenn `calls_without_cost > 0` und `cost_usd == 0`; `detailed` = Zeile hat `message`.
    - `users(entries, profiles) -> list[dict]` – je Profil `{"user_id", "email", "role", "searches": n}`, dazu am Ende `{"user_id": "unknown", "email": None, "role": None, "searches": n}` nur wenn n > 0; sortiert nach Anzahl absteigend, dann E-Mail.
    - `searches(entries, profiles, owner: str | None, offset: int, limit: int) -> dict` – `{"items": [summary…], "total": n, "sums": {"count": n, "cost_usd": Summe der gemeldeten Kosten, "avg_duration_ms": Mittel über Zeilen mit duration_ms oder None}}`; `owner=None` = alle; Summen über die ganze gefilterte Menge, nicht nur die Seite.
    - `detail(entries, profiles, request_id: str) -> dict | None` – die ganze Zeile plus `"owner"` und `"email"`.

- [ ] **Step 1: Write the failing tests** in `test_admin_log.py` (Zeilen als Dicts in eine tmp-JSONL schreiben; Profile direkt als `Profile(...)`):
  - `test_missing_file_gives_no_entries`
  - `test_broken_and_partial_lines_are_skipped` – Datei mit gültiger Zeile, `{"request_id": ` (abgeschnitten), `[]`, `{"ts": "x"}` → genau 1 Eintrag.
  - `test_reader_reloads_after_append` – `entries()`, Zeile anhängen, `entries()` hat 2.
  - `test_owner_by_user_id_then_hash_then_unknown` – drei Zeilen: mit `user_id` eines Profils; nur `user_hash = hash_user(profil2.user_id)`; `user_hash` ohne Profil → `[p1, p2, "unknown"]`.
  - `test_old_line_summary_has_dashes` – alte Zeile (Felder wie `data/logs/chat.jsonl` Zeile 1): `message is None`, `hits is None`, `detailed is False`, `tokens == 1513 + 327`.
  - `test_cost_unknown_when_not_reported` – `cost_usd: 0.0, calls_without_cost: 2` → `None`; Summen zählen sie nicht.
  - `test_searches_filter_paging_and_sums` – 3 Zeilen von p1, 1 von p2: `searches(..., owner=p1.user_id, offset=1, limit=1)` → `len(items) == 1`, `total == 3`, `sums["count"] == 3`, Kosten-Summe über alle 3.
  - `test_users_counts_and_unknown_row`
  - `test_detail_unknown_id_is_none`
  - `test_roles.py::test_list_profiles_uses_current_auth_email` (DB-Test wie die vorhandenen in `test_roles.py`, mit Aufräumen im `finally`): Benutzer anlegen, `auth.users.email` ändern → `list_profiles` liefert die neue Adresse.

- [ ] **Step 2: Run** `uv run pytest tests/test_admin_log.py tests/test_roles.py -q` – Expected: FAIL.
- [ ] **Step 3: Implement** `admin_log.py` und `list_profiles`.
- [ ] **Step 4: Run** dieselben Tests – Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: Log-Leser für das Admin-Backend mit Benutzerzuordnung"`

---

### Task 5: Admin-API

**Files:**
- Create: `backend/src/hikeall/api/auth.py` (`AUTH_MESSAGES`, `authenticate` aus `api/chat.py` hierher verschoben; `api/chat.py` importiert sie)
- Modify: `backend/src/hikeall/api/admin.py`
- Modify: `backend/src/hikeall/api/app.py`
- Test: `backend/tests/test_api_admin.py`

**Interfaces:**
- Consumes: `LogReader`, `users`, `searches`, `detail`, `UNKNOWN`, `Profile`, `list_profiles` (Task 4).
- Produces:
  - `make_admin_router(settings, role_lookup, profiles_lookup: Callable[[], list[Profile]], reader: LogReader)`
  - `create_app(..., role_lookup=None, profiles_lookup=None)`; Default-`profiles_lookup` öffnet eine Verbindung und ruft `list_profiles`; `reader = LogReader(cfg.chat_log_path)`.
  - Endpunkte (alle zuerst `require_admin`):
    - `GET /admin/me` → unverändert.
    - `GET /admin/users` → `{"users": [...], "total": <Anzahl aller Einträge>}`.
    - `GET /admin/searches?user=<uuid|unknown>&offset=0&limit=50` → Ergebnis von `searches`. `limit` 1–200 (sonst 422), `offset` ≥ 0; `user` fehlt = alle.
    - `GET /admin/searches/{request_id}` → `detail`; unbekannt → 404 `{"detail": "Suche nicht gefunden"}`.
  - DB-Fehler bei `profiles_lookup` → 503 mit `AUTH_MESSAGES["unavailable"]`. Log-Lesen läuft per `run_in_threadpool`.

- [ ] **Step 1: Write the failing tests** in `test_api_admin.py` (vorhandene Token-/Rollen-Fakes des Moduls nutzen; Log als tmp-Datei über `Settings(chat_log_path=...)`):
  - `test_every_admin_endpoint_rejects_anonymous_and_users` – parametrisiert über `/admin/users`, `/admin/searches`, `/admin/searches/r1`: ohne Token 401, mit Benutzer-Token 403 `{"detail": "Kein Zugriff"}`, und der Antworttext enthält keinen Wert aus dem Log (z. B. den Suchtext `"Feldberg"`).
  - `test_users_lists_profiles_with_counts`
  - `test_searches_filters_by_user_and_unknown` – `?user=unknown` liefert nur unzugeordnete Zeilen.
  - `test_searches_limit_bounds` – `limit=0` und `limit=201` → 422.
  - `test_detail_and_404`
  - `test_profiles_db_error_is_503`
  - `test_missing_log_file_is_empty_not_500`
  - Der bestehende `test_api_chat.py` läuft unverändert mit dem verschobenen `authenticate`.

- [ ] **Step 2: Run** `uv run pytest tests/test_api_admin.py tests/test_api_chat.py -q` – Expected: FAIL.
- [ ] **Step 3: Implement** Verschiebung nach `api/auth.py`, Router, `create_app`.
- [ ] **Step 4: Run** `uv run pytest -q` – Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: Admin-API – Benutzer, Suchen, Detail"`

---

### Task 6: Seite `/admin`

**Files:**
- Create: `web/src/lib/admin.ts`, `web/src/lib/admin.test.ts`
- Create: `web/src/app/admin/page.tsx`, `web/src/app/admin/page.test.tsx`
- Create: `web/src/components/admin/SearchDetail.tsx`, `web/src/components/admin/SearchDetail.test.tsx`
- Create: `web/src/components/admin/SearchTable.tsx`

**Interfaces:**
- Consumes: API aus Task 5 über `/api/admin/...` (Next-Rewrite besteht), `getAccessToken`, `useSession` aus `lib/auth.ts`, `ChatText` für die Antwort, `PageFrame` mit `wide`.
- Produces (`lib/admin.ts`):
  - Typen `AdminUser`, `SearchSummary`, `SearchPage`, `SearchDetail` (Felder wie Task 4/5; Detail-Felder optional, weil alte Zeilen sie nicht haben).
  - `type AdminResult<T> = { ok: true; data: T } | { ok: false; status: number; message: string }`
  - `adminGet<T>(path: string): Promise<AdminResult<T>>` – holt Token, `fetch("/api/admin" + path, { headers: { Authorization: "Bearer …" } })`; ohne Token `{ok:false,status:401,message:"Bitte anmelden."}`; Netzfehler `{ok:false,status:0,message:"Backend nicht erreichbar"}`; sonst `detail` aus der JSON-Antwort.
  - Format-Helfer: `usd(v: number | null): string` – `null` → „–“, sonst `"0,0021 $"` (4 Nachkommastellen, deutsch); `ms(v: number | null): string` – „4,2 s“ / „–“; `when(ts: string): string` – „heute 14:02“ / „gestern 09:12“ / „31.10. 18:40“ (Europe/Berlin).
- Seitenverhalten:
  - `loading` → nichts; ohne Session → Link „Bitte anmelden“ auf `/anmelden`; `/admin/me` 403 → nur „Kein Zugriff“; 503/0 → die Meldung.
  - Drei Spalten (`grid-cols-[16rem_22rem_1fr]`): **Benutzer** („Alle (N)“, dann E-Mails mit Anzahl, „Unbekannt (n)“); **Letzte Suchen** des gewählten Benutzers (erste 50: Suchtext oder „(ältere Suche)“, Zeit, Kosten); **Details** der gewählten Suche. Darunter **Alle Suchen** als Tabelle mit Spalten Zeit, Benutzer, Suche, Intent, Treffer („3“, „2 (Ausweich)“, „–“), Tools, Tokens, Kosten, Dauer, Fehler, Summenzeile „Summe: N Suchen · X $ · Ø Y s“, und „Mehr laden“ (offset += 50) solange `items.length < total`.
  - Auswahl eines Benutzers lädt Liste und Tabelle neu und wählt die neueste Suche; Klick auf eine Zeile in Liste oder Tabelle zeigt ihr Detail.
- `SearchDetail` (von oben nach unten, wie Spec „Details einer Suche“):
  1. Suchtext (fett), darunter „Vorher in dieser Unterhaltung“ mit `previous_messages`; Benutzer, Zeit, Intent, Aktivität.
  2. **So verstanden**: aus `request` – Ort (`start.label`), Bedingungen (`constraints`: Art, min/max, Rundweg ja/nein), Dauer, Datum, Vorlieben und „ohne …“ für Meiden; unbekannte Felder werden weggelassen.
  3. **Antwort** über `ChatText`, darunter „Zahlenprüfung: X Zahlen ersetzt · Y Namen markiert · Z Aussagen entfernt“ aus `grounding_unsupported`, `grounding_unsupported_names`, `unsat_claims_removed`; `fallback_reason` als Hinweis.
  4. **Warum diese Touren?** Tabelle aus `candidates`: Name, je Bedingung eine Spalte (Kopf aus `kind`: Länge, Höhenmeter, Rundweg, Entfernung, Dauer) mit „✓ 12,4“ / „✗ 22,3“ / „?“, Vorlieben („Einkehr ✓“, fehlend ✗, gemieden „ohne … ✗“), Punkte, Status („gezeigt“, „Ausweich“, „verworfen“) und `note`; verworfene Zeilen `opacity-60`. Bei `plan`: stattdessen Weg (`trail_name`) und je Tag „Tag n · x km · Ziel (stop.name oder ‚Wegende‘)“. Ohne beides entfällt der Block.
  5. **Tool-Aufrufe (n)**: nummeriert, Name, Argumente als JSON, Ergebnis: 300 Zeichen Vorschau, Rest in `<details>`; „gekürzt“-Hinweis bei `truncated`; Fehlerklasse wenn `error`.
  6. **Modell · Tokens · Kosten · Dauer**: je LLM-Aufruf eine Zeile (Step, Modell, ein/aus, Kosten mit `usd`, Dauer) und eine Summenzeile aus den Zeilenfeldern `input_tokens`, `output_tokens`, `cost_usd`, `duration_ms`.
  7. **Prompts**: je LLM-Aufruf ein `<details>` „Prompt: <step>“ mit allen Nachrichten (Rolle als Überschrift, Inhalt in `<pre className="whitespace-pre-wrap">`) und der Ausgabe.
  - Zeile ohne `message` (alt): nur Kopf, Kennzahlen (Block 6 nur Summe) und der Hinweis „Ältere Suche – nur Kennzahlen gespeichert“.

- [ ] **Step 1: Write the failing tests**
  - `admin.test.ts`: `usd(null) === "–"`, `usd(0.0021) === "0,0021 $"`; `ms(4200) === "4,2 s"`; `adminGet` ohne Token → `status 401`; mit 403-Antwort → `{ok:false,status:403,message:"Kein Zugriff"}`; bei `fetch`-Throw → `status 0`.
  - `SearchDetail.test.tsx`: volle Zeile (Fixture mit 1 gezeigt, 1 Ausweich, 1 verworfen, 2 LLM-Aufrufen, 1 Tool mit 1.000 Zeichen Ergebnis) zeigt „So verstanden“, „Warum diese Touren?“, „verworfen“, „Tool-Aufrufe (1)“, „Prompt: understand“; Vorschau des Tool-Ergebnisses ist höchstens 300 Zeichen lang sichtbar; alte Zeile zeigt „Ältere Suche – nur Kennzahlen gespeichert“ und keinen Block „Warum diese Touren?“; Zeile mit `plan` zeigt „Tag 1“.
  - `page.test.tsx` (fetch und `useSession`/`getAccessToken` gemockt wie in `web/src/app/gemerkt/page.test.tsx`): ohne Session „Bitte anmelden“; `/me` 403 → „Kein Zugriff“ und keine weitere Anfrage an `/users` oder `/searches`; Admin → Benutzerliste mit „Alle (4)“ und „Unbekannt (1)“, Klick auf einen Benutzer ruft `/searches?user=<id>` und zeigt dessen Suchen; Tabelle zeigt Summenzeile; „Mehr laden“ erscheint bei `total > items.length` und ruft `offset=50`.

- [ ] **Step 2: Run** `cd web && npx vitest run src/lib/admin.test.ts src/components/admin src/app/admin` – Expected: FAIL.
- [ ] **Step 3: Implement** lib, Komponenten, Seite.
- [ ] **Step 4: Run** `npx vitest run && npx tsc --noEmit` – Expected: alles PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: Seite /admin mit Benutzern, Suchen, Details und Tabelle"`

---

### Task 7: Zugang im Kopf, README, Prüfung im Browser

**Files:**
- Modify: `web/src/components/AccountMenu.tsx`, `web/src/components/AccountMenu.test.tsx`
- Modify: `README.md`

**Interfaces:**
- Consumes: `adminGet` (Task 6).

- [ ] **Step 1: Write the failing test** `AccountMenu.test.tsx::shows Backend link only for admins` – `/me` 200 → Link „Backend“ auf `/admin`; 403 → kein Link; ohne Session wird `/me` nicht angefragt.
- [ ] **Step 2: Run** `npx vitest run src/components/AccountMenu.test.tsx` – Expected: FAIL.
- [ ] **Step 3: Implement** – nach Laden der Session einmal `adminGet("/me")`; bei `ok` Link „Backend“ vor „Meine Pläne“. Reset bei Session-Wechsel.
- [ ] **Step 4: Run** `npx vitest run && npx tsc --noEmit` – Expected: PASS.
- [ ] **Step 5: README** – Abschnitt „Backend (Admin)“: Aufruf `/admin`, nur mit Rolle `admin`; was der Log jetzt enthält (Suchtext, Prompts, Tool-Aufrufe, Benutzer-ID; keine Passwörter/Tokens); dass ältere Zeilen nur Kennzahlen haben; Hinweis, dass `data/logs/chat.jsonl` dadurch persönliche Daten enthält und nicht weitergegeben werden soll.
- [ ] **Step 6: Prüfung im laufenden System** – Backend und Web starten (wie in README), als `admin@hikeall.local` eine Suche „Rundtour Feldberg 15 km mit Einkehr“ stellen, `/admin` öffnen: neue Suche erscheint mit Details, alte Zeilen unter ihren Benutzern; als `smoke@hikeall.local` `/admin` → „Kein Zugriff“. Ergebnis im Bericht festhalten.
- [ ] **Step 7: Commit** `git commit -m "feat: Backend-Link für Admins, README"`
