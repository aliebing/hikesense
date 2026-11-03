# Wie die KI arbeitet: Spickzettel fürs Review

Eine Chatnachricht von Anfang bis Ende, mit echten JSON-Beispielen und kurzen Antworten auf die typischen Review-Fragen. Grundsatz des Projekts: **Der Code entscheidet, das Modell formuliert.** Das Video dazu: `scripts/video/ai_demo.py` (`out/hikeallabout-ai-de.mp4`, `out/hikeallabout-ai-en.mp4`).

Quellen der Beispiele (Stand 2026-11-03):

- **Titisee-Durchlauf:** echte Zeile aus `data/logs/chat.jsonl` (Nutzervideo, „A round walk near Titisee, about 10 km“, `openai/gpt-4o-mini`). Gekürzt, Schlüssel und Werte echt, `…` = weggelassen.
- **Feldberg-Ort-Durchlauf:** echte Zeilen aus `data/logs/chat.jsonl` der Hauptarbeitskopie (2026-11-02, Rückfrage und Antwort darauf).
- **Wissensfrage mit Tool-Calls:** Im Log gibt es noch keinen Wissens-Durchlauf mit Tool-Aufrufen (die 127 Wissens-Zeilen stammen von vor dem Trace). Deshalb ein **Demo-Durchlauf durch den echten Graphen**: echte Tools (Datenbank, Wissensindex), echtes Grounding, aber die Antworten des Modells vorgegeben (`FakeGateway` aus `llm/gateway.py`). Die Form der Nachrichten ist genau die, die LangChain liefert.

---

## 1. Eine Nachricht, Schritt für Schritt

| # | Schritt | Wo im Code | Modell? |
|---|---|---|---|
| 1 | Browser schickt `POST /chat` mit JSON-Body und Supabase-Token | `web/src/lib/chat.ts` | – |
| 2 | API prüft Token (401/503), Ratenlimit (10/min, 100/Tag pro Konto, sonst 429), Körpergröße (64 KB), validiert den Body mit Pydantic (`ChatRequest`), bereinigt die Nachricht (max. 1000 Zeichen) | `api/chat.py: chat`, `api/auth.py: authenticate`, `rate_limit.py: RateLimiter`, `guard.py: sanitize_text` | – |
| 3 | `run_chat` startet den Graphen mit Kosten-Zähler (max. 0,05 $) und Trace; `thread_id = user_hash:thread_id`; `deps.graph.stream(..., stream_mode="custom")` | `agent/graph.py: run_chat, _run` | – |
| 4 | **guard**: bereinigen, Verlauf merken, Prompt-Injection-Muster → fester Satz (Route `reply`) | `graph.py: build_graph.guard`, `guard.py: looks_like_injection` | nein |
| 5 | **understand**: höchstens ein Modellaufruf, Ausgabe als JSON nach Schema `RawRequest`; danach `resolve` (reiner Code) → `HikeRequest` oder `Clarify`; sendet `understood`; setzt `state["route"]` | `graph.py: understand`, `understand.py: parse, resolve` | ja (1×) |
| 6 | **Arbeitsknoten** (genau einer): `clarify`, `reply`, `search`, `multiday`, `react`, `groups`, `events` | `graph.py: build_graph` (bedingte Kante) | je nach Knoten |
| 7 | **answer**: Modell formuliert aus dem Datenblock (Temperatur 0,3); übersprungen, wenn `react` schon einen Entwurf hat oder der Code einen festen Text schreibt | `graph.py: answer`, `gateway.py: answer` | ja (1×) |
| 8 | **ground**: Prompt-Leck, „keine Tour erfüllt …“ ohne Ausweichen, Wetterbehauptungen, Zahlenprüfung, Tournamen; Code-Sätze davor/danach; dann `token`- und `sources`-Ereignisse | `graph.py: ground`, `grounding.py: grounding_check, strip_unsat_claims` | nein |
| 9 | **log**: eine JSON-Zeile in `data/logs/chat.jsonl`, dann `done` mit Tokens und Kosten | `graph.py: log, _write_log`, `chatlog.py` | nein |

Ausnahmen in understand ohne Modell: die Antwort auf eine Ortsrückfrage („Feldberg-Ort“) setzt die gemerkte Anfrage fort (`_continue_pending`), und „Regenvariante für Tag 2“ zum letzten Plan (`_rain_request`). Bei einem Fehler des Modells (`LLMError`) schreibt `_run` die Log-Zeile mit dem Fehlernamen und schickt ein `error`-Ereignis.

**Modellaufrufe pro Nachricht:** Tagestour 2 (understand + answer) · Antwort auf Rückfrage 1 (nur answer, im Log: Feldberg-Ort) · Mehrtagestour 2 · Wissensfrage 1 + n Tool-Runden (der Text der letzten Runde ist der Entwurf, answer entfällt) · Gruppen 1 (nur understand, Antwort vom Code) · Veranstaltungen 1 + Websuche + Extraktion je Seite (Antwort vom Code).

**Ereignisse** (alle Pydantic-Klassen, Unterklassen von `ChatEvent` in `graph.py`): `understood`, `clarify`, `results`, `weather_days`, `plan`, `groups`, `events`, `token`, `sources`, `done`, `error`. Gesendet mit LangGraphs `get_stream_writer()` (`_emit`) und in `api/chat.py: _event` zu `{"event": event.type, "data": event.model_dump_json()}`.

### Der Graph

```
START → guard ─┬─ reply ─────────────────────────────┐
               └─ understand ─┬─ clarify ────────────┤
                              ├─ reply ──────────────┤
                              ├─ search ──┐          │
                              ├─ multiday ┤          │
                              ├─ react ───┼→ answer → ground → log → END
                              ├─ groups ──┤
                              └─ events ──┘
```

Zwölf Knoten, `StateGraph(State)` in `build_graph`; `add_conditional_edges` liest `state["route"]`; `compile(checkpointer=MemorySaver)` hält pro Gespräch die letzte Anfrage, eine offene Rückfrage, die letzten Touren und den letzten Plan (nur JSON-Daten).

---

## 2. Die JSON-Stationen mit echten Daten

### 2.1 Anfrage und Ereignisse

```json
POST /chat   Authorization: Bearer <Supabase JWT>
{"thread_id": "6f0c2a1e-…", "message": "A round walk near Titisee, about 10 km", "lang": "en"}
```

```text
event: understood
data: {"type": "understood", "text": "Understood: day hike, walking, start: Titisee, round walk, length 8.5–11.5 km (≈ 10 km), radius at most 15 km.", "request": {…}, "labels": {}}

event: results
data: {"type": "results", "cards": [{"trail_id": "day-12013912", "name": "Genießerpfad - Säbelthomaweg", "length_km": 11.44, "ascent_m": 389, …}, …], "fallback_reason": null}

event: token
data: {"type": "token", "text": "Here "}

event: done
data: {"type": "done", "usage": {"input_tokens": 1916, "output_tokens": 317, "cost_usd": 0.0003816, …}, "unsupported": 0}
```

### 2.2 understand: Schema rein, JSON raus

`gw.structured(RawRequest, SYSTEM_PROMPT, user)` → `ChatOpenAI(...).with_structured_output(RawRequest, include_raw=True)`. LangChain 1.x nutzt dafür standardmäßig `method="json_schema"`: Das OpenAI-SDK macht aus der Pydantic-Klasse ein **striktes** JSON-Schema (`strict: true`, alle Felder Pflicht, `additionalProperties: false`), das als `response_format` an OpenRouter geht (geprüft mit `openai.lib._parsing.type_to_response_format_param`):

```json
{"type": "json_schema",
 "json_schema": {"name": "RawRequest", "strict": true,
   "schema": {"type": "object", "additionalProperties": false,
     "required": ["intent", "activity", "start_text", …],
     "properties": {
       "intent": {"enum": ["day_hike", "multiday", "knowledge", "change", "events", "groups", "other"], "type": "string"},
       "start_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
       "length_km_min": {"anyOf": [{"type": "number"}, {"type": "null"}]}, …}}}}
```

Echte Ausgabe des Modells (`llm_calls[0].output`, Titisee):

```json
{"intent": "day_hike", "activity": "hike", "start_text": "Titisee", "roundtrip": true,
 "length_km_min": 10.0, "length_km_max": 10.0, "ascent_m_min": 0.0, "ascent_m_max": 0.0,
 "duration_h_min": 0.0, "duration_h_max": 0.0, "length_km_approx": 10.0, "ascent_m_approx": 0.0,
 "duration_h_approx": 0.0, "radius_km_max": 0.0, "pace_min_per_km": 0.0, "trail_text": null, "days": null, …,
 "wishes": [], "question": null}
```

Gültiges JSON, aber acht erfundene Nullen. `resolve` → `_constraints` behält eine Zahl nur, wenn `_written` sie in der Nachricht findet. Ergebnis (`request` in der Log-Zeile):

```json
{"start": {"kind": "place", "tag_id": "place:titisee", "label": "Titisee", "lat": 47.9011491, "lon": 8.1499728},
 "constraints": [{"kind": "roundtrip", "required": true},
                 {"kind": "length_km", "min": 8.5, "max": 11.5, "approx": 10.0},
                 {"kind": "radius_km", "max": 15.0}]}
```

Log: `"discarded_model_numbers": 8` (Anstieg min/max/approx, Dauer min/max/approx, Umkreis, Tempo). `min = max = 10` wird zum Band ±15 % (`_approx`), der Standard-Umkreis 15 km kommt von `_finish`, „round walk“ steht wirklich da (`_roundtrip_written`).

Zweites echtes Beispiel (Feldberg, 2026-11-02): „ich suche eine rundstrecke am feldberg bei freiburg ca. 10km < 300 höhenmeter“ → Modell: `"start_text": "Feldberg bei Freiburg"`, `"ascent_m_min": 0.0`, `"ascent_m_max": 300.0`. Der Code kennt „Feldberg bei Freiburg“ nicht und fragt zurück („Meinst du „Feldberg-Ort“?“). Die Antwort „Feldberg-Ort“ läuft **ohne Modellaufruf** weiter (`_continue_pending` + `resolve_option`); die 0 m Mindestanstieg werden verworfen (`discarded_model_numbers: 1`).

### 2.3 search: Der Graph ruft das Tool selbst

`build_graph.search` → `tools.search_day_hikes(req, lang)` (`DbTools` → `tools.py: search_day_hikes`, PostGIS + `constraints.select`). `TracedTools` zeichnet Argumente und Ergebnis auf:

```json
"tools": [{"name": "search_day_hikes",
  "args": {"arg0": {"intent": "day_hike", "start": {"kind": "place", "label": "Titisee", …},
                    "constraints": [{"kind": "roundtrip", "required": true, …},
                                    {"kind": "length_km", "min": 8.5, "max": 11.5, "approx": 10.0, …},
                                    {"kind": "radius_km", "max": 15.0, …}], …}},
  "result": "{\"selection\": {\"matches\": [{\"candidate\": {\"trail_id\": \"day-12013912\", \"name\": \"Genießerpfad - Säbelthomaweg\", \"length_km\": 11.44, \"ascent_m\": 389, …}, \"results\": [{\"kind\": \"length_km\", \"ok\": true, \"actual\": 11.44, \"bound\": \"at least 8.5 and at most 11.5\"}, …]}, …], \"fallbacks\": [], \"reason\": null, \"rejected\": [{\"candidate\": {\"name\": \"Genießerpfad - Jägersteig\", \"length_km\": 11.57, …}, \"results\": [{\"kind\": \"length_km\", \"ok\": false, \"actual\": 11.57, \"bound\": \"at most 11.5\"}, …]}, …]}, …}",
  "truncated": true, "duration_ms": 93}]
```

Daraus baut `_search_data` den Datenblock, die einzige Nutzernachricht an `answer` (`llm_calls[1]`):

```text
Understood: day hike, walking, start: Titisee, round walk, length 8.5–11.5 km (≈ 10 km), radius at most 15 km.
Matching tours (sorted by preferences):
1. Genießerpfad - Säbelthomaweg – length 11.4 km, ascent 389 m, walking time 3.9 h, distance to the start 3.5 km; conditions: round walk met; length met; distance met
2. …
```

### 2.4 react: echtes Tool-Calling (Demo-Durchlauf)

Die Tool-Karte `TOOL_SPECS` in `tools.py` (OpenAI-Funktionsformat, gebaut von `_spec`); `gw.tool_round` → `ChatOpenAI.bind_tools(TOOL_SPECS)` schickt sie als Feld `tools` mit jedem Aufruf der Schleife:

```json
{"type": "function",
 "function": {"name": "hiking_time",
   "description": "Berechnet die Gehzeit nach DIN 33466 (ohne Pausen) aus Länge, Aufstieg und Abstieg.",
   "parameters": {"type": "object",
     "properties": {"length_km": {"type": "number"}, "ascent_m": {"type": "number"}, "descent_m": {"type": "number"}},
     "required": ["length_km", "ascent_m", "descent_m"]}}}
```

Vier Tools: `get_trail_details(trail_id)`, `find_accommodation(trail_id, near_km?, max_dist_m?)`, `hiking_time(length_km, ascent_m, descent_m)`, `search_knowledge(query, k?)`. `search_day_hikes` steht bewusst nicht darauf („search_day_hikes is called by the graph itself“).

Nachrichtenliste der Schleife (Folgefrage nach der Feldberg-Ort-Suche, gekürzt):

| # | Nachricht | von | Inhalt |
|---|---|---|---|
| 1 | `SystemMessage` | Code | `react_system(lang)`: „… antworte nur mit dem, was die Werkzeuge liefern …“ |
| 2 | `SystemMessage` | Code | letzte Touren: `- day-12013547: Genießerpfad - Menzenschwander Geißenpfad …` |
| 3 | `HumanMessage` | Nutzer | „Wie lange brauche ich für den Geißenpfad, und gibt es dort eine Einkehr?“ |
| 4 | `AIMessage` | **Code** | `tool_calls=[{"name": "search_knowledge", "args": {"query": "…", "k": 5}, "id": "vorab"}]` |
| 5 | `ToolMessage` | Code | `tool_call_id="vorab"`, `[{"text": "Einkehr, Hütten und Übernachtung …", "url": "https://de.wikivoyage.org/…", "license": "CC BY-SA 4.0", …}, …]` |
| 6 | `AIMessage` | Modell | `tool_calls=[{"name": "get_trail_details", "args": {"trail_id": "day-12013547"}, "id": "call_1"}]` |
| 7 | `ToolMessage` | Code | `tool_call_id="call_1"`, `{"trail_id": "day-12013547", "length_km": 9.78, "ascent_m": 278, "descent_m": 277, "pois": [{"name": "Hotel Hirschen", "kind": "food", "dist_m": 286, …}, …], …}` |
| 8 | `AIMessage` | Modell | `tool_calls=[{"name": "hiking_time", "args": {"length_km": 9.78, "ascent_m": 278, "descent_m": 277}, "id": "call_2"}]` |
| 9 | `ToolMessage` | Code | `tool_call_id="call_2"`, `{"hours": 3.19, "horizontal_h": 2.44, "vertical_h": 1.48, "formula": "max(h, v) + min(h, v) / 2 …"}` |
| 10 | `AIMessage` | Modell | keine `tool_calls` → Entwurf: „Für den Menzenschwander Geißenpfad (9,8 km, 278 Hm) rechnet DIN 33466 mit etwa 3,2 Stunden ohne Pausen, also rund 4 Stunden mit Pausen.“ |

Auf der Leitung (OpenAI-Format) stehen die Argumente als JSON-**String** in `tool_calls[].function.arguments`; LangChain parst sie in das Dict `args`. Eine `ToolMessage` wird zur Nachricht mit `role: "tool"` und derselben `tool_call_id`, so weiß das Modell, welches Ergebnis zu welchem Aufruf gehört. Das Log speichert die Tool-Aufrufe als Name + Argumente (`trace.py: message_dicts`).

Nach `ground`:

```text
Für den Menzenschwander Geißenpfad (9,8 km, 278 Hm) rechnet DIN 33466 mit etwa 3,2 Stunden ohne Pausen, also rund ? Stunden mit Pausen.

Hinweis: 1 Angabe(n) ließ(en) sich nicht belegen und wurde(n) entfernt.
```

Belege, die `_walk` aus den Tool-JSONs gezogen hat (Auszug): `9,78 km`, `278 Hm`, `277 Hm`, `3,19 h`, `2,44 h`, `1,48 h`, `286 m`, Namen `Genießerpfad - Menzenschwander Geißenpfad`, `Hotel Hirschen`. 9,8 km und 3,2 h sind gerundet belegt, „4 Stunden“ steht in keinem Ergebnis.

### 2.5 Die Log-Zeile

```json
{"ts": "2026-11-03T00:34:37+00:00", "intent": "day_hike", "tool_calls": 1,
 "input_tokens": 1916, "output_tokens": 317, "cost_usd": 0.0003816,
 "discarded_model_numbers": 8, "grounding_unsupported": 0,
 "message": "A round walk near Titisee, about 10 km", "request": {…}, "answer": "Here are some …",
 "candidates": [{"name": "Genießerpfad - Säbelthomaweg", "status": "shown", …}, …],
 "llm_calls": [{"step": "understand", "model": "openai/gpt-4o-mini", "messages": [{"role": "system", …}, …],
                "output": {"intent": "day_hike", …}, "input_tokens": 1435, "output_tokens": 153,
                "cost_usd": 0.00021105, "duration_ms": 2074},
               {"step": "answer", "input_tokens": 481, "output_tokens": 164, "cost_usd": 0.00017055, "duration_ms": 1859, …}],
 "tools": [{"name": "search_day_hikes", "args": {"arg0": {…}}, "result": "{\"selection\": …}", "truncated": true, "duration_ms": 93}],
 "duration_ms": 4071}
```

Die Admin-Seite `/admin` liest diese Datei (`api/admin.py`, `admin_log.py: LogReader`). Nie im Log: Passwörter, Tokens, Fehlertexte (nur Klassennamen). `user_hash` ist ein Hash der Nutzer-ID (damit ist auch der Checkpointer-Schlüssel gebildet); die ID selbst steht in `user_id` für die Admin-Ansicht.

---

## 3. Fragen und Antworten

**Wie ruft der Agent ein Tool auf?**
Auf zwei Wegen. Bei Tagestouren, Mehrtagesplänen, Gruppen und Veranstaltungen ruft der Graph-Knoten das Tool direkt als Python-Funktion auf, z. B. `build_graph.search` → `tools.search_day_hikes(req, lang)`; das Modell ist daran nicht beteiligt. Nur im Knoten `react` (Wissensfragen) gibt es echtes Tool-Calling: `gw.tool_round(messages, TOOL_SPECS)` bindet die Funktionsbeschreibungen mit `bind_tools`, das Modell antwortet mit einer `AIMessage` mit `tool_calls` (Name, JSON-Argumente, ID), `_run_tool` → `_call_tool` führt das passende Tool aus und hängt das Ergebnis als `ToolMessage(json, tool_call_id=id)` an. Jeder Aufruf läuft über `TracedTools` (`trace.py`) und landet mit Argumenten und Ergebnis im Log.

**Wer entscheidet, welches Tool läuft?**
Die Route entscheidet der Code: Das Modell nennt in `RawRequest.intent` nur die Absicht, `understand` setzt daraus `state["route"]` und kann sie überstimmen (Rückfrage bei unklarem Ort, fehlender Startort, Folgefrage zum Plan). Bei `search`, `multiday`, `groups` und `events` steht das Tool im Code fest. Nur in `react` wählt das Modell Tools und Argumente aus `TOOL_SPECS`; aber der Code sucht vorab selbst im Wissensindex (`id: "vorab"`), begrenzt auf `max_tool_calls = 8` (die Vorab-Suche mitgezählt) und antwortet ohne Quelle mit einem festen Satz (`no_source_reply`).

**Welche Rolle spielt JSON?**
JSON ist die Schnittstelle zwischen Modell und Code an sechs Stellen: (1) das JSON-Schema von `RawRequest` und `TOOL_SPECS` an das Modell, (2) die Ausgabe des Modells, die Pydantic validiert (sonst `LLMBadOutput`), (3) die Tool-Argumente in `tool_calls`, (4) die Tool-Ergebnisse (`_dump` → `json.dumps` in die `ToolMessage`, und `_walk` liest daraus die Belege), (5) die `ChatEvent`-Ereignisse per SSE an den Browser, (6) die Log-Zeile in `chat.jsonl`. Weil alles typisiert ist (Pydantic), sieht der Code nie freien Text, wo er Daten erwartet. Auch der Gesprächszustand im Checkpointer ist nur JSON (`model_dump(mode="json")`).

**Was passiert, wenn das Modell eine Zahl erfindet?**
Zweimal abgesichert. Beim Verstehen behält `understand.py: _constraints` eine Zahl nur, wenn `_written` sie in der Nachricht findet; sonst wird sie verworfen und als `discarded_model_numbers` geloggt (Titisee: 8 erfundene Nullen). In der Antwort sucht `grounding.py: grounding_check` jede Zahl mit Einheit und vergleicht sie mit den Belegen aus den Tool-Ergebnissen und den Code-Sätzen dieses Durchlaufs; eine unbelegte Zahl wird durch „?“ ersetzt, mit Hinweis, und als `grounding_unsupported` gezählt. Eine von `hiking_time` berechnete Gehzeit zählt nur als Beleg, wenn ihre Eingaben selbst belegt sind (`_inputs_in_evidence`).

**Warum nicht alles per Tool-Calling?**
Weil die wichtigen Entscheidungen prüfbar und reproduzierbar sein sollen: Welche Touren passen, welche knapp daneben liegen und warum eine Tour ausfällt, entscheidet `constraints.select` deterministisch (sortiert nach Score, Entfernung, ID). Ein Modell, das selbst Tools wählt, könnte eine Bedingung vergessen, eine Suche auslassen oder anders sortieren, und jede Runde kostet Tokens und Zeit. So braucht eine Tagestour genau zwei Modellaufrufe, die Evaluation prüft die Ergebnisse mit Code, und Tool-Calling bleibt dort, wo die Frage offen ist (Wissensfragen).

**Was ist LangGraph hier, was macht LangChain, was OpenRouter?**
LangGraph ist der Ablauf: `StateGraph(State)` mit zwölf Knoten, bedingten Kanten über `state["route"]`, dem `MemorySaver`-Checkpointer pro Gespräch und dem Custom-Stream (`get_stream_writer`), über den die Ereignisse kommen (`graph.py: build_graph`). LangChain ist die Modell-Schicht: `ChatOpenAI`, die Nachrichtenklassen (`SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`), `with_structured_output` und `bind_tools` (`llm/gateway.py: OpenRouterGateway`). OpenRouter ist der API-Anbieter: eine OpenAI-kompatible Schnittstelle (`https://openrouter.ai/api/v1`) zum Modell `openai/gpt-4o-mini`, die die Kosten pro Aufruf mitliefert (`usage.include`) und für Veranstaltungen das Websuche-Plugin bereitstellt (`web_completion`, Engine `exa`).

**Streamt das Modell die Antwort live?**
Nein. Die `token`-Ereignisse entstehen erst in `ground`, nachdem der ganze Text geprüft ist; der Code zerlegt ihn in Wortstücke (`_CHUNK`). So kann keine unbelegte Zahl kurz auf dem Bildschirm erscheinen. Live kommen dagegen `understood` und `results`, sobald der Code sie hat.

---

## English

# How the AI works: review cheat sheet

One chat message from start to finish, with real JSON and short answers to the usual review questions. The project's principle: **the code decides, the model words it.** The video: `scripts/video/ai_demo.py` (`out/hikeallabout-ai-en.mp4`, `out/hikeallabout-ai-de.mp4`). The JSON examples are the ones in sections 2.1–2.5 above (identical data; JSON keys are English anyway).

Sources of the examples (as of 2026-11-03):

- **Titisee turn:** a real line of `data/logs/chat.jsonl` (user video, "A round walk near Titisee, about 10 km", `openai/gpt-4o-mini`). Shortened, keys and values real, `…` = left out.
- **Feldberg-Ort turn:** real lines of `data/logs/chat.jsonl` in the main checkout (2026-11-02, a clarify question and the answer to it).
- **Knowledge question with tool calls:** the log has no knowledge turn with tool calls yet (the 127 knowledge lines predate the trace). So it is a **demo turn through the real graph**: real tools (database, knowledge index), real grounding, but scripted model replies (`FakeGateway` in `llm/gateway.py`). The message shapes are exactly what LangChain returns.

### 1. One message, step by step

| # | Step | Where in the code | Model? |
|---|---|---|---|
| 1 | The browser sends `POST /chat` with a JSON body and the Supabase token | `web/src/lib/chat.ts` | – |
| 2 | The API checks the token (401/503), the rate limit (10/min, 100/day per account, else 429), the body size (64 KB), validates the body with Pydantic (`ChatRequest`) and cleans the message (max. 1000 characters) | `api/chat.py: chat`, `api/auth.py: authenticate`, `rate_limit.py: RateLimiter`, `guard.py: sanitize_text` | – |
| 3 | `run_chat` starts the graph with a cost meter (max. $0.05) and a trace; `thread_id = user_hash:thread_id`; `deps.graph.stream(..., stream_mode="custom")` | `agent/graph.py: run_chat, _run` | – |
| 4 | **guard**: clean, remember the history, prompt-injection pattern → fixed reply (route `reply`) | `graph.py: build_graph.guard`, `guard.py: looks_like_injection` | no |
| 5 | **understand**: at most one model call, output as JSON for the `RawRequest` schema; then `resolve` (pure code) → `HikeRequest` or `Clarify`; emits `understood`; sets `state["route"]` | `graph.py: understand`, `understand.py: parse, resolve` | yes (1×) |
| 6 | **one worker**: `clarify`, `reply`, `search`, `multiday`, `react`, `groups`, `events` | `graph.py: build_graph` (conditional edge) | depends |
| 7 | **answer**: the model words the data block (temperature 0.3); skipped when `react` already has a draft or the code writes a fixed text | `graph.py: answer`, `gateway.py: answer` | yes (1×) |
| 8 | **ground**: prompt leak, "no tour meets …" without a fallback, weather claims, number check, tour names; the code's sentences before/after; then `token` and `sources` events | `graph.py: ground`, `grounding.py: grounding_check, strip_unsat_claims` | no |
| 9 | **log**: one JSON line in `data/logs/chat.jsonl`, then `done` with tokens and cost | `graph.py: log, _write_log`, `chatlog.py` | no |

Exceptions in understand without a model call: the answer to a place question ("Feldberg-Ort") continues the stored request (`_continue_pending`), and "rain variant for day 2" on the last plan (`_rain_request`). On a model error (`LLMError`), `_run` writes the log line with the error class and sends an `error` event.

**Model calls per message:** day hike 2 (understand + answer) · answer to a clarify question 1 (answer only; in the log: Feldberg-Ort) · multi-day 2 · knowledge 1 + n tool rounds (the last round's text is the draft, answer is skipped) · groups 1 (understand only, the answer is code-written) · events 1 + web search + one extraction per page (code-written answer).

**Events** (Pydantic subclasses of `ChatEvent` in `graph.py`): `understood`, `clarify`, `results`, `weather_days`, `plan`, `groups`, `events`, `token`, `sources`, `done`, `error`. Emitted through LangGraph's `get_stream_writer()` (`_emit`) and turned into `{"event": event.type, "data": event.model_dump_json()}` by `api/chat.py: _event`.

**The graph:** twelve nodes (diagram in section 1 above), `StateGraph(State)` in `build_graph`; `add_conditional_edges` reads `state["route"]`; `compile(checkpointer=MemorySaver)` keeps the last request, an open clarify question, the last tours and the last plan per conversation (JSON data only).

### 2. Notes on the JSON stations (see 2.1–2.5 above)

- **understand:** `gw.structured(RawRequest, SYSTEM_PROMPT, user)` → `ChatOpenAI(...).with_structured_output(RawRequest, include_raw=True)`. LangChain 1.x uses `method="json_schema"` by default: the OpenAI SDK turns the Pydantic class into a **strict** JSON Schema (`strict: true`, every field required, `additionalProperties: false`), sent as `response_format` to OpenRouter. The model's real output for Titisee is valid JSON with eight invented zeros; `resolve` → `_constraints` keeps a number only if `_written` finds it in the message (`discarded_model_numbers: 8`), turns `min = max = 10` into a ±15 % band (`_approx`) and adds the default 15 km radius (`_finish`). Feldberg: "Feldberg bei Freiburg" is unknown, so the code asks back; the answer "Feldberg-Ort" continues **without a model call**, and the invented minimum ascent of 0 m is dropped (`discarded_model_numbers: 1`).
- **search:** `build_graph.search` calls `tools.search_day_hikes(req, lang)` itself (PostGIS + `constraints.select`); `TracedTools` records args and result; `_search_data` writes the data block that is the only user message to `answer`.
- **react:** `TOOL_SPECS` (OpenAI function format, built by `_spec`) is sent with every round by `bind_tools`. On the wire the arguments are a JSON **string** in `tool_calls[].function.arguments`; LangChain parses them into the dict `args`. A `ToolMessage` becomes a message with `role: "tool"` and the same `tool_call_id`, so the model knows which result belongs to which call. In the demo turn, "about 4 hours with breaks" is in no tool result and becomes "?" with a note; 9.8 km and 3.2 h are supported (rounded from 9.78 km and 3.19 h).
- **log:** one line per turn; `/admin` reads it (`api/admin.py`, `admin_log.py: LogReader`). Never in the log: passwords, tokens, exception texts (class names only).

### 3. Questions and answers

**How does the agent call a tool?**
In two ways. For day hikes, multi-day plans, groups and events the graph node calls the tool directly as a Python function, e.g. `build_graph.search` → `tools.search_day_hikes(req, lang)`; the model is not involved. Only the `react` node (knowledge questions) does real tool calling: `gw.tool_round(messages, TOOL_SPECS)` binds the function specs with `bind_tools`, the model replies with an `AIMessage` carrying `tool_calls` (name, JSON arguments, id), `_run_tool` → `_call_tool` runs the matching tool and appends the result as `ToolMessage(json, tool_call_id=id)`. Every call goes through `TracedTools` (`trace.py`) and lands in the log with its arguments and result.

**Who decides which tool runs?**
The code decides the route: the model only names the intent in `RawRequest.intent`; `understand` turns it into `state["route"]` and can overrule it (a clarify question for an unclear place, a missing start, a follow-up on the plan). In `search`, `multiday`, `groups` and `events` the tool is fixed in code. Only in `react` does the model pick tools and arguments from `TOOL_SPECS`; even there the code searches the knowledge index first (`id: "vorab"`), stops at `max_tool_calls = 8` (that first search included), and without a source replies with a fixed sentence (`no_source_reply`).

**What role does JSON play?**
JSON is the interface between model and code in six places: (1) the JSON Schema of `RawRequest` and `TOOL_SPECS` to the model, (2) the model's output, validated by Pydantic (else `LLMBadOutput`), (3) tool arguments in `tool_calls`, (4) tool results (`_dump` → `json.dumps` into the `ToolMessage`, and `_walk` reads the evidence from them), (5) the `ChatEvent` events to the browser over SSE, (6) the log line in `chat.jsonl`. Because everything is typed (Pydantic), the code never sees free text where it expects data. Even the conversation state in the checkpointer is plain JSON (`model_dump(mode="json")`).

**What happens if the model invents a number?**
It is caught twice. When understanding, `understand.py: _constraints` keeps a number only if `_written` finds it in the message; otherwise it is dropped and logged as `discarded_model_numbers` (Titisee: eight invented zeros). In the answer, `grounding.py: grounding_check` finds every number with a unit and compares it with the evidence from this turn's tool results and the code's own sentences; an unsupported number is replaced by "?", with a note, and counted as `grounding_unsupported`. A walking time computed by `hiking_time` only counts as evidence if its inputs are evidence themselves (`_inputs_in_evidence`).

**Why not do everything with tool calling?**
Because the important decisions must be checkable and reproducible: which tours match, which are near misses, and why a tour fails is decided deterministically by `constraints.select` (sorted by score, distance and id). A model choosing its own tools could forget a condition, skip a search or sort differently, and every round costs tokens and time. This way a day hike needs exactly two model calls, the evaluation checks the results with code, and tool calling stays where the question is open (knowledge questions).

**What is LangGraph here, what does LangChain do, what OpenRouter?**
LangGraph is the flow: `StateGraph(State)` with twelve nodes, conditional edges on `state["route"]`, the `MemorySaver` checkpointer per conversation, and the custom stream (`get_stream_writer`) that carries the events (`graph.py: build_graph`). LangChain is the model layer: `ChatOpenAI`, the message classes (`SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage`), `with_structured_output` and `bind_tools` (`llm/gateway.py: OpenRouterGateway`). OpenRouter is the API provider: an OpenAI-compatible endpoint (`https://openrouter.ai/api/v1`) for `openai/gpt-4o-mini` that reports the cost of each call (`usage.include`) and provides the web search plugin used for running events (`web_completion`, engine `exa`).

**Does the model stream its answer live?**
No. The `token` events are created in `ground`, after the whole text has been checked; the code splits it into word chunks (`_CHUNK`). So no unsupported number can flash on the screen. `understood` and `results`, on the other hand, are sent as soon as the code has them.
