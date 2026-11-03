"""Video 3: how the AI works inside one chat turn (slides only, no running app), in English or German.

One chat message from the browser to the answer: request and server-sent events, the LangGraph graph, structured
output (RawRequest JSON Schema → model JSON → Pydantic), the number check, the search the graph calls itself, real
tool calling in react, evidence and grounding, and the log line. Code panels are read from the repository at
recording time (code_snippets.py); the JSON panels below are shortened copies of real data:
- the turn "A round walk near Titisee, about 10 km" of the user video (data/logs/chat.jsonl, 2026-11-03),
- a knowledge turn run through the real graph with real tools (database, knowledge index) and scripted model
  replies (FakeGateway), because the chat log holds no knowledge turn with tool calls yet (2026-11-03).
Keys and values are real; "…" marks what is left out.

Usage:
    python scripts/video/ai_demo.py --lang en   # out/hikesense-ai-en.mp4, voice en-GB-RyanNeural
    python scripts/video/ai_demo.py --lang de   # out/hikesense-ai-de.mp4, voice de-DE-ConradNeural
"""

from __future__ import annotations

import argparse
import asyncio
import json
from html import escape
from pathlib import Path

from code_snippets import Snippet, render_slides
from playwright.async_api import async_playwright
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer
from recorder import RATE, VOICE, H, Screencast, Segment, W, narrate, render, synthesize

VOICES = {"en": (VOICE, RATE), "de": ("de-DE-ConradNeural", "+5%")}

# --- narration ---------------------------------------------------------------------------------------------------

TEXT = {
    "en": {
        "a01": "HikeSense: how the AI works. This video follows one chat message through the system: how the "
        "browser talks to the API, how the LangGraph graph routes the message, why the model returns JSON instead "
        "of free text, how tools are called, and how the code checks every number before you see it.",
        "a02": "Here is the whole journey. The browser sends the message as JSON to the API. The API checks the "
        "sign-in token and a rate limit, then runs the LangGraph graph. For a day-hike search the model is usually "
        "called twice: once to understand the message, and once to word the answer. Everything in between, the "
        "search, the checks and the honest sentences, is ordinary Python. The results come back as a stream of "
        "small JSON events.",
        "a03": "The request is a small JSON body: a thread id, the message and the language, with the Supabase token "
        "in the header. FastAPI validates it with a Pydantic model. The answer is not one response but a stream of "
        "server-sent events. Each event is a Pydantic class, a ChatEvent, and the function underscore event turns "
        "it into JSON: understood, clarify, results, weather days, plan, groups, events, token, sources, done, or "
        "error. The web app draws the chips, the tour cards and the text from these events.",
        "a04": "Inside the API runs a LangGraph StateGraph with twelve nodes. Guard answers known prompt-injection "
        "patterns with a fixed reply, without a model. Understand decides the route and writes it into the state. "
        "A conditional edge reads it and picks exactly one worker: clarify, search, multiday, react, groups or "
        "events. Then come answer, ground and log. A checkpointer keeps the state of each conversation under the "
        "user hash and the thread id, so follow-up messages work.",
        "a05": "Understand makes at most one model call, and the answer must be JSON. The Pydantic class RawRequest "
        "is turned into a JSON Schema and sent to OpenRouter as a strict response format, at temperature zero. The "
        "model can only fill in this form: the intent, the start as free text, bounds for length, ascent and "
        "duration, and wishes. On the right is the real output for: a round walk near Titisee, about ten "
        "kilometres, taken from the chat log.",
        "a06": "In the code, this is the method structured of the OpenRouter gateway. LangChain's with structured "
        "output binds the schema to the model, and include raw keeps the raw reply, so tokens and cost can be "
        "counted. If the reply does not parse into the class, the gateway raises LLM bad output. So the rest of "
        "the graph never sees free text, only a validated Python object.",
        "a07": "But valid JSON is not yet correct JSON. Look at the real output: the model wrote zero for the "
        "ascent, the duration, the radius and the pace. Nobody asked for that. So the code reads the message "
        "itself and keeps a number only if the user wrote it. Eight model numbers were not in the message: they "
        "were dropped, and counted in the log. The ten, sent as minimum and maximum, became a band of plus or "
        "minus fifteen percent, and the code added the default radius of fifteen kilometres. Without this check, "
        "the search would run with conditions the user never set.",
        "a08": "Now the search. Here, the model does not choose a tool. The graph node search calls search day "
        "hikes itself, with the checked request as its argument. PostGIS finds the candidates, and constraints "
        "dot select checks every condition. The result is JSON again: matches, near misses, and rejected tours "
        "with the reason. From it, the code writes a short data block, and only this block goes to the model for "
        "wording.",
        "a09": "Real tool calling happens in one place: the react node, for knowledge questions. The tools are "
        "described in TOOL SPECS as OpenAI function specs: a name, a description, and the parameters as a JSON "
        "Schema. There are four: get trail details, find accommodation, hiking time to DIN three three four six "
        "six, and search knowledge. LangChain's bind tools sends this list with every model call of the loop.",
        "a10": "The loop works like this. Before the model is asked, the code itself searches the knowledge index, "
        "and puts the result into the conversation as if it were a first tool call. Then the model replies with an "
        "AI message. If it contains tool calls, each one has a name, arguments as JSON, and an id. The code runs "
        "the tool, turns the result into JSON, and sends it back as a tool message with the same id. This repeats "
        "until the model replies with text only, or until eight tool calls are used up, the code's own search "
        "included.",
        "a11": "Here is that loop in the code. tool round calls the model with the tool specs. No tool calls means: "
        "this text is the draft. Otherwise, run tool runs every call. A failing tool never stops the turn: the "
        "error goes back to the model as text. And if no tool result has a source, the reply is a fixed, honest "
        "sentence instead of a free answer.",
        "a12": "Every tool result is also evidence. The function walk goes through the JSON: a field ending in k m "
        "gives kilometres, ascent m gives metres of ascent, hours gives hours, and names are collected too. A "
        "walking time only counts if its inputs are evidence themselves. Then ground compares every number in the "
        "draft with this evidence. In this demo the model's replies were scripted, but the tools and the check "
        "are real: four hours with breaks is in no tool result, so it becomes a question mark, with a note.",
        "a13": "So what may the model write? Only the wording, from the data block, at temperature zero point "
        "three. The code's own sentences, like the fallback reason or the near-miss line, are put before and after "
        "the model's text, word for word. A claim like: no tour meets all your wishes, is removed unless the code "
        "said so, and a leaked system prompt is replaced. Only after this check is the text sent to the browser, "
        "as token events.",
        "a14": "Finally, log writes one JSON line per turn to chat dot JSON L: the request, the answer, every "
        "candidate, every model call with its exact messages, output, tokens, cost and duration, and every tool "
        "call with its arguments and result. The admin page reads this file, so every answer can be traced back "
        "to its data.",
        "a15": "To sum up, JSON appears six times: as the schema the model must fill in, as the model's output, as "
        "tool arguments, as tool results, as the events to the browser, and as the log line. And the division of "
        "labour stays the same: the model understands and words. The code decides the route, the tools, the "
        "numbers and the honest sentences. Thanks for watching.",
    },
    "de": {
        "a01": "HikeSense: So arbeitet die KI. Dieses Video verfolgt eine einzige Chatnachricht durch das "
        "System: wie der Browser mit der API spricht, wie der LangGraph-Graph die Nachricht weiterleitet, warum "
        "das Modell JSON statt freiem Text liefert, wie Tools aufgerufen werden, und wie der Code jede Zahl prüft, "
        "bevor sie auf dem Bildschirm erscheint.",
        "a02": "Zuerst der ganze Weg im Überblick. Der Browser schickt die Nachricht als JSON an die API. Die API "
        "prüft das Anmelde-Token und ein Ratenlimit und startet dann den LangGraph-Graphen. Bei einer "
        "Tagestour-Suche fragt sie das Modell meist genau zweimal: einmal, um die Nachricht zu verstehen, und "
        "einmal, um die Antwort zu formulieren. Alles dazwischen, also die Suche, die Prüfungen und die ehrlichen "
        "Sätze, ist ganz normaler Python-Code. Zurück kommt ein Strom kleiner JSON-Ereignisse.",
        "a03": "Die Anfrage ist ein kleiner JSON-Body: Thread-ID, Nachricht und Sprache, dazu das Supabase-Token im "
        "Header. FastAPI prüft ihn mit einem Pydantic-Modell. Die Antwort ist keine einzelne Response, sondern ein "
        "Strom aus Server-Sent Events. Jedes Ereignis ist eine Pydantic-Klasse, ein ChatEvent, und die Funktion "
        "event macht daraus JSON: understood, clarify, results, weather days, plan, groups, events, token, "
        "sources, done oder error. Aus diesen Ereignissen baut die Web-App die Chips, die Tourenkarten und den "
        "Text.",
        "a04": "In der API läuft ein LangGraph-StateGraph mit zwölf Knoten. Guard erkennt bekannte "
        "Prompt-Injection-Muster und antwortet dann mit einem festen Satz, ganz ohne Modell. Understand legt die "
        "Route fest und schreibt sie in den State. Eine bedingte Kante liest sie und wählt genau einen "
        "Arbeitsknoten: clarify, search, multiday, react, groups oder events. Danach folgen answer, ground und "
        "log. Ein Checkpointer speichert den Zustand jedes Gesprächs unter User-Hash und Thread-ID. Deshalb "
        "funktionieren Rückfragen und Folgenachrichten.",
        "a05": "Understand macht höchstens einen Modellaufruf, und die Antwort muss JSON sein. Aus der "
        "Pydantic-Klasse RawRequest wird ein JSON-Schema, das als strenges Antwortformat an OpenRouter geht, bei "
        "Temperatur null. Das Modell kann nur dieses Formular ausfüllen: die Absicht, den Startort als freien "
        "Text, Grenzen für Länge, Anstieg und Dauer, und Wünsche. Rechts steht die echte Ausgabe aus dem Chat-Log, "
        "für die Nachricht: A round walk near Titisee, about 10 km.",
        "a06": "Im Code ist das die Methode structured des OpenRouter-Gateways. LangChains with structured output "
        "bindet das Schema an das Modell, und include raw behält die Rohantwort, damit Tokens und Kosten gezählt "
        "werden. Lässt sich die Antwort nicht in die Klasse übersetzen, wirft das Gateway LLM Bad Output. Der Rest "
        "des Graphen sieht also nie freien Text, sondern nur ein geprüftes Python-Objekt.",
        "a07": "Gültiges JSON heißt aber noch nicht, dass der Inhalt stimmt. In der echten Ausgabe hat das Modell "
        "für Anstieg, Dauer, Umkreis und Tempo jeweils null eingetragen, obwohl niemand danach gefragt hat. Der "
        "Code liest deshalb selbst aus der Nachricht, welche Zahlen wirklich dastehen. Acht Modellzahlen standen "
        "nicht in der Nachricht: Sie wurden verworfen und im Log gezählt. Die Zehn, die als Minimum und Maximum "
        "kam, wird zu einem Band von plus minus fünfzehn Prozent, und der Code ergänzt den Standard-Umkreis von "
        "fünfzehn Kilometern. Ohne diese Prüfung liefe die Suche mit Bedingungen, die nie jemand gestellt hat.",
        "a08": "Jetzt die Suche. Hier wählt das Modell kein Tool. Der Knoten search ruft search day hikes selbst "
        "auf, mit der geprüften Anfrage als Argument. PostGIS findet die Kandidaten, und constraints punkt select "
        "prüft jede Bedingung. Das Ergebnis ist wieder JSON: Treffer, knapp daneben, und abgelehnte Touren mit "
        "Grund. Daraus schreibt der Code einen kurzen Datenblock, und nur dieser Block geht zum Formulieren an das "
        "Modell.",
        "a09": "Echtes Tool-Calling gibt es an genau einer Stelle: im Knoten react, für Wissensfragen. Die Tools "
        "stehen in TOOL SPECS als OpenAI-Funktionsbeschreibungen: ein Name, eine Beschreibung, und die Parameter "
        "als JSON-Schema. Es sind vier: get trail details, find accommodation, hiking time nach DIN drei drei vier "
        "sechs sechs, und search knowledge. LangChains bind tools schickt diese Liste bei jedem Modellaufruf der "
        "Schleife mit.",
        "a10": "Die Schleife läuft so. Bevor das Modell gefragt wird, durchsucht der Code selbst den Wissensindex "
        "und legt das Ergebnis ins Gespräch, als wäre es ein erster Tool-Aufruf. Dann antwortet das Modell mit "
        "einer AI-Message. Enthält sie Tool-Calls, hat jeder einen Namen, Argumente als JSON und eine ID. Der Code "
        "führt das Tool aus, macht aus dem Ergebnis JSON und schickt es als Tool-Message mit derselben ID zurück. "
        "Das wiederholt sich, bis das Modell nur noch Text liefert, oder bis acht Tool-Aufrufe verbraucht sind, "
        "die Vorab-Suche des Codes mitgezählt.",
        "a11": "So sieht die Schleife im Code aus. tool round ruft das Modell mit den Tool-Beschreibungen auf. Keine "
        "Tool-Calls heißt: Dieser Text ist der Entwurf. Sonst führt run tool jeden Aufruf aus. Ein fehlerhaftes "
        "Tool bricht den Durchlauf nie ab: Der Fehler geht als Text zurück ans Modell. Und hat kein "
        "Tool-Ergebnis eine Quelle, kommt statt einer freien Antwort ein fester, ehrlicher Satz.",
        "a12": "Jedes Tool-Ergebnis ist zugleich ein Beleg. Die Funktion walk geht durch das JSON: Ein Feld, das auf "
        "k m endet, liefert Kilometer, ascent m liefert Höhenmeter, hours liefert Stunden, und Namen werden "
        "ebenfalls gesammelt. Eine Gehzeit zählt nur, wenn ihre Eingaben selbst belegt sind. Danach vergleicht "
        "ground jede Zahl im Entwurf mit diesen Belegen. In dieser Demo sind die Antworten des Modells vorgegeben, "
        "die Tools und die Prüfung aber echt: Vier Stunden mit Pausen stehen in keinem Tool-Ergebnis. Also wird "
        "daraus ein Fragezeichen, mit Hinweis.",
        "a13": "Was darf das Modell also schreiben? Nur die Formulierung, aus dem Datenblock, bei Temperatur null "
        "Komma drei. Die eigenen Sätze des Codes, etwa der Grund für Ausweichtouren oder der Satz zu knapp "
        "daneben, stehen wörtlich vor und hinter dem Modelltext. Eine Behauptung wie: keine Tour erfüllt alle "
        "Wünsche, wird entfernt, wenn der Code das nicht gesagt hat, und ein durchgesickerter Systemprompt wird "
        "ersetzt. Erst nach dieser Prüfung geht der Text als Token-Ereignisse an den Browser.",
        "a14": "Zum Schluss schreibt log pro Durchlauf eine JSON-Zeile in die Datei chat punkt JSON L: die Anfrage, "
        "die Antwort, alle Kandidaten, jeden Modellaufruf mit den exakten Nachrichten, Ausgabe, Tokens, Kosten und "
        "Dauer, und jeden Tool-Aufruf mit Argumenten und Ergebnis. Die Admin-Seite liest diese Datei. So lässt "
        "sich jede Antwort bis zu ihren Daten zurückverfolgen.",
        "a15": "Zusammengefasst taucht JSON sechsmal auf: als Schema, das das Modell ausfüllen muss, als Ausgabe des "
        "Modells, als Tool-Argumente, als Tool-Ergebnisse, als Ereignisse an den Browser, und als Log-Zeile. Und "
        "die Arbeitsteilung bleibt immer gleich: Das Modell versteht und formuliert. Der Code entscheidet über "
        "Route, Tools, Zahlen und die ehrlichen Sätze. Danke fürs Zuschauen.",
    },
}

# --- code panels (read from the repository at recording time) ----------------------------------------------------

A = "backend/src/hikesense/agent/"
CODE = {
    "a03c": [Snippet("backend/src/hikesense/api/chat.py", "_event", mark=["model_dump_json"])],
    "a05c": [Snippet(A + "request.py", start="class RawRequest(BaseModel):", end="length_km_max: float")],
    "a06": [
        Snippet("backend/src/hikesense/llm/gateway.py", start="        messages = [SystemMessage(system), HumanMessage(user)]",
                end='raise LLMBadOutput("', mark=["with_structured_output", "LLMBadOutput", "parsed = "]),
        Snippet(A + "understand.py", "parse", mark=["gw.structured("]),
    ],
    "a08c": [Snippet(A + "graph.py", start='        req = HikeRequest.model_validate(state["current"])',
                     end="result = tools.search_day_hikes(req, lang)",
                     mark=["tools.search_day_hikes("])],
    "a11": [
        Snippet(A + "graph.py", start="        for _ in range(settings.max_tool_calls + 2):",
                end='messages.append(ToolMessage(content[0], tool_call_id=call["id"]))',
                mark=["gw.tool_round(", "if not ai.tool_calls", "tool_call_id="]),
    ],
}  # fmt: skip

# --- JSON panels: shortened real data (keys real; ... marks what is left out) ------------------------------------

E = ...  # rendered as "…"

TITISEE_OUTPUT = {  # data/logs/chat.jsonl, "A round walk near Titisee, about 10 km": llm_calls[0].output
    "intent": "day_hike", "activity": "hike", "start_text": "Titisee", "roundtrip": True,
    "length_km_min": 10.0, "length_km_max": 10.0, "ascent_m_min": 0.0, "ascent_m_max": 0.0,
    "duration_h_min": 0.0, "duration_h_max": 0.0, "length_km_approx": 10.0, "ascent_m_approx": 0.0,
    "duration_h_approx": 0.0, "radius_km_max": 0.0, "pace_min_per_km": 0.0, "trail_text": None, "days": None,
    "day_km": None, "start_date": None, "start_time": None, "day_change_day": None, "day_change_direction": None,
    "weather_wish": None, "wishes": [], "question": None,
}  # fmt: skip

SCHEMA = {  # what the OpenAI SDK sends for RawRequest (LangChain with_structured_output, method json_schema)
    "type": "json_schema",
    "json_schema": {
        "name": "RawRequest", "strict": True,
        "schema": {
            "type": "object", "additionalProperties": False,
            "required": ["intent", "activity", "start_text", E],
            "properties": {
                "intent": {"enum": ["day_hike", "multiday", "knowledge", E], "type": "string"},
                "start_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                E: E,
            },
        },
    },
}  # fmt: skip

CONSTRAINTS = {  # the resolved HikeRequest of the same turn (request in the log)
    "start": {"kind": "place", "tag_id": "place:titisee", "label": "Titisee", "lat": 47.9011491, "lon": 8.1499728},
    "constraints": [
        {"kind": "roundtrip", "required": True},
        {"kind": "length_km", "min": 8.5, "max": 11.5, "approx": 10.0},
        {"kind": "radius_km", "max": 15.0},
    ],
    "discarded_model_numbers": 8,
}  # fmt: skip

SEARCH_ARGS = {"arg0": {
    "intent": "day_hike", "start": {"kind": "place", "label": "Titisee", E: E},
    "constraints": [{"kind": "roundtrip", "required": True, E: E},
                    {"kind": "length_km", "min": 8.5, "max": 11.5, "approx": 10.0, E: E},
                    {"kind": "radius_km", "max": 15.0, E: E}],
    E: E}}  # fmt: skip

SEARCH_RESULT = {"selection": {
    "matches": [{
        "candidate": {"trail_id": "day-12013912", "name": "Genießerpfad - Säbelthomaweg", "length_km": 11.44,
                      "ascent_m": 389, E: E},
        "results": [{"kind": "length_km", "ok": True, "actual": 11.44, "bound": "at least 8.5 and at most 11.5"}, E],
        E: E}, E],
    "fallbacks": [], "reason": None,
    "rejected": [{"candidate": {"name": "Genießerpfad - Jägersteig", "length_km": 11.57, E: E},
                  "results": [{"kind": "length_km", "ok": False, "actual": 11.57, "bound": "at most 11.5"}, E]}, E],
    E: E}, "searched_radius_km": 15.0, E: E}  # fmt: skip

DATA_BLOCK = (  # llm_calls[1] (answer): the user message the code built
    "Understood: day hike, walking, start: Titisee, round walk, length 8.5–11.5 km (≈ 10 km), radius at most 15 km.\n"
    "Matching tours (sorted by preferences):\n"
    "1. Genießerpfad - Säbelthomaweg – length 11.4 km, ascent 389 m, walking time 3.9 h, distance to the start "
    "3.5 km; conditions: round walk met; length met; distance met\n"
    "2. …"
)

HIKING_TIME_SPEC = {  # TOOL_SPECS[2] as bind_tools sends it
    "type": "function",
    "function": {
        "name": "hiking_time",
        "description": "Berechnet die Gehzeit nach DIN 33466 (ohne Pausen) aus …",
        "parameters": {
            "type": "object",
            "properties": {"length_km": {"type": "number"}, "ascent_m": {"type": "number"},
                           "descent_m": {"type": "number"}},
            "required": ["length_km", "ascent_m", "descent_m"],
        },
    },
}  # fmt: skip

TRAIL_DETAILS = {"trail_id": "day-12013547", "name": "Genießerpfad - Menzenschwander Geißenpfad",
                 "length_km": 9.78, "ascent_m": 278, "descent_m": 277, "roundtrip": True,
                 "surface_shares": {"paved": 0.148, "gravel": 0.618, E: E},
                 "pois": [{"name": "Hotel Hirschen", "kind": "food", "dist_m": 286, "along_km": 0.379}, E], E: E}  # fmt: skip
HIKING_TIME = {"hours": 3.19, "horizontal_h": 2.44, "vertical_h": 1.48, "formula": "max(h, v) + min(h, v) / 2 …"}

LOG_LINE = {
    "ts": "2026-11-03T00:34:37+00:00", "intent": "day_hike", "tool_calls": 1,
    "input_tokens": 1916, "output_tokens": 317, "cost_usd": 0.0003816,
    "discarded_model_numbers": 8, "grounding_unsupported": 0,
    "message": "A round walk near Titisee, about 10 km", "request": {E: E}, "answer": "Here are some …",
    "candidates": [{"name": "Genießerpfad - Säbelthomaweg", "status": "shown", E: E}, E], E: E,
    "llm_calls": [
        {"step": "understand", "model": "openai/gpt-4o-mini", "messages": [{"role": "system", E: E}, E],
         "output": {"intent": "day_hike", E: E}, "input_tokens": 1435, "output_tokens": 153,
         "cost_usd": 0.00021105, "duration_ms": 2074},
        {"step": "answer", "input_tokens": 481, "output_tokens": 164, "cost_usd": 0.00017055, "duration_ms": 1859, E: E},
    ],
    "tools": [{"name": "search_day_hikes", "args": {"arg0": {E: E}}, "result": "{\"selection\": …}",
               "truncated": True, "duration_ms": 93}],
    "duration_ms": 4071,
}  # fmt: skip


def _inline(o) -> str:
    if o is E:
        return "…"
    if isinstance(o, dict):
        return "{" + ", ".join("…" if k is E else f"{json.dumps(k)}: {_inline(v)}" for k, v in o.items()) + "}"
    if isinstance(o, list):
        return "[" + ", ".join(_inline(x) for x in o) + "]"
    return json.dumps(o, ensure_ascii=False)


def _block(o, indent: int, width: int, lead: int = 0, pack: bool = False) -> list[str]:
    """Pretty JSON: an object or array stays on one line if it fits in `width` (after `lead` characters of key on
    its first line), else one item per line; pack=True puts several short scalar items of an object on one line."""
    one = _inline(o)
    if len(one) + indent + lead <= width or not isinstance(o, (dict, list)) or not o:
        return [one]
    pad = " " * (indent + 2)
    items = list(o.items()) if isinstance(o, dict) else [(None, x) for x in o]
    lines = ["{" if isinstance(o, dict) else "["]
    packing = False  # the last line holds packed scalar items
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if k is E:
            if pack and len(lines) > 1 and len(lines[-1]) + 2 + len(comma) <= width:
                lines[-1] += " …" + comma
            else:
                lines.append(pad + "…" + comma)
                packing = False
            continue
        key = f"{json.dumps(k, ensure_ascii=False)}: " if isinstance(o, dict) else ""
        if pack and key and not isinstance(v, (dict, list)):
            item = key + _inline(v) + comma
            if packing and len(lines[-1]) + 1 + len(item) <= width:
                lines[-1] += " " + item
            else:
                lines.append(pad + item)
            packing = True
            continue
        packing = False
        sub = _block(v, indent + 2, width, len(key), pack)
        lines.append(pad + key + sub[0])
        lines += sub[1:-1]
        if len(sub) > 1:
            lines.append(sub[-1])
        lines[-1] += comma
    lines.append(" " * indent + ("}" if isinstance(o, dict) else "]"))
    return lines


def _hl(code: str, lexer, mark: list[str]) -> str:
    marked = [i for i, line in enumerate(code.splitlines(), 1) if any(m in line for m in mark)]
    return highlight(code + "\n", lexer, HtmlFormatter(hl_lines=marked, cssclass="src"))


def jpanel(head: str, obj, mark: list[str] = (), width: int = 64, pack: bool = False) -> str:
    code = "\n".join(_block(obj, 0, width, pack=pack))
    return f'<div class="codehead">{escape(head)}</div>{_hl(code, JsonLexer(), list(mark))}'


def tpanel(head: str, text: str) -> str:
    return f'<div class="codehead">{escape(head)}</div><div class="src"><pre class="txt">{escape(text)}</pre></div>'


def sse_panel(head: str, events: list[tuple[str, dict]]) -> str:
    rows = []
    for name, data in events:
        js = highlight(_inline(data), JsonLexer(), HtmlFormatter(nowrap=True))
        rows.append(f'<span class="ev">event: {escape(name)}</span>\n<span class="dl">data: </span>{js.rstrip()}')
    return f'<div class="codehead">{escape(head)}</div><div class="src"><pre class="sse">' + "\n\n".join(rows) + "</pre></div>"


LOG = "data/logs/chat.jsonl"
SHORT = {"en": "shortened", "de": "gekürzt"}


def panels(lang: str) -> dict[str, list[str]]:
    s = SHORT[lang]
    demo = {"en": "demo turn · real tools, scripted model", "de": "Demo · echte Tools, vorgegebenes Modell"}[lang]
    request = {"thread_id": "6f0c2a1e-…", "message": "A round walk near Titisee, about 10 km", "lang": "en"}
    events = [
        ("understood", {"type": "understood", "text": "Understood: day hike, walking, start: Titisee, round walk, …",
                        "request": {"intent": "day_hike", E: E}, "labels": {}}),
        ("results", {"type": "results", "cards": [{"trail_id": "day-12013912", "name": "Genießerpfad - Säbelthomaweg",
                     "length_km": 11.44, "ascent_m": 389, E: E}, E], "fallback_reason": None}),
        ("token", {"type": "token", "text": "Here "}),
        ("token", {"type": "token", "text": "are "}),
        ("sources", {"type": "sources", "sources": [{"id": "osm", "license": "ODbL", E: E}]}),
        ("done", {"type": "done", "usage": {"input_tokens": 1916, "output_tokens": 317, "cost_usd": 0.0003816, E: E},
                  "unsupported": 0}),
    ]  # fmt: skip
    return {
        "a03L": [jpanel("POST /chat · Authorization: Bearer <Supabase JWT>", request, width=46)],
        "a03R": [sse_panel(f"text/event-stream · {s}", events)],
        "a05L": [jpanel(f"response_format → OpenRouter · {s}", SCHEMA, width=86)],
        "a05R": [jpanel(f"{LOG} · llm_calls[0].output", TITISEE_OUTPUT, width=40, mark=['"intent"'])],
        "a07L": [jpanel(f"llm_calls[0].output · {s}", {k: TITISEE_OUTPUT[k] for k in list(TITISEE_OUTPUT)[3:15]},
                        width=40, mark=['": 0.0'])],
        "a07R": [jpanel(f"{LOG} · request · {s}", CONSTRAINTS, width=70, pack=True, mark=["8.5", "15.0", "discarded"])],
        "a08L": [jpanel(f"tools[0].args · {s}", SEARCH_ARGS, width=66, pack=True)],
        "a13d": [tpanel(f"llm_calls[1] (answer) · user message · {s}", DATA_BLOCK)],
        "a08R": [jpanel(f"tools[0].result · {s}", SEARCH_RESULT, width=86, pack=True, mark=['"ok": false'])],
        "a09L": [jpanel("agent/tools.py · TOOL_SPECS[2] → bind_tools", HIKING_TIME_SPEC, width=72)],
        "a12L": [jpanel(f"get_trail_details · {demo}", TRAIL_DETAILS, width=60, pack=True, mark=["length_km", "_m\":"]),
                 jpanel("hiking_time", HIKING_TIME, width=60, mark=["hours"])],
        "a14L": [jpanel(f"{LOG} · {s}", LOG_LINE, width=78, pack=True, mark=['"llm_calls"', '"tools"'])],
    }


async def main(lang: str, out: Path) -> None:
    work = out / f"work-ai-{lang}"
    segments = [Segment(k, v) for k, v in TEXT[lang].items()]
    voice, rate = VOICES[lang]
    await synthesize(segments, work / "voice", voice, rate)
    for s in segments:
        print(f"{s.key}: {s.duration:5.1f}s")
    print(f"voice total {sum(s.duration for s in segments):.0f}s")
    shots = out / "shots"
    if not (shots / "admin-model.jpg").exists():
        raise SystemExit("missing out/shots/admin-model.jpg: run user_demo.py or tech_demo.py first")
    slides = (Path(__file__).parent / "ai_slides.html").resolve()
    code = render_slides(CODE) | panels(lang)
    pad = 1.2
    async with async_playwright() as p:
        browser = await p.chromium.launch()  # slides: 1920 × 1080 CSS pixels, no scale flag
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        await page.goto(slides.as_uri())
        await page.wait_for_load_state("networkidle")
        await page.evaluate("([lang, code]) => { setLang(lang); fillCode(code); }", [lang, code])
        await page.wait_for_timeout(1500)
        rec = Screencast(page, work / "frames")
        await page.evaluate("go('none')")
        await rec.start()
        for s in segments:
            await page.evaluate(f"go('{s.key}', {s.duration + pad:.2f})")
            await narrate(rec, s, pad=pad)
        await rec.stop(tail=1.5)
        await browser.close()
    target = out / f"hikesense-ai-{lang}.mp4"
    render(rec, segments, target)
    print("wrote", target, f"{rec.shift(rec.end):.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["en", "de"], default="en")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    args = ap.parse_args()
    asyncio.run(main(args.lang, args.out.resolve()))
