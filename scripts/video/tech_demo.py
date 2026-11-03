"""Video 2: how HikeSense works inside (British English voice-over over animated slides).

Uses the screenshots that user_demo.py saves to out/shots/, so run that first. With a running app (--base) it takes
fresh screenshots of the admin backend /admin (no agent turn, no cost); without one it keeps the user video's.
Usage:
    python scripts/video/tech_demo.py [--base http://localhost:3104] [--api http://localhost:8004] [--out …]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import urllib.request
from pathlib import Path

from code_snippets import Snippet, render_slides
from playwright.async_api import async_playwright
from recorder import BROWSER_ARGS, SCALE, VIEW_H, VIEW_W, H, Screencast, Segment, W, narrate, render, synthesize

# Counts for the slides, from README.md ("Daten und Lizenzen", queried 2026-10-31, Black Forest only). Update them
# from the README after the import of the new regions, together with the narration of t04/t05/t06.
COUNTS = {
    "lines": "4", "stages": "46", "day_hikes": "122", "lodgings": "1,814", "photos": "849",
    "scanned": "1,712", "auto_rejected": "1,335", "manual_rejected": "255",
}  # fmt: skip

SEGMENTS = [
    Segment(
        "t01",
        "HikeSense, under the hood. This video shows how the planner works inside: the data and its "
        "licences, the quality rules for day hikes, the LangGraph agent, the grounding check, near misses, the "
        "weather day finder, the admin backend, the bilingual design, and the evaluation.",
    ),
    Segment(
        "t03",
        "The web app is built with Next.js and installs as a progressive web app. It uses Supabase for sign-in, "
        "saved plans and photos, and a Python API built with FastAPI for the chat. The API checks the Supabase "
        "token and a rate limit, then runs a LangGraph graph. Routes and places live in Postgres with PostGIS. "
        "The language model, by default gpt-4o-mini, is called through OpenRouter.",
    ),
    Segment(
        "t04",
        "Every imported row points to a source with its licence. Trails, places and accommodation come from "
        "OpenStreetMap, imported once, so the app never queries OpenStreetMap at runtime. Elevation profiles are "
        "computed from the Copernicus terrain model, photos come from Wikimedia Commons with author and licence, "
        "and the weather from Open-Meteo, live, for up to fourteen days. For the Black Forest that is four "
        "long-distance lines with forty-six stages, a hundred and twenty-two day hikes, eighteen hundred and "
        "fourteen places to stay and eight hundred and forty-nine photos.",
    ),
    Segment(
        "t05",
        "There are now three regions: the Black Forest, Lake Constance with its Swiss and Austrian shore, and the "
        "Palatinate Forest, German side only. Four long-distance trails with stages join the Westweg, Mittelweg "
        "and Ostweg: the Pfälzer Weinsteig, the Pfälzer Waldpfad, the Jubiläumsweg Bodenseekreis and the SeeGang. "
        "The import for the new regions is still running, so the counts here are for the Black Forest.",
    ),
    Segment(
        "t06",
        "Day hikes follow strict rules: quality before quantity. A scan writes every OpenStreetMap hiking relation "
        "into a curation file. A relation is rejected automatically if it has no name, is a stage of a "
        "long-distance trail, has gaps, is shorter than five or longer than thirty kilometres, or belongs to a "
        "long-distance network. A manual decision always wins. Of seventeen hundred and twelve relations in the "
        "Black Forest, a hundred and twenty-two remain.",
    ),
    Segment(
        "c06",
        "In code, the automatic decision is one small function. The rules run in this order, and the first one "
        "that fails is the reason written to the curation file.",
    ),
    Segment(
        "t07",
        "The agent is a LangGraph graph. Guard answers known prompt-injection patterns with a fixed reply, "
        "without calling the model. Understand makes one structured model call, and code resolves the result. "
        "If a place is ambiguous, clarify asks back. Otherwise one worker runs: search for day hikes, multiday "
        "for plans, react for knowledge questions, or groups and events. Then answer lets the model word the "
        "reply, ground checks it, and log writes one line per request.",
    ),
    Segment(
        "c07",
        "The wiring is short: conditional edges after guard and understand, and fixed edges from every worker "
        "through answer and ground to log. The checkpointer keeps each conversation, so follow-ups work.",
    ),
    Segment(
        "t08",
        "The rule behind it: the code decides, the model words it. The model turns a message into a structured "
        "request and writes the answer text. Everything in between is code: it keeps a number only if the user "
        "wrote it, resolves places, searches and checks the tours, picks near misses, plans the days with walking "
        "times to DIN 33466, and writes the honest sentences itself, such as: no tour meets all your wishes.",
    ),
    Segment(
        "c08",
        "Here is that check. For every bound from the model, the code asks: did the user write this number? If "
        "not, the value is dropped and counted. A single value, like about ten kilometres, becomes a band of "
        "plus or minus fifteen percent.",
    ),
    Segment(
        "t09",
        "Each candidate is checked against every hard condition: length, ascent, round walk, distance and "
        "duration, with a tick, a cross, or a question mark if the data cannot tell. At most five full matches "
        "are shown. If only one or two match, near misses fill the list up to three: tours that break exactly "
        "one condition by at most a quarter, never the round walk. If nothing matches, the code shows fallbacks "
        "that break exactly one condition, and says why.",
    ),
    Segment(
        "c09",
        "This is select. Matches are sorted by preference score, distance and id, so the result is "
        "reproducible. Then come the near misses, or, without a match, the best fallback per condition, with "
        "the reason. The rejected candidates are kept for the admin backend.",
    ),
    Segment(
        "t10",
        "The grounding check runs on every answer. It finds each number with a unit, like eleven point six "
        "kilometres or two hours, and looks for it in this round's tool results and the code's own sentences. A "
        "number it cannot find becomes a question mark, with a note. Tour names that the results do not mention "
        "get a note too. It reads both languages: decimal commas and German number words, and decimal points, "
        "thousands commas and English number words.",
    ),
    Segment(
        "c10",
        "In the code: every unsupported number is collected and its span replaced by a question mark. Then the "
        "two notes are added, and the counts go to the log and the backend.",
    ),
    Segment(
        "t11",
        "The weather day finder starts from a wish in the message: fine, dry, or snow. The model only spots the "
        "wish. The code reads the Open-Meteo forecast for today and the next fourteen days. Fine means clear to "
        "overcast, at most half a millimetre of precipitation and at most thirty percent probability. Dry allows "
        "one millimetre and forty percent. Snow needs one centimetre of snowfall or a snow weather code. For a "
        "multi-day tour, it looks for start days on which every day fits. If none does, it says so.",
    ),
    Segment(
        "c11",
        "The decision is tri-state: a known failure decides, but a missing value gives unknown, never a guess.",
    ),
    Segment(
        "t13",
        "Accounts have a role, user or admin, in a profiles table that clients can only read, and the API checks "
        "it on the server. The backend page reads the chat log: users and their searches, and for each search "
        "how it was understood, the answer and the number check. Why these tours? lists every candidate with its "
        "conditions, score and status, including the twenty best rejected ones. Then the tool calls, and each "
        "model call with prompts, tokens, cost as reported by OpenRouter, and duration. Passwords and tokens "
        "never go into the log.",
    ),
    Segment(
        "t14",
        "The app is bilingual: English by default, German with one click. All web texts live in two catalogues "
        "with the same keys, and a test checks that no frame text is hard-coded. The web app sends the language "
        "with every chat message, so the backend writes answers, questions and its fixed sentences in that "
        "language, with an English or a German system prompt. A saved result keeps its language.",
    ),
    Segment(
        "t15",
        "Evaluation runs fifty-two fixed requests against the real agent, model, database and index, and checks "
        "the results with code. The last full run, with gpt-4o-mini on the thirty-first of October, passed all "
        "fifty-two: no invented tour among seventy-four tour ids, no unsupported number among five hundred and "
        "eighteen, all eight impossible wishes named, and a recall at five of one for knowledge questions, for "
        "under three cents. It was one run on a small, self-written set, before the English answers and the "
        "weather finder. A smoke test of nineteen prompts against the real model covers those.",
    ),
    Segment(
        "t16",
        "Finally, the limits. The location on the trail stays in the browser, own photos are private, and no "
        "e-mail or user id goes to the model. The app does not know whether a room is free, OpenStreetMap data "
        "can be out of date, and the model can still word something wrongly between the checked numbers and "
        "names. Thanks for watching.",
    ),
]


A = "backend/src/hikesense/agent/"
CODE = {  # code slide -> its panels, read from the repository at recording time
    "c06": [Snippet("backend/src/hikesense/ingest/day_hikes.py", "auto_decision",
                    mark=["gap_error", "MIN_KM", "LONG_DISTANCE_NETWORKS"])],
    "c07": [Snippet(A + "graph.py", start='    g.add_edge(START, "guard")', end="return g.compile(",
                    mark=["add_conditional_edges", "checkpointer"])],
    "c08": [Snippet(A + "understand.py", "_written", mark=["return any"]),
            Snippet(A + "understand.py", start="    for kind, lo, hi, approx in (", end="bounds.append(value)",
                    mark=["not _written(", "R27"])],
    "c09": [Snippet(A + "constraints.py", "select", mark=["matches.sort", "_near_misses(", "fallbacks = sorted"])],
    "c10": [Snippet(A + "grounding.py", "grounding_check", mark=["_supported", '"?"', "_unsupported_names("])],
    "c11": [Snippet(A + "weather.py", "matches", mark=["FINE_CODES", "False in checks", "SNOW_MIN_CM"])],
}  # fmt: skip


async def admin_shots(browser, base: str, out: Path) -> None:
    """Fresh screenshots of /admin (signed in as the local admin; reads the chat log, no agent turn)."""
    ctx = await browser.new_context(viewport={"width": VIEW_W, "height": VIEW_H}, device_scale_factor=SCALE)
    page = await ctx.new_page()
    await page.goto(base + "/anmelden")
    await page.get_by_label("E-mail", exact=True).fill("admin")
    await page.get_by_label("Password").fill("admin")
    await page.get_by_role("button", name="Sign in", exact=True).click()
    await page.wait_for_url(re.compile(r"/$"), timeout=20_000)
    await page.goto(base + "/admin")
    await page.get_by_text("Recent searches").wait_for(timeout=20_000)
    await page.wait_for_timeout(1500)
    near = page.get_by_role("button", name=re.compile("Under 300 m ascent"))
    if await near.count():
        await near.first.click()
    await page.get_by_text("Details", exact=True).wait_for()
    await page.wait_for_timeout(1500)
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(shots / "admin.jpg"), quality=90, type="jpeg")
    for name, text in [("admin-why", "Why these tours?"), ("admin-model", "Model · tokens · cost · duration")]:
        loc = page.get_by_text(text).first
        if await loc.count():
            await loc.evaluate("e => window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 90)")
            await page.wait_for_timeout(600)
            box = await loc.bounding_box()  # only the details column: the columns on its left end further up
            x = max(box["x"] - 24, 0) if box else 0
            clip = {"x": x, "y": 0, "width": VIEW_W - x, "height": VIEW_H}
            await page.screenshot(path=str(shots / f"{name}.jpg"), quality=90, type="jpeg", clip=clip)
    await ctx.close()


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status == 200
    except OSError:
        return False


async def main(out: Path, base: str, api: str) -> None:
    work = out / "work-tech"
    await synthesize(SEGMENTS, work / "voice")
    slides = (Path(__file__).parent / "slides.html").resolve()
    for s in SEGMENTS:
        print(f"{s.key}: {s.duration:5.1f}s")
    print(f"voice total {sum(s.duration for s in SEGMENTS):.0f}s")

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=BROWSER_ARGS)
        if reachable(base + "/") and reachable(api.rstrip("/") + "/health"):
            await admin_shots(browser, base, out)
        else:
            print("app not reachable, keeping the admin screenshots in out/shots/")
        missing = [n for n in ("results", "nearmiss", "weather", "fallback", "plan-map", "german", "admin-why")
                   if not (out / "shots" / f"{n}.jpg").exists()]  # fmt: skip
        if missing:
            raise SystemExit(f"missing screenshots {missing}: run user_demo.py first")
        await browser.close()
        browser = await p.chromium.launch()  # slides: 1920 × 1080 CSS pixels, no scale flag
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        await page.goto(slides.as_uri())
        await page.wait_for_load_state("networkidle")
        await page.evaluate(
            "([code, counts]) => { fillCounts(counts); fillCode(code); }", [render_slides(CODE), COUNTS]
        )
        await page.wait_for_timeout(1500)
        rec = Screencast(page, work / "frames")
        await page.evaluate("go('none')")
        await rec.start()
        for s in SEGMENTS:
            await page.evaluate(f"go('{s.key}')")
            await narrate(rec, s, pad=1.2)
        await rec.stop(tail=1.5)
        await browser.close()

    render(rec, SEGMENTS, out / "hikesense-tech.mp4")
    print("wrote", out / "hikesense-tech.mp4", f"{rec.shift(rec.end):.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    ap.add_argument("--base", default="http://localhost:3104", help="running web app, for the /admin screenshots")
    ap.add_argument("--api", default="http://localhost:8004", help="its API (checked for /health)")
    args = ap.parse_args()
    asyncio.run(main(args.out.resolve(), args.base.rstrip("/"), args.api))
