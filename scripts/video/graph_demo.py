"""Video 4: LangGraph on two examples – agentic vs generative AI, ReAct, and the state through the graph.

Slides only (graph_slides.html), in English or German. Code panels are read from the repository at recording time
(code_snippets.py). Every state snapshot, model output, message list and event on the example slides is read from
data/graph_runs.json: real turns through the compiled graph with the real model (openai/gpt-4o-mini via OpenRouter),
the real database and the real knowledge index, recorded on 2026-11-03 by data/capture_graph.py:
  1. "A round walk near Titisee, about 10 km"             (thread titisee)
  2. "Under 300 m ascent, please"                          (same thread: checkpointer)
  3. "How long does the first tour take, and where can I stay near it?"   (same thread: react)
  4. "How is the Westweg waymarked?"                        (new thread: react, no extra tool)
Panels are shortened ("…" marks what is left out); keys and values are real. The model's wording varies between
runs, so the narration describes what it did in this recorded run.

Usage:
    python scripts/video/graph_demo.py --lang en   # out/hikesense-graph-en.mp4, voice en-GB-RyanNeural
    python scripts/video/graph_demo.py --lang de   # out/hikesense-graph-de.mp4, voice de-DE-ConradNeural
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from html import escape
from pathlib import Path

from ai_demo import E, jpanel, tpanel
from code_snippets import Snippet, render_slides
from playwright.async_api import async_playwright
from recorder import VOICE, H, Screencast, Segment, W, narrate, render, synthesize

VOICES = {"en": (VOICE, "+12%"), "de": ("de-DE-ConradNeural", "+14%")}
HERE = Path(__file__).parent
RUNS = json.loads((HERE / "data" / "graph_runs.json").read_text(encoding="utf-8"))

# --- narration ---------------------------------------------------------------------------------------------------

TEXT = {
    "en": {
        "g01": "HikeSense: LangGraph on two examples. This video follows the state through the graph, node by "
        "node, for real runs with the real model, GPT-4o mini. First a day-hike search with a follow-up, then a "
        "knowledge question that the model answers with tool calls. Along the way: what makes an AI system "
        "agentic, what ReAct means, where this project uses it, and where it deliberately does not.",
        "g02": "First, two terms. Generative AI, in its simplest form, is one model call: a prompt goes in, text "
        "comes out. An agent wraps the model "
        "in a loop: it has tools it can call, a state it carries from step to step, and at every step something "
        "decides what happens next. The key question is: who decides? In a workflow, the path is written in code. "
        "In an agent, the model chooses the next action itself.",
        "g03": "The best-known agent pattern is ReAct, short for reason and act. The model reasons about the "
        "question, then acts: it asks for a tool call. The program runs the tool and hands back the result. That is "
        "the observation. With the observation in its context, the model reasons again, and either calls another "
        "tool or answers. This repeats until the model replies with text only, or until a limit stops it.",
        "g04": "This project is a hybrid. The outer structure is a LangGraph state machine: a fixed set of nodes and "
        "edges. Which edge is taken is decided by code, from the model's structured understanding of the message. "
        "Only inside one node, react, runs a real ReAct loop, where the model picks the tools. Why not make "
        "everything an agent? Reliability: a tour search must check every condition, every time. Grounding: every "
        "number must come from data. Cost: each round costs tokens and time. And testability: a fixed path can be "
        "evaluated with code. In short: the code decides, the model words it.",
        "g05": "Now LangGraph, as it is used here. The state is a typed dictionary, State, in graph dot p y: the "
        "message, the language, the route, the request, the evidence, the draft, the final text, and more. A node "
        "is a plain Python function. It receives the whole state and returns only the keys it changes: a partial "
        "update. LangGraph merges the update into the state. No reducers are defined, so a returned key simply "
        "replaces the old value. On the right, the smallest node: guard.",
        "g06": "The graph is built in build graph. StateGraph of State creates it, add node registers the twelve "
        "functions, and add edge connects them: START to guard, search to answer, answer to ground, ground to log, "
        "and log to END. The branches are conditional edges: add conditional edges, with a small function that "
        "only reads state route. So the node understand writes the route, and the edge just follows it. Compile "
        "turns all this into a runnable graph, with a checkpointer.",
        "g07": "Two more pieces. First, streaming. The API runs graph dot stream with stream mode custom. Inside a "
        "node, emit calls LangGraph's get stream writer, and every ChatEvent goes to the browser at once, while the "
        "graph is still running. Second, the checkpointer. Each run has a thread id, made of the user hash and the "
        "conversation id. After every node, LangGraph saves the state under this id. The next message starts from "
        "the saved state. Its input resets only the per-message keys, so request, last tours and history survive. "
        "That is how follow-up questions work.",
        "g08": "Example one: A round walk near Titisee, about ten kilometres. The run takes the path guard, "
        "understand, search, answer, ground and log. This table is the real run: per node, what it reads, whether it calls the model or a tool, which keys it writes, and which event it sends. Two model calls, one tool call, and that tool call is made by the graph itself, not "
        "chosen by the model.",
        "g09": "Guard finds no injection pattern and writes route understand. Understand is where the route of this "
        "turn is decided. It makes one structured-output call: the model fills in the RawRequest form. Intent day "
        "hike, start Titisee, round walk, ten kilometres, and eight zeros nobody asked for. Then code takes over. "
        "Resolve keeps only the numbers the user wrote and drops the eight zeros, turns the ten into a band from "
        "eight point five to eleven point five, finds Titisee in the place vocabulary, and adds the default radius. "
        "The node sends the understood event, and writes current, request, and route search.",
        "g10": "Search is a code node. It reads current, validates it into a HikeRequest, and calls search day hikes "
        "directly, as a Python function: PostGIS finds the candidates, and constraints dot select checks every "
        "condition. There is no model here, and no tool call chosen by a model. The node sends the results event "
        "with three tour cards, and writes back: one tool call, the three last tours with their ids, the "
        "candidates for the log, the evidence, which is every number the answer may use, and data, the short text "
        "block for the model.",
        "g11": "Answer reads data and makes the second model call, at temperature zero point three. The model only "
        "words the data block, and the node writes draft. Ground is code again: it compares every number in the "
        "draft with the evidence. Here all of them are supported, so unsupported is zero. It puts the code's own "
        "sentences around the text, writes final text, and only now sends the text to the browser as token "
        "events, in word chunks, followed by the sources. Log "
        "writes one JSON line, sends done with tokens and cost, and returns an empty update.",
        "g12": "Now a follow-up in the same thread: Under three hundred metres ascent, please. The checkpointer already holds the previous request, the last tours, and the history. Understand gives "
        "the previous request to the model, which answers with intent change and an ascent of at most three "
        "hundred. The code merges this into the stored request: same start, same length band, plus the new ascent "
        "bound. Search runs again. Two tours now match, and the Jägersteig is shown as a near miss: eleven point six "
        "kilometres instead of at most eleven point five. Again, no ReAct: two model calls, one tool call by the "
        "graph.",
        "g13": "Example two continues the same conversation: How long does the first tour take, and where can I stay "
        "near it? In understand, the model says intent knowledge, and copies seven numbers "
        "from the previous request, which the code drops. The code writes route react. So the path is now guard, "
        "understand, react, answer, ground and log. And this time, inside react, the model decides which tools to "
        "call.",
        "g14": "Inside react, the code builds a list of LangChain messages. One: the system prompt with the rules. "
        "Use the tools, and every number must come from a tool result. Two: the tours suggested last, with their "
        "ids, taken from the checkpointed state. Three: the question. Then the code acts first. Four and five are "
        "its own knowledge search, written like a tool call with the id vorab, and its result. Round one: the model reasons that the first tour is the Menzenschwander "
        "Geißenpfad, and acts with two tool calls at once: get trail details and find accommodation, both with its "
        "trail id. The code observes: it runs both tools, and appends two tool messages with the matching ids. "
        "Round two: the model has what it needs, and replies with text only. No tool calls means: stop, this is "
        "the draft.",
        "g15": "Here is the loop in the code. g w dot tool round sends the message list, with the tool specs bound. "
        "If the reply has no tool calls, its text is the draft, and the loop ends. Otherwise, run tool executes "
        "every call, and its result goes back as a ToolMessage with the call's id. The code counts the calls: "
        "three in this run, out of a limit of eight, the code's own search included. A failing tool goes back to "
        "the model as text, and without any sourced result, the code answers with a fixed sentence instead.",
        "g16": "React writes tool calls three, the sources, the evidence collected from every tool result, and the "
        "draft. Answer sees that a draft exists and returns an empty update: no extra model call for the wording. "
        "Now ground does its job. The model did not call hiking time. Instead, it wrote: about two hours and thirty "
        "minutes. That duration is in no tool result, so ground replaces it with question marks and adds a note. "
        "The length, nine point seven eight kilometres, and the guest houses with their distances are evidence, so "
        "they stay. Three model calls in total, for less than a tenth of a cent.",
        "g17": "A second knowledge run, in a new thread: How is the Westweg waymarked? There are no last tours, so the "
        "list has no tour message. The code's own search finds passages about the Westweg from Wikivoyage and "
        "Wikipedia. In round one, the model answers directly, without calling any tool. So a ReAct loop can end "
        "after a single round, when the model decides that what it already observed is enough. And one honest "
        "limit: grounding checks numbers and names, not every claim. The passages do not describe the waymark, so "
        "the answer stays vague.",
        "g18": "To sum up. The model acts in three places: in understand, where it fills in a form; in the react "
        "rounds, where it chooses tools and arguments; and in answer, where it words a data block. The code decides "
        "everything else: the route, the search and its conditions, the multi-day planning, the first knowledge "
        "search, the limit of eight calls, and the check of every number. So the system is agentic where the "
        "question is open, and a fixed workflow where the results must be checkable.",
        "g19": "And this is how to explain it in one minute. HikeSense is a LangGraph state machine with twelve "
        "nodes. One structured model call understands the message; code checks it and picks the route. For tour "
        "searches, the graph calls the search itself, and the model only words the result. For open knowledge "
        "questions, a ReAct loop lets the model call four tools, at most eight times. Every number in the answer is "
        "checked against tool results before it is shown, and a checkpointer per thread makes follow-ups work. The "
        "code decides, the model words it. Thanks for watching.",
    },
    "de": {
        "g01": "HikeSense: LangGraph an zwei Beispielen. Dieses Video verfolgt den Zustand durch den Graphen, "
        "Knoten für Knoten, an echten Durchläufen mit dem echten Modell, GPT-4o mini. Zuerst eine "
        "Tagestour-Suche mit einer Folgefrage, dann eine Wissensfrage, die das Modell mit Tool-Aufrufen "
        "beantwortet. Unterwegs klären wir: Was macht ein KI-System agentisch, was bedeutet ReAct, wo nutzt dieses "
        "Projekt es, und wo bewusst nicht.",
        "g02": "Zuerst zwei Begriffe. Generative KI ist in ihrer einfachsten Form ein einziger Modellaufruf: Ein "
        "Prompt geht hinein, Text kommt heraus. Ein Agent legt eine Schleife um das Modell: Er hat Tools, die er aufrufen kann, einen "
        "Zustand, den er von Schritt zu Schritt mitnimmt, und bei jedem Schritt entscheidet etwas, wie es "
        "weitergeht. Die entscheidende Frage ist: Wer entscheidet? In einem Workflow steht der Weg im Code. In "
        "einem Agenten wählt das Modell die nächste Aktion selbst.",
        "g03": "Das bekannteste Agenten-Muster heißt ReAct, kurz für Reason and Act, also Überlegen und Handeln. Das "
        "Modell überlegt, was die Frage braucht, und handelt dann: Es verlangt einen Tool-Aufruf. Das Programm "
        "führt das Tool aus und gibt das Ergebnis zurück. Das ist die Beobachtung. Mit dieser Beobachtung im "
        "Kontext überlegt das Modell erneut und ruft entweder ein weiteres Tool auf oder antwortet. Das wiederholt "
        "sich, bis das Modell nur noch Text liefert, oder bis ein Limit greift.",
        "g04": "Dieses Projekt ist ein Hybrid. Die äußere Struktur ist eine LangGraph-Zustandsmaschine: feste Knoten "
        "und feste Kanten. Welche Kante genommen wird, entscheidet der Code, anhand des strukturierten "
        "Verständnisses, das das Modell von der Nachricht liefert. Nur in einem einzigen Knoten, react, läuft eine "
        "echte ReAct-Schleife, in der das Modell die Tools wählt. Warum nicht alles als Agent? Zuverlässigkeit: "
        "Eine Tourensuche muss jede Bedingung prüfen, jedes Mal. Grounding: Jede Zahl muss aus den Daten kommen. "
        "Kosten: Jede Runde kostet Tokens und Zeit. Und Testbarkeit: Einen festen Weg kann man mit Code "
        "evaluieren. Kurz: Der Code entscheidet, das Modell formuliert.",
        "g05": "Jetzt LangGraph, so wie es hier genutzt wird. Der Zustand ist ein typisiertes Dictionary, State, in "
        "graph punkt p y: die Nachricht, die Sprache, die Route, die Anfrage, die Belege, der Entwurf, der "
        "endgültige Text und mehr. Ein Knoten ist eine ganz normale Python-Funktion. Er bekommt den ganzen Zustand "
        "und gibt nur die Schlüssel zurück, die er ändert: ein Teil-Update. LangGraph führt dieses Update in den "
        "Zustand zusammen. Reducer sind nicht definiert, also ersetzt ein zurückgegebener Schlüssel einfach den "
        "alten Wert. Rechts der kleinste Knoten: guard.",
        "g06": "Gebaut wird der Graph in build graph. StateGraph von State legt ihn an, add node registriert die "
        "zwölf Funktionen, und add edge verbindet sie: START mit guard, search mit answer, answer mit ground, "
        "ground mit log, und log mit END. Die Verzweigungen sind bedingte Kanten: add conditional edges, mit einer "
        "kleinen Funktion, die nur state route liest. Der Knoten understand schreibt also die Route, und die Kante "
        "folgt ihr nur. Compile macht daraus einen ausführbaren Graphen, mit Checkpointer.",
        "g07": "Zwei weitere Bausteine. Erstens das Streaming. Die API startet graph punkt stream mit dem Stream-Modus "
        "custom. In einem Knoten ruft emit LangGraphs get stream writer auf, und jedes ChatEvent geht sofort an den "
        "Browser, während der Graph noch läuft. Zweitens der Checkpointer. Jeder Durchlauf hat eine Thread-ID, "
        "gebildet aus User-Hash und Gesprächs-ID. Nach jedem Knoten speichert LangGraph den Zustand unter dieser "
        "ID. Die nächste Nachricht startet von diesem gespeicherten Zustand. Ihre Eingabe setzt nur die Schlüssel "
        "pro Nachricht zurück, also bleiben Anfrage, letzte Touren und Verlauf erhalten. So funktionieren "
        "Folgefragen.",
        "g08": "Beispiel eins: A round walk near Titisee, about 10 km. Der Durchlauf nimmt den Weg guard, understand, search, answer, ground und log. Die Tabelle zeigt den echten Durchlauf: pro Knoten, was er liest, ob er Modell oder Tool aufruft, welche Schlüssel er schreibt und welches Ereignis er schickt. Zwei Modellaufrufe, ein Tool-Aufruf, und diesen Tool-Aufruf macht der Graph selbst, nicht das "
        "Modell.",
        "g09": "Guard findet kein Injection-Muster und schreibt die Route understand. In understand wird die Route "
        "dieses Durchlaufs entschieden. Der Knoten macht einen Aufruf mit strukturierter Ausgabe: Das Modell füllt "
        "das Formular RawRequest aus. Absicht Tagestour, Start Titisee, Rundweg, zehn Kilometer, und acht Nullen, "
        "nach denen niemand gefragt hat. Dann übernimmt der Code. Resolve behält nur Zahlen, die in der Nachricht "
        "stehen, und verwirft die acht Nullen, macht aus der Zehn ein Band von acht Komma fünf bis elf Komma fünf, "
        "findet Titisee im Orts-Vokabular und ergänzt den Standard-Umkreis. Der Knoten schickt das Ereignis "
        "understood und schreibt current, request und die Route search.",
        "g10": "Search ist ein reiner Code-Knoten. Er liest current, prüft es als HikeRequest und ruft search day "
        "hikes direkt auf, als Python-Funktion: PostGIS findet die Kandidaten, und constraints punkt select prüft "
        "jede Bedingung. Hier gibt es kein Modell, und keinen Tool-Aufruf, den ein Modell gewählt hätte. Der "
        "Knoten schickt das Ereignis results mit drei Tourenkarten und schreibt zurück: einen Tool-Aufruf, die "
        "drei letzten Touren mit ihren IDs, die Kandidaten fürs Log, die Belege, also jede Zahl, die die Antwort "
        "verwenden darf, und data, den kurzen Textblock für das Modell.",
        "g11": "Answer liest data und macht den zweiten Modellaufruf, bei Temperatur null Komma drei. Das Modell "
        "formuliert nur den Datenblock, und der Knoten schreibt draft. Ground ist wieder Code: Er vergleicht jede "
        "Zahl im Entwurf mit den Belegen. Hier sind alle belegt, unsupported ist also null. Er setzt die eigenen "
        "Sätze des Codes um den Text, schreibt final text, und erst jetzt geht der Text als Token-Ereignisse an den "
        "Browser, in Wortstücken, danach die Quellen. Log "
        "schreibt eine JSON-Zeile, schickt done mit Tokens und Kosten, und gibt ein leeres Update zurück.",
        "g12": "Jetzt eine Folgefrage im selben Thread: Under 300 m ascent, please. Der Checkpointer hält schon die vorige Anfrage, die letzten Touren und den Verlauf. Understand gibt dem Modell die vorige Anfrage mit, und es antwortet mit der Absicht change "
        "und einem Anstieg von höchstens dreihundert. Der Code führt das mit der gespeicherten Anfrage zusammen: "
        "gleicher Start, gleiches Längenband, dazu die neue Grenze für den Anstieg. Search läuft erneut. Jetzt "
        "passen zwei Touren, und der Jägersteig erscheint als knapp daneben: elf Komma sechs Kilometer statt "
        "höchstens elf Komma fünf. Wieder kein ReAct: zwei Modellaufrufe, ein Tool-Aufruf durch den Graphen.",
        "g13": "Beispiel zwei setzt dasselbe Gespräch fort: How long does the first tour take, and where can I stay "
        "near it? Also: Wie lange dauert die erste Tour, und wo kann ich in der Nähe übernachten? In understand nennt das Modell die Absicht knowledge und kopiert sieben Zahlen aus der vorigen "
        "Anfrage, die der Code verwirft. Der Code schreibt die Route react. Der Weg ist jetzt guard, understand, "
        "react, answer, ground und log. Und diesmal entscheidet in react das Modell, welche Tools es aufruft.",
        "g14": "In react baut der Code eine Liste aus LangChain-Nachrichten. Eins: der Systemprompt mit den Regeln. "
        "Nutze die Tools, und jede Zahl muss aus einem Tool-Ergebnis kommen. Zwei: die zuletzt vorgeschlagenen "
        "Touren mit ihren IDs, aus dem gespeicherten Zustand. Drei: die Frage. Dann handelt zuerst der Code. Vier "
        "und fünf sind seine eigene Wissenssuche, geschrieben wie ein Tool-Aufruf mit der ID vorab, und ihr "
        "Ergebnis. Runde eins: Das Modell überlegt, dass die erste "
        "Tour der Menzenschwander Geißenpfad ist, und handelt mit zwei Tool-Aufrufen auf einmal: get trail details "
        "und find accommodation, beide mit dessen Tour-ID. Der Code beobachtet: Er führt beide Tools aus und hängt "
        "zwei Tool-Messages mit den passenden IDs an. Runde zwei: Das Modell hat, was es braucht, und antwortet "
        "nur mit Text. Keine Tool-Calls heißt: Stopp, das ist der Entwurf.",
        "g15": "So sieht die Schleife im Code aus. g w punkt tool round schickt die Nachrichtenliste, mit den "
        "gebundenen Tool-Beschreibungen. Hat die Antwort keine Tool-Calls, ist ihr Text der Entwurf, und die "
        "Schleife endet. Sonst führt run tool jeden Aufruf aus, und das Ergebnis geht als ToolMessage mit der ID "
        "des Aufrufs zurück. Der Code zählt die Aufrufe: drei in diesem Durchlauf, bei einem Limit von acht, die "
        "Vorab-Suche des Codes mitgezählt. Ein fehlerhaftes Tool geht als Text zurück ans Modell, und ohne ein "
        "Ergebnis mit Quelle antwortet der Code stattdessen mit einem festen Satz.",
        "g16": "React schreibt tool calls drei, die Quellen, die Belege aus allen Tool-Ergebnissen, und den Entwurf. "
        "Answer sieht, dass es schon einen Entwurf gibt, und gibt ein leeres Update zurück: kein zusätzlicher "
        "Modellaufruf fürs Formulieren. Jetzt macht ground seine Arbeit. Das Modell hat hiking time nicht "
        "aufgerufen. Stattdessen schrieb es: etwa zwei Stunden und dreißig Minuten. Diese Dauer steht in keinem "
        "Tool-Ergebnis. Also ersetzt ground sie durch Fragezeichen und fügt einen Hinweis an. Die Länge, neun Komma "
        "sieben acht Kilometer, und die Gästehäuser mit ihren Entfernungen sind belegt, also bleiben sie stehen. "
        "Insgesamt drei Modellaufrufe, für weniger als ein Zehntel Cent.",
        "g17": "Ein zweiter Wissens-Durchlauf, in einem neuen Thread: How is the Westweg waymarked? Also: Wie ist der "
        "Westweg markiert? Es gibt keine letzten Touren, also fehlt die Touren-Nachricht. Die eigene Suche des "
        "Codes findet Textstellen zum Westweg aus Wikivoyage und Wikipedia. In Runde eins antwortet das Modell "
        "direkt, ohne ein Tool aufzurufen. Eine ReAct-Schleife kann also nach einer einzigen Runde enden, wenn das "
        "Modell entscheidet, dass das Beobachtete reicht. Und eine ehrliche Grenze: Grounding prüft Zahlen und "
        "Namen, nicht jede Aussage. Die Textstellen beschreiben die Markierung nicht, deshalb bleibt die Antwort "
        "vage.",
        "g18": "Zusammengefasst. Das Modell handelt an drei Stellen: in understand, wo es ein Formular ausfüllt, in "
        "den react-Runden, wo es Tools und Argumente wählt, und in answer, wo es einen Datenblock formuliert. Alles "
        "andere entscheidet der Code: die Route, die Suche und ihre Bedingungen, die Mehrtagesplanung, die erste "
        "Wissenssuche, das Limit von acht Aufrufen, und die Prüfung jeder Zahl. Das System ist also agentisch, wo "
        "die Frage offen ist, und ein fester Workflow, wo die Ergebnisse prüfbar sein müssen.",
        "g19": "Und so erklärt man es in einer Minute. HikeSense ist eine LangGraph-Zustandsmaschine mit zwölf "
        "Knoten. Ein strukturierter Modellaufruf versteht die Nachricht; der Code prüft sie und wählt die Route. "
        "Bei Tourensuchen ruft der Graph die Suche selbst auf, und das Modell formuliert nur das Ergebnis. Bei "
        "offenen Wissensfragen darf das Modell in einer ReAct-Schleife vier Tools aufrufen, höchstens acht Mal. "
        "Jede Zahl in der Antwort wird gegen die Tool-Ergebnisse geprüft, bevor sie erscheint, und ein "
        "Checkpointer pro Thread macht Folgefragen möglich. Der Code entscheidet, das Modell formuliert. Danke "
        "fürs Zuschauen.",
    },
}

# --- code panels (read from the repository at recording time) ----------------------------------------------------

G = "backend/src/hikesense/agent/graph.py"
CODE = {
    "g05L": [Snippet(G, start="class State(TypedDict, total=False):", end="candidates: list[dict]",
                     mark=["route: str", "current:", "evidence:", "draft:", "final_text:", "persists per thread"])],
    "g05R": [Snippet(G, "build_graph.guard", mark=["return {"])],
    "g06": [Snippet(G, start="    g = StateGraph(State)", end="return g.compile(checkpointer=deps.checkpointer)",
                    mark=["StateGraph(State)", "add_conditional_edges", 'lambda s: s["route"]', "compile("])],
    "g07L": [Snippet(G, "_emit", mark=["get_stream_writer"]),
             Snippet(G, start='    graph_thread = f"{user_hash', end='            "thread_id": graph_thread,',
                     mark=["graph_thread =", '"thread_id": graph_thread']),
             Snippet(G, start="        config = _run_config(", end="stream = deps.graph.stream(",
                     mark=["graph.stream("])],
    "g15": [Snippet(G, start='        pre = {"name": "search_knowledge"', end='        return out | {"data": data}',
                    mark=["gw.tool_round(", "if not ai.tool_calls", "tool_call_id=call", "max_tool_calls"])],
    "g16c": [Snippet(G, "build_graph.answer", mark=['if state.get("draft")'])],
}  # fmt: skip

# --- real data from graph_runs.json --------------------------------------------------------------------------------

TITISEE, FOLLOW, TOURQ, WESTWEG = RUNS["runs"]
NODE_ORDER = ["guard", "understand", "search", "react", "answer", "ground", "log"]

# what each node reads from the state (from the code of build_graph; not recorded by the run)
READS = {
    "guard": "message · history",
    "understand": "message · request · pending · plan",
    "search": "current · lang",
    "react": "current · message · last_tours",
    "answer": "draft · data · system",
    "ground": "draft · fixed · reason · evidence · sources · …",
    "log": "state + config (usage, trace)",
}
TOOL_NODE = {"search_day_hikes": "search"}  # every other tool of these runs was called inside react


def step(run: dict, node: str) -> dict:
    return next(s for s in run["steps"] if s["node"] == node)


def update(run: dict, node: str) -> dict:
    return step(run, node)["update"]


def calls_of(run: dict, node: str) -> tuple[int, list[str]]:
    """(model calls, tool names) of one node in the recorded trace."""
    model = sum(1 for c in run["llm_calls"] if c["step"] == node)
    tools = [t["name"] for t in run["tool_calls"] if TOOL_NODE.get(t["name"], "react") == node]
    return model, tools


def events_of(run: dict, node: str) -> str:
    n = Counter(e["type"] for e in step(run, node)["events"])
    return " · ".join(f"{k} ×{v}" if v > 1 else k for k, v in n.items()) or "–"


L = {
    "en": {"node": "node", "reads": "reads", "does": "model / tool", "writes": "writes into the state",
           "event": "event → browser", "model": "model", "code": "code only", "empty": "{} (nothing)",
           "skipped": "skipped: draft exists", "short": "shortened", "vorab": "code, vorab", "real": "real run 2026-11-03"},
    "de": {"node": "Knoten", "reads": "liest", "does": "Modell / Tool", "writes": "schreibt in den Zustand",
           "event": "Ereignis → Browser", "model": "Modell", "code": "nur Code", "empty": "{} (nichts)",
           "skipped": "übersprungen: Entwurf da", "short": "gekürzt", "vorab": "Code, vorab", "real": "echter Lauf 2026-11-03"},
}  # fmt: skip


def step_table(run: dict, lang: str) -> str:
    t = L[lang]
    rows = []
    for s in run["steps"]:
        node = s["node"]
        model, tools = calls_of(run, node)
        does = []
        if model:
            does.append(f'<span class="tag m">{t["model"]} ×{model}</span>' if model > 1 else f'<span class="tag m">{t["model"]}</span>')
        if node == "react" and tools and tools[0] == "search_knowledge":  # the code's own first search
            does.append(f'<span class="tag c">search_knowledge · {t["vorab"]}</span>')
            tools = tools[1:]
        for name, k in Counter(tools).items():
            does.append(f'<span class="tag t">{escape(name)}{" ×" + str(k) if k > 1 else ""}</span>')
        if not does:
            does.append(f'<span class="tag c">{t["code"]}</span>')
        keys = list(s["update"])
        if node == "answer" and not keys:
            writes = f'<span class="muted">{t["skipped"]}</span>'
        else:
            writes = " ".join(f'<span class="key">{escape(k)}</span>' for k in keys) or f'<span class="muted">{t["empty"]}</span>'
        rows.append(
            f'<tr class="b" data-node="{node}"><td class="nd">{node}</td><td class="rd">{escape(READS[node])}</td>'
            f"<td>{''.join(does)}</td><td>{writes}</td><td class=\"evc\">{escape(events_of(run, node))}</td></tr>"
        )
    head = f'<tr><th>{t["node"]}</th><th>{t["reads"]}</th><th>{t["does"]}</th><th>{t["writes"]}</th><th>{t["event"]}</th></tr>'
    return f'<table class="steps">{head}{"".join(rows)}</table>'


def path(run: dict, cur: list[str]) -> str:
    """The node strip: the run's path, current node(s) highlighted."""
    nodes = [s["node"] for s in run["steps"]]
    out, seen = [], False
    for i, n in enumerate(nodes):
        cls = "cur" if n in cur else ("done" if not seen else "")
        if n in cur:
            seen = True
        model, tools = calls_of(run, n)
        dot = '<i class="m"></i>' if model else ('<i class="t"></i>' if tools else '<i class="c"></i>')
        out.append(f'<span class="pn {cls}">{dot}{n}</span>')
        if i < len(nodes) - 1:
            out.append('<span class="pa">→</span>')
    return "".join(out)


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _cons(c: dict) -> dict:
    return {k: v for k, v in c.items() if v is not None}


def _body(m: dict, width: int = 150) -> str:
    """One message of the ReAct list as a highlighted one-liner."""
    if m.get("tool_calls"):
        calls = " · ".join(
            f'<span class="v">{escape(c["name"])}</span>({escape(_short(json.dumps(c["args"], ensure_ascii=False), 60))})'
            f' <span class="k">id</span>=<span class="s">"{escape(_short(c["id"], 12))}"</span>'
            for c in m["tool_calls"]
        )
        return f"tool_calls: {calls}"
    return escape(_short(str(m["content"]).replace("\n", " "), width))


ROLE = {
    "en": {"rules": "code · rules", "tours": "code · last_tours", "q": "the question", "pre": "written by the code",
           "tool": "code runs the tool", "act": "model · Act", "final": "model · no tool_calls → draft",
           "round": "round", "setup": "prepared by the code", "stop": "answer · stop", "obs": "Observe"},
    "de": {"rules": "Code · Regeln", "tours": "Code · last_tours", "q": "die Frage", "pre": "vom Code geschrieben",
           "tool": "Code führt das Tool aus", "act": "Modell · Act", "final": "Modell · keine tool_calls → Entwurf",
           "round": "Runde", "setup": "vom Code vorbereitet", "stop": "Antwort · Stopp", "obs": "Observe"},
}  # fmt: skip


def react_seq(run: dict, lang: str, fracs: list[float]) -> str:
    """The message list of the last ReAct round plus the final reply, numbered, with who wrote each message."""
    r = ROLE[lang]
    rounds = run["react_rounds"]
    msgs = rounds[-1]["sent"] + [rounds[-1]["reply"]]
    rows, f = [], iter(fracs)
    # message number where the model's reply of each round appears → a round label above it
    starts = {
        len(rd["sent"]) + 1: f'{r["round"]} {k + 1} · Reason → ' + ("Act → Observe" if rd["reply"].get("tool_calls") else r["stop"])
        for k, rd in enumerate(rounds)
    }
    for i, m in enumerate(msgs, 1):
        if i == 1:
            rows.append(f'<div class="rmark b" style="--f:{fracs[0]}">{escape(r["setup"])}</div>')
        elif i in starts:
            rows.append(f'<div class="rmark b" style="--f:{fracs[min(i - 1, len(fracs) - 1)]}">{escape(starts[i])}</div>')
        typ = m["type"]
        if typ == "SystemMessage":
            cls, sub = "code", r["tours"] if "trail_id" in str(m["content"]) else r["rules"]
        elif typ == "HumanMessage":
            cls, sub = "code", r["q"]
        elif typ == "AIMessage" and m.get("tool_calls") and m["tool_calls"][0]["id"] == "vorab":
            cls, sub = "code", r["pre"]
        elif typ == "AIMessage" and m.get("tool_calls"):
            cls, sub = "model", r["act"]
        elif typ == "AIMessage":
            cls, sub = "model final", r["final"]
        else:
            cls, sub = "tool", f'{r["obs"]} · tool_call_id="{_short(m["tool_call_id"], 12)}"'
        rows.append(
            f'<div class="msg {cls} b" style="--f:{next(f, 0.9)}"><div class="n">{i}</div>'
            f'<div class="role">{typ}<small>{escape(sub)}</small></div><div class="body">{_body(m)}</div></div>'
        )
    return '<div class="seq">' + "".join(rows) + "</div>"


def panels(lang: str) -> dict[str, list[str]]:
    s = L[lang]["short"]
    u_und = update(TITISEE, "understand")
    cur = u_und["current"]
    llm0 = TITISEE["llm_calls"][0]["output"]
    keys0 = ["intent", "activity", "start_text", "roundtrip", "length_km_min", "length_km_max", "length_km_approx",
             "ascent_m_min", "ascent_m_max", "ascent_m_approx", "duration_h_min", "duration_h_max",
             "duration_h_approx", "radius_km_max", "pace_min_per_km"]
    und_view = {
        "route": u_und["route"], "intent": u_und["intent"], "discarded_numbers": u_und["discarded_numbers"],
        "current": {"start": {k: cur["start"][k] for k in ("kind", "label", "lat", "lon")},
                    "constraints": [_cons(c) for c in cur["constraints"]], E: E},
        "request": "= current", "pending": None, E: E,
    }
    u_s = update(TITISEE, "search")
    search_view = {
        "tool_calls": u_s["tool_calls"], "reason": u_s["reason"], "near_sentence": u_s["near_sentence"],
        "last_tours": u_s["last_tours"],
        "evidence": {"numbers": u_s["evidence"]["numbers"][:6] + [E], "names": u_s["evidence"]["names"][:1] + [E]},
        "candidates": [{k: u_s["candidates"][0][k] for k in ("name", "status", "length_km", "ascent_m")}, E],
        "sources": [{"id": x["id"], "license": x["license"]} for x in u_s["sources"]],
    }
    data_text = "\n".join(u_s["data"].splitlines()[:3]) + "\n…"
    ground = update(TITISEE, "ground")
    done = next(e for e in step(TITISEE, "log")["events"] if e["type"] == "done")
    tokens = [e for e in step(TITISEE, "ground")["events"] if e["type"] == "token"]
    ground_view = {k: ground[k] for k in ("unsupported", "unsupported_names", "unsat_claims_removed")} | {
        "final_text": _short(ground["final_text"].replace("\n", " "), 34)}
    events_view = {"token": [tokens[0]["text"], tokens[1]["text"], tokens[2]["text"], E], "count": len(tokens),
                   "then": "sources"}
    done_view = {"type": "done", "usage": {k: round(done["usage"][k], 6) for k in ("calls", "input_tokens",
                                                                                "output_tokens", "cost_usd")},
                 "unsupported": done["unsupported"]}
    # follow-up
    before = FOLLOW["state_before"]
    ck_view = {"request": {"start": {"label": before["request"]["start"]["label"], E: E},
                           "constraints": [_cons(c) for c in before["request"]["constraints"]], E: E},
               "last_tours": before["last_tours"], "history": before["history"], "pending": None, "plan": None}
    llm1 = FOLLOW["llm_calls"][0]["output"]
    f_model = {k: llm1[k] for k in ("intent", "start_text", "length_km_min", "length_km_max", "ascent_m_min",
                                    "ascent_m_max", "radius_km_max")} | {E: E}
    fu = update(FOLLOW, "understand")
    fs = update(FOLLOW, "search")
    res_ev = next(e for e in step(FOLLOW, "search")["events"] if e["type"] == "results")
    f_code = {"discarded_numbers": fu["discarded_numbers"], "route": fu["route"],
              "current.constraints": [_cons(c) for c in fu["current"]["constraints"]],
              "results.cards": [{"name": c["name"].replace("Genießerpfad - ", ""), "length_km": c["length_km"],
                                 "ascent_m": c["ascent_m"], "near_miss": c.get("near_miss")} for c in res_ev["cards"]],
              "near_sentence": fs["near_sentence"]}
    # example 2
    llm2 = TOURQ["llm_calls"][0]["output"]
    tu = update(TOURQ, "understand")
    t_model = {k: llm2[k] for k in ("intent", "start_text", "length_km_min", "length_km_max", "ascent_m_max",
                                    "radius_km_max")} | {"question": _short(llm2["question"], 26), E: E}
    t_code = {"discarded_numbers": tu["discarded_numbers"], "route": tu["route"],
              "current": {"intent": tu["current"]["intent"], "start": tu["current"]["start"],
                          "constraints": tu["current"]["constraints"], "question": _short(tu["current"]["question"], 40), E: E}}
    rx = update(TOURQ, "react")
    react_view = {"tool_calls": rx["tool_calls"],
                  "sources": [x["id"] for x in rx["sources"]],
                  "evidence": {"numbers": [n for n in rx["evidence"]["numbers"] if len(n) < 12][:4] + [E],
                               "names": [n for n in rx["evidence"]["names"] if "Gästehaus" in n or "Geißenpfad" in n][:2] + [E]},
                  "draft": _short(rx["draft"].replace("\n", " "), 70)}
    w_seq_note = WESTWEG["react_rounds"][0]["reply"]["content"]
    return {
        "g09L": [jpanel(f"llm_calls[0] · understand · output · {s}", {k: llm0[k] for k in keys0} | {E: E},
                        width=40, mark=['": 0.0'])],
        "g09R": [jpanel(f"update ← understand · {s}", und_view, width=76, pack=True,
                        mark=['"route"', '"discarded_numbers"', "8.5"])],
        "g10R": [jpanel(f"update ← search · {s}", search_view, width=84, pack=True,
                        mark=['"tool_calls"', '"last_tours"', '"trail_id"'])],
        "g10d": [tpanel("data → answer", data_text)],
        "g11a": [tpanel(f"update ← answer · draft · {s}", _short(update(TITISEE, "answer")["draft"], 330))],
        "g11g": [jpanel(f"update ← ground · {s}", ground_view, width=50, mark=['"unsupported"']),
                 jpanel(f"custom events ← ground · {s}", events_view, width=50)],
        "g11l": [jpanel("update ← log", {}, width=30), jpanel(f"event done · {s}", done_view, width=50, mark=["cost_usd"])],
        "g12L": [jpanel(f"checkpoint · thread video-demo:titisee · {s}", ck_view, width=80, pack=True,
                        mark=['"request"', '"last_tours"', '"history"'])],
        "g12M": [jpanel(f"llm_calls[0] · understand · output · {s}", f_model, width=40, pack=True,
                        mark=['"change"', '300.0'])],
        "g12R": [jpanel(f"update ← understand, search · {s}", f_code, width=96, pack=True,
                        mark=['"ascent_m"', "Near miss", '"near_miss": true'])],
        "g13L": [jpanel(f"llm_calls[0] · output · {s}", t_model, width=44, mark=['"knowledge"'])],
        "g13R": [jpanel(f"update ← understand · {s}", t_code, width=60, pack=True, mark=['"route"', "discarded"])],
        "g16L": [jpanel(f"update ← react · {s}", react_view, width=100, pack=True,
                        mark=['"tool_calls"', '"draft"'])],
        "g17n": [tpanel(f"AIMessage · round 1 · content · {s}", _short(w_seq_note, 420))],
    }


def html_blocks(lang: str) -> dict[str, str]:
    """Raw HTML for slots that are not code panels (tables, node strips, message lists)."""
    ex1 = ["guard", "understand", "search", "answer", "ground", "log"]
    return {
        "g08t": step_table(TITISEE, lang),
        "g08p": path(TITISEE, []),
        "g09p": path(TITISEE, ["guard", "understand"]),
        "g10p": path(TITISEE, ["search"]),
        "g11p": path(TITISEE, ["answer", "ground", "log"]),
        "g12p": path(FOLLOW, ["understand", "search"]),
        "g13t": step_table(TOURQ, lang),
        "g13p": path(TOURQ, ["understand"]),
        "g14p": path(TOURQ, ["react"]),
        "g14s": react_seq(TOURQ, lang, [0.03, 0.08, 0.13, 0.2, 0.26, 0.45, 0.62, 0.66, 0.84]),
        "g16p": path(TOURQ, ["react", "answer", "ground"]),
        "g17p": path(WESTWEG, ["react"]),
        "g17s": react_seq(WESTWEG, lang, [0.05, 0.12, 0.2, 0.26, 0.36]),
        "ex1": " → ".join(ex1),
    }


def facts() -> dict:
    """Numbers shown on slides, from the runs (cost, calls)."""
    def f(run):
        return {"cost": run["usage"]["cost_usd"], "calls": run["usage"]["calls"], "tools": len(run["tool_calls"]),
                "in": run["usage"]["input_tokens"], "out": run["usage"]["output_tokens"]}
    return {"titisee": f(TITISEE), "follow": f(FOLLOW), "tourq": f(TOURQ), "westweg": f(WESTWEG),
            "total": RUNS["total_cost_usd"], "final2": update(TOURQ, "ground")["final_text"],
            "draft2": update(TOURQ, "react")["draft"]}


async def main(lang: str, out: Path) -> None:
    work = out / f"work-graph-{lang}"
    segments = [Segment(k, v) for k, v in TEXT[lang].items()]
    voice, rate = VOICES[lang]
    await synthesize(segments, work / "voice", voice, rate)
    for s in segments:
        print(f"{s.key}: {s.duration:5.1f}s")
    print(f"voice total {sum(s.duration for s in segments):.0f}s")
    slides = (HERE / "graph_slides.html").resolve()
    code = render_slides(CODE) | panels(lang)
    pad = 0.7
    async with async_playwright() as p:
        browser = await p.chromium.launch()  # slides: 1920 × 1080 CSS pixels, no scale flag
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        await page.goto(slides.as_uri())
        await page.wait_for_load_state("networkidle")
        await page.evaluate(
            "([lang, code, html, facts]) => { setLang(lang); fillHtml(html); fillFacts(facts); fillCode(code); }",
            [lang, code, html_blocks(lang), facts()],
        )
        await page.wait_for_timeout(1500)
        rec = Screencast(page, work / "frames")
        await page.evaluate("go('none')")
        await rec.start()
        for s in segments:
            await page.evaluate(f"go('{s.key}', {s.duration + pad:.2f})")
            await narrate(rec, s, pad=pad)
        await rec.stop(tail=1.5)
        await browser.close()
    target = out / f"hikesense-graph-{lang}.mp4"
    render(rec, segments, target)
    print("wrote", target, f"{rec.shift(rec.end):.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["en", "de"], default="en")
    ap.add_argument("--out", type=Path, default=HERE / "out")
    ap.add_argument("--preview", action="store_true", help="write out/graph-preview-<lang>.html, no recording")
    args = ap.parse_args()
    if args.preview:
        page = (HERE / "graph_slides.html").read_text(encoding="utf-8")
        data = json.dumps([args.lang, render_slides(CODE) | panels(args.lang), html_blocks(args.lang), facts()])
        boot = f"<script>(([l,c,h,f])=>{{setLang(l);fillHtml(h);fillFacts(f);fillCode(c);go(location.hash.slice(1)||'g01',30)}})({data})</script>"
        target = args.out / f"graph-preview-{args.lang}.html"
        target.write_text(page.replace("</body>", boot + "</body>"), encoding="utf-8")
        print("wrote", target)
    else:
        asyncio.run(main(args.lang, args.out.resolve()))
