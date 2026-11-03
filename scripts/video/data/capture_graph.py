"""Capture real turns through the compiled LangGraph graph for the graph video (graph_demo.py).

Runs the same graph as the API (default_deps_factory: real database, knowledge index, OpenRouter model) and
records, per turn: every state update a node returned (stream_mode "updates"), every UI event it emitted
(stream_mode "custom"), the model calls and tool calls of the trace, the exact message list of every ReAct round
(with tool_call ids), and the state the checkpointer keeps for the thread afterwards. No user id or e-mail is
used: the thread key is "video-demo:<thread>". The chat log goes to a scratch file (CHAT_LOG_PATH).

Usage (from backend/, costs about $0.001 per turn with openai/gpt-4o-mini):
    CHAT_LOG_PATH=/tmp/graph-demo-chat.jsonl uv run python ../scripts/video/data/capture_graph.py
writes scripts/video/data/graph_runs.json
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

if "CHAT_LOG_PATH" not in os.environ:
    sys.exit("set CHAT_LOG_PATH to a scratch file, not the checkout's data/logs/chat.jsonl")

from hikesense.agent.graph import _turn
from hikesense.api.chat import default_deps_factory
from hikesense.config import Settings
from hikesense.llm import gateway as gwmod
from hikesense.llm.usage import metered
from hikesense.trace import to_jsonable, traced

OUT = Path(__file__).with_name("graph_runs.json")

# (thread, message, lang): example 1 (day hike + follow-up), example 2 (knowledge questions)
TURNS = [
    ("titisee", "A round walk near Titisee, about 10 km", "en"),
    ("titisee", "Under 300 m ascent, please", "en"),
    ("titisee", "How long does the first tour take, and where can I stay near it?", "en"),
    ("westweg", "How is the Westweg waymarked?", "en"),
]

ROUNDS: list[dict] = []  # filled by the wrapped tool_round
_orig_tool_round = gwmod.OpenRouterGateway.tool_round


def _msg(m) -> dict:
    d = {"type": type(m).__name__, "content": m.content}
    if getattr(m, "tool_calls", None):
        d["tool_calls"] = [
            {"name": c["name"], "args": c["args"], "id": c["id"]} for c in m.tool_calls
        ]
    if getattr(m, "tool_call_id", None):
        d["tool_call_id"] = m.tool_call_id
    return d


def _recording_tool_round(self, messages, tools):
    reply = _orig_tool_round(self, messages, tools)
    ROUNDS.append(
        {
            "sent": [_msg(m) for m in messages],
            "reply": _msg(reply),
            "tools_sent": [t["function"]["name"] for t in tools],
        }
    )
    return reply


gwmod.OpenRouterGateway.tool_round = _recording_tool_round


def main() -> None:
    settings = Settings()
    print("chat log:", settings.chat_log_path, "model:", settings.hikesense_model)
    deps = default_deps_factory(settings)()
    graph = deps.graph
    runs = []
    total = 0.0
    for thread, message, lang in TURNS:
        ROUNDS.clear()
        with metered(max_cost_usd=settings.max_cost_usd) as usage, traced() as tr:
            config = {
                "configurable": {
                    "thread_id": f"video-demo:{thread}",
                    "usage": usage,
                    "request_id": uuid.uuid4().hex,
                    "user_hash": None,
                    "user_id": None,
                    "lang": lang,
                    "trace": tr,
                }
            }
            before = to_jsonable(graph.get_state(config).values)
            steps = []
            for mode, chunk in graph.stream(
                _turn(message, lang), config, stream_mode=["updates", "custom"]
            ):
                if mode == "updates":
                    for node, update in chunk.items():
                        steps.append(
                            {"node": node, "update": to_jsonable(update or {}), "events": []}
                        )
                else:  # custom events are emitted while the node runs, before its update arrives
                    ev = to_jsonable(chunk)
                    if steps and steps[-1].get("open"):
                        steps[-1]["events"].append(ev)
                    else:
                        steps.append({"node": None, "events": [ev], "open": True})
            # attach events to the node that emitted them (they arrive before that node's update)
            merged, pending = [], []
            for s in steps:
                if s["node"] is None:
                    pending += s["events"]
                else:
                    s["events"] = pending + s["events"]
                    pending = []
                    merged.append(s)
            after = to_jsonable(graph.get_state(config).values)
        total += usage.cost_usd
        runs.append(
            {
                "thread": thread,
                "message": message,
                "lang": lang,
                "state_before": {
                    k: before.get(k)
                    for k in ("request", "pending", "last_tours", "plan", "history")
                },
                "steps": merged,
                "state_after": after,
                "llm_calls": to_jsonable(tr.llm_calls),
                "tool_calls": to_jsonable(tr.tool_calls),
                "react_rounds": to_jsonable(ROUNDS),
                "usage": to_jsonable(usage),
            }
        )
        print(
            f"{message!r}: route={after.get('route')} cost=${usage.cost_usd:.5f} "
            f"nodes={[s['node'] for s in merged]} rounds={len(ROUNDS)}"
        )
    OUT.write_text(
        json.dumps(
            {"model": settings.hikesense_model, "total_cost_usd": total, "runs": runs},
            ensure_ascii=False,
            indent=1,
        )
    )
    print(f"total ${total:.5f} → {OUT}")


if __name__ == "__main__":
    main()
