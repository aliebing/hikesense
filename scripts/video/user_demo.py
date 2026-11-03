"""Video 1: how a hiker works with Hike all about (British English voice-over, real screen recording).

Needs the API and the web app running (see README.md). Signs in as the local admin, makes six real chat turns (about
$0.0005 each with openai/gpt-4o-mini) and saves one search and one plan, which it deletes again after the recording.
Usage:
    python scripts/video/user_demo.py [--base http://localhost:3104] [--api http://localhost:8004] [--out …]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright
from recorder import (
    BROWSER_ARGS,
    CURSOR_JS,
    SCALE,
    VIEW_H,
    VIEW_W,
    Screencast,
    Segment,
    click,
    glide,
    glide_to,
    narrate,
    render,
    synthesize,
)

USER, PASSWORD = "admin", "admin"  # local admin from `make admin-user` (README "Konto anlegen")
Q_TITISEE = "A round walk near Titisee, about 10 km"
Q_ASCENT = "Under 300 m ascent, please"
Q_WEATHER = "A round walk near Titisee in fine weather"
Q_FELDBERG = "Round walk, under 200 m ascent, over 15 km, Feldberg"
Q_MULTIDAY = "3 days on the Westweg from Hausach"

SEGMENTS = [
    Segment(
        "01_intro",
        "Welcome to Hike all about, a hiking planner that you use through a chat. It plans day hikes and "
        "multi-day tours with places to stay, walking times and weather, in the Black Forest, at Lake Constance "
        "and in the Palatinate Forest. The interface is in English by default; the flags switch it to German.",
    ),
    Segment("02_signin", "Planning needs an account, so I sign in, here as the local admin."),
    Segment("03_type", "Now I write what I want, in my own words: a round walk near Titisee, about ten kilometres."),
    Segment(
        "04_agent",
        "The language model turns my message into a structured request. The code keeps a number only if it "
        "really is in my message, and it finds and checks the tours itself.",
    ),
    Segment(
        "05_reply",
        "The chips show what was understood, including the default search radius of fifteen kilometres. Every "
        "tile has a tick for each condition. The model writes the chat text, and the code checks every number "
        "in it against the search results.",
    ),
    Segment("06_refine", "I narrow it down: under three hundred metres of ascent. The rest of the request stays."),
    Segment(
        "07_nearmiss",
        "Only two tours fit now, so a near miss fills up the list. The yellow card breaks exactly one condition, "
        "by a small margin, and says by how much.",
    ),
    Segment(
        "08_tour",
        "A tile opens the tour page: the route on a map with places to stay, inns and viewpoints, a description "
        "built from the data, the elevation profile from the Copernicus terrain model, and accommodation near "
        "the trail with its distance from the route. The photos come from Wikimedia Commons, with author and "
        "licence.",
    ),
    Segment(
        "09_weather",
        "Back in the chat, a weather wish: in fine weather. The model only spots the wish. The code checks the "
        "Open-Meteo forecast for the next fourteen days against fixed thresholds and lists the days that fit.",
    ),
    Segment("10_save", "Save result keeps this as a snapshot under My plans."),
    Segment(
        "11_clarify",
        "A new conversation, and a wish that cannot be met: a round walk, under two hundred metres of ascent, "
        "over fifteen kilometres, Feldberg. Feldberg is ambiguous, so the app asks back, and I pick the peak.",
    ),
    Segment(
        "12_fallback",
        "No tour meets every wish, and the code says so first, with the reason. The cards show tours that break "
        "exactly one condition, marked with a cross and the real value.",
    ),
    Segment(
        "13_multiday",
        "Now multi-day planning: three days on the Westweg from Hausach. Each day is about fifteen kilometres, "
        "and ends at a place to stay at most one kilometre from the trail.",
    ),
    Segment(
        "14_plan",
        "The plan page shows the day sections on the map, and each day with its distance, times and "
        "accommodation. Times are walking times to DIN 33466, without breaks. With a start date, the weather "
        "is added too. I save the plan.",
    ),
    Segment("15_myplans", "My plans shows what I have saved. Only I can see it."),
    Segment(
        "16_german",
        "The flags switch the language without reloading the page, and numbers and dates follow German "
        "conventions. Back to English.",
    ),
    Segment(
        "17_admin",
        "As admin I also get the Backend: the users and their searches from the chat log, with cost and "
        "duration. Here is the search with the near miss.",
    ),
    Segment(
        "18_admin_why",
        "The details show how it was understood, the answer, and the number check. Why these tours? lists every "
        "candidate with its real values and its status: shown, near miss, or rejected. Below are the tool calls, "
        "and each model call with tokens, cost and duration.",
    ),
    Segment(
        "19_outro",
        "That is Hike all about: the code finds and checks real routes, and the model puts them into words. The "
        "second video shows how it works inside.",
    ),
]


async def shot(page, out: Path, name: str) -> None:
    """Screenshot of the viewport for the slides of the technical video (tech_demo.py)."""
    (out / "shots").mkdir(parents=True, exist_ok=True)
    hide = "v => { const c = document.getElementById('__demo_cursor'); if (c) c.style.visibility = v; }"
    await page.evaluate(hide, "hidden")  # no pointer dot on the slides
    await page.screenshot(path=str(out / "shots" / f"{name}.jpg"), quality=90, type="jpeg")
    await page.evaluate(hide, "visible")


async def send(rec: Screencast, page, text: str, delay: int = 45) -> None:
    """Type a chat message and send it; the agent's wait is cut from the video."""
    box = page.get_by_label("Message", exact=True)
    await click(page, box, 800)
    await page.keyboard.type(text, delay=delay)
    await asyncio.sleep(0.3)
    await click(page, page.get_by_role("button", name="Send"), 500)


async def finished(page) -> None:
    """Wait until the agent turn has finished (the 'thinking …' line is gone)."""
    await page.wait_for_timeout(600)
    await page.get_by_text("thinking …").wait_for(state="detached", timeout=120_000)
    await page.wait_for_timeout(800)


async def done(rec: Screencast, page) -> None:
    """Wait for the agent turn and cut the dead time out of the video."""
    await rec.wait_cut(finished(page))


async def chat_scroll(page, to: str = "bottom", text: str | None = None) -> None:
    """Scroll the chat history smoothly: to the bottom, or so that the last item with `text` is at the top."""
    await page.evaluate(
        """([to, text]) => {
          const ol = document.querySelector("ol[aria-label='History']");
          if (!ol) return;
          let top = ol.scrollHeight;
          if (to === 'text') {
            const hits = [...ol.querySelectorAll('li')].filter((li) => li.innerText.includes(text));
            if (hits.length) top = hits[hits.length - 1].offsetTop - ol.offsetTop - 8;
          }
          ol.scrollTo({ top, behavior: 'smooth' });
        }""",
        [to, text],
    )


async def wheel(page, dy: int, steps: int = 8, pause: float = 0.08) -> None:
    for _ in range(steps):
        await page.mouse.wheel(0, dy / steps)
        await asyncio.sleep(pause)


SAVED_LINKS = "els => els.map((a) => a.getAttribute('href'))"


async def sign_in(page, base: str) -> None:
    await page.goto(base + "/anmelden")
    await page.get_by_label("E-mail", exact=True).fill(USER)
    await page.get_by_label("Password").fill(PASSWORD)
    await page.get_by_role("button", name="Sign in", exact=True).click()
    await page.wait_for_url(re.compile(r"/$"), timeout=20_000)


async def saved_before(browser, base: str) -> set[str]:
    """Links of the account's saved searches and plans before this run (in a separate, unrecorded context)."""
    ctx = await browser.new_context()
    page = await ctx.new_page()
    await sign_in(page, base)
    await page.goto(base + "/meine-plaene")
    await page.wait_for_timeout(2500)
    hrefs = set(await page.eval_on_selector_all("li a[href*='id=']", SAVED_LINKS))
    await ctx.close()
    return hrefs


async def cleanup(page, base: str, before: set[str]) -> None:
    """Delete what this run saved (after the recording), so re-runs don't pile up entries under My plans."""
    await page.goto(base + "/meine-plaene")
    await page.wait_for_timeout(2500)
    for href in set(await page.eval_on_selector_all("li a[href*='id=']", SAVED_LINKS)) - before:
        li = page.locator("li", has=page.locator(f"a[href='{href}']"))
        await li.get_by_role("button").first.click()
        await page.wait_for_timeout(1200)
        print("deleted", href)


async def main(base: str, api: str, out: Path) -> None:
    with urllib.request.urlopen(api.rstrip("/") + "/health", timeout=10) as r:  # noqa: ASYNC210 - once, at start
        assert r.status == 200, "API not healthy"
    work = out / "work-user"
    await synthesize(SEGMENTS, work / "voice")
    seg = {s.key: s for s in SEGMENTS}
    for s in SEGMENTS:
        print(f"{s.key}: {s.duration:5.1f}s")

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=BROWSER_ARGS)
        before = await saved_before(browser, base)
        ctx = await browser.new_context(
            viewport={"width": VIEW_W, "height": VIEW_H}, device_scale_factor=SCALE, locale="en-GB",
            timezone_id="Europe/Berlin",
        )  # fmt: skip
        await ctx.add_init_script(CURSOR_JS)
        page = await ctx.new_page()
        await page.goto(base + "/")
        await page.wait_for_timeout(3500)

        rec = Screencast(page, work / "frames")
        await rec.start()

        async def intro():
            await asyncio.sleep(1.0)
            await glide(page, 760, 300, 2200)
            await asyncio.sleep(3.0)
            await glide_to(page, page.get_by_label("English"), 1800)
            await asyncio.sleep(1.2)
            await glide_to(page, page.get_by_label("Deutsch"), 700)
            await shot(page, out, "home")

        await narrate(rec, seg["01_intro"], intro)

        async def signin():
            await click(page, page.get_by_role("link", name="Sign in").first, 900)
            await page.get_by_label("Password").wait_for()
            await page.wait_for_timeout(600)
            await click(page, page.get_by_label("E-mail", exact=True), 700)
            await page.keyboard.type(USER, delay=90)
            await click(page, page.get_by_label("Password"), 500)
            await page.keyboard.type(PASSWORD, delay=90)
            await click(page, page.get_by_role("button", name="Sign in", exact=True), 600)
            await page.wait_for_url(re.compile(r"/$"), timeout=20_000)
            await page.get_by_label("Message", exact=True).wait_for(timeout=20_000)

        await narrate(rec, seg["02_signin"], signin, pad=0.3)

        await narrate(rec, seg["03_type"], lambda: send(rec, page, Q_TITISEE), pad=0.2)

        async def agent():
            await glide(page, 1000, 420, 1500)

        await narrate(rec, seg["04_agent"], agent, pad=0.2)
        await done(rec, page)

        async def reply():
            await chat_scroll(page, "text", Q_TITISEE)
            chips = page.get_by_label("Understood criteria").last
            await glide_to(page, chips, 1200)
            await asyncio.sleep(3.0)
            await glide(page, 900, 330, 1200)
            await asyncio.sleep(1.0)
            await glide_to(page, page.get_by_text("✓", exact=True).first, 1000)
            await asyncio.sleep(2.0)
            await shot(page, out, "results")
            await chat_scroll(page, "bottom")
            await glide(page, 350, 600, 1500)

        await narrate(rec, seg["05_reply"], reply)

        async def refine():
            await glide_to(page, page.get_by_text("Too many?"), 1000, dx=0.3)
            await asyncio.sleep(0.8)
            await send(rec, page, Q_ASCENT)

        await narrate(rec, seg["06_refine"], refine, pad=0.2)
        await done(rec, page)

        async def nearmiss():
            card = page.get_by_text("Near miss", exact=True).first
            await glide_to(page, card, 1300)
            await asyncio.sleep(1.5)
            await glide_to(page, page.get_by_text("everything else fits").first, 900)
            await asyncio.sleep(1.5)
            await shot(page, out, "nearmiss")
            await chat_scroll(page, "text", Q_ASCENT)

        await narrate(rec, seg["07_nearmiss"], nearmiss)

        async def tour():
            await click(page, page.get_by_text("Details and map").first, 1000)
            await page.get_by_text("Elevation profile").first.wait_for(timeout=30_000)
            await page.wait_for_timeout(2500)  # map tiles
            await glide(page, 760, 450, 1200)
            await asyncio.sleep(1.5)
            await shot(page, out, "tour-map")
            await wheel(page, 520, 10)
            await glide_to(page, page.get_by_text("Description", exact=True), 800)
            await asyncio.sleep(1.2)
            await glide_to(page, page.get_by_text(re.compile("^Elevation profile")).first, 800)
            await asyncio.sleep(1.5)
            await glide_to(page, page.get_by_text("Places to stay nearby"), 900)
            await asyncio.sleep(1.5)
            await shot(page, out, "tour-details")
            await wheel(page, 520, 10)
            await glide_to(page, page.get_by_text("Photos", exact=True), 900)
            await asyncio.sleep(0.8)
            await click(page, page.get_by_label("Next picture").first, 700)
            await asyncio.sleep(1.0)

        await narrate(rec, seg["08_tour"], tour)

        async def weather():
            await click(page, page.get_by_role("link", name=re.compile("Back to suggestions")).first, 900)
            await page.get_by_label("Message", exact=True).wait_for(timeout=20_000)
            await page.wait_for_timeout(800)
            await send(rec, page, Q_WEATHER)
            await finished(page)  # under the narration: no cut needed unless the turn outlasts it
            card = page.get_by_label("Weather day finder").last
            await chat_scroll(page, "text", "Days for")
            await asyncio.sleep(0.5)
            await glide_to(page, card, 1000)
            await asyncio.sleep(1.5)
            await shot(page, out, "weather")

        await narrate(rec, seg["09_weather"], weather, pad=0.3)

        async def save_click():
            await click(page, page.get_by_role("button", name="Save result"), 1000)
            await asyncio.sleep(1.0)

        await narrate(rec, seg["10_save"], save_click)

        async def clarify():
            # a new conversation: the chat lives in the tab's sessionStorage (one thread per tab)
            await page.evaluate("sessionStorage.clear()")
            await page.reload()
            await page.get_by_label("Message", exact=True).wait_for(timeout=20_000)
            await page.wait_for_timeout(600)
            await send(rec, page, Q_FELDBERG, delay=35)

        await narrate(rec, seg["11_clarify"], clarify, pad=0.1)
        await done(rec, page)
        await chat_scroll(page, "bottom")
        option = page.get_by_role("button", name=re.compile(r"\(peak\)"))
        await glide_to(page, option, 900)
        await asyncio.sleep(1.0)
        await shot(page, out, "clarify")
        await click(page, option, 300)
        await done(rec, page)

        async def fallback():
            note = page.get_by_role("note").first
            await glide_to(page, note, 1100, dx=0.3)
            await asyncio.sleep(2.5)
            await glide_to(page, page.get_by_text("✗", exact=True).first, 1200)
            await asyncio.sleep(2.0)
            await shot(page, out, "fallback")
            await glide_to(page, page.get_by_text("✗", exact=True).nth(1), 1000)

        await narrate(rec, seg["12_fallback"], fallback)

        async def multiday():
            await send(rec, page, Q_MULTIDAY)

        await narrate(rec, seg["13_multiday"], multiday, pad=0.1)
        await done(rec, page)

        async def plan():
            await glide_to(page, page.get_by_text("Day 1", exact=True).first, 900)
            await asyncio.sleep(1.0)
            await shot(page, out, "plan-tiles")
            await click(page, page.get_by_role("link", name=re.compile("View plan with map")), 900)
            await page.get_by_label("Days").first.wait_for(timeout=30_000)
            await page.wait_for_timeout(2500)
            await glide(page, 760, 380, 1200)
            await asyncio.sleep(1.5)
            await shot(page, out, "plan-map")
            await wheel(page, 560, 10)
            await glide_to(page, page.get_by_text("All times without breaks", exact=False).first, 900, dx=0.3)
            await asyncio.sleep(1.5)
            await shot(page, out, "plan-days")
            await wheel(page, 300, 8)
            await asyncio.sleep(1.5)
            await wheel(page, -860, 10)
            await click(page, page.get_by_role("button", name="Save", exact=True).first, 900)
            await asyncio.sleep(1.0)

        await narrate(rec, seg["14_plan"], plan)

        async def myplans():
            await click(page, page.get_by_role("link", name="My plans"), 900)
            await page.get_by_text("Saved searches").wait_for(timeout=20_000)
            await page.wait_for_timeout(800)
            await glide_to(page, page.get_by_text("Saved searches"), 900)
            await asyncio.sleep(1.0)
            await glide_to(page, page.get_by_text("Tours and plans"), 900)
            await shot(page, out, "myplans")

        await narrate(rec, seg["15_myplans"], myplans)

        async def german():
            await click(page, page.get_by_label("Deutsch"), 900)
            await page.get_by_text("Meine Pläne").first.wait_for(timeout=20_000)
            await asyncio.sleep(0.8)
            await glide(page, 600, 250, 1000)
            await shot(page, out, "german")
            await asyncio.sleep(max(seg["16_german"].duration - 6.5, 1.0))
            await click(page, page.get_by_label("English"), 800)
            await page.get_by_text("My plans").first.wait_for(timeout=20_000)

        await narrate(rec, seg["16_german"], german)

        async def admin():
            await click(page, page.get_by_role("link", name="Backend"), 900)
            await page.get_by_text("Recent searches").wait_for(timeout=20_000)
            await page.wait_for_timeout(1500)
            await glide_to(page, page.get_by_text("Users", exact=True), 900, only_y=True)
            await asyncio.sleep(1.0)
            await glide_to(page, page.get_by_text("Recent searches"), 900, only_y=True)
            await asyncio.sleep(1.0)
            row = page.get_by_role("button", name=re.compile(re.escape(Q_ASCENT))).first
            await click(page, row, 1100)
            await page.get_by_text("Why these tours?").wait_for(timeout=20_000)
            await asyncio.sleep(0.8)
            await shot(page, out, "admin")

        await narrate(rec, seg["17_admin"], admin)

        async def why():
            await glide_to(page, page.get_by_text("Understood as"), 900, dx=0.05, only_y=True)
            await asyncio.sleep(1.2)
            await glide_to(page, page.get_by_text(re.compile("^Number check")), 900, dx=0.05, only_y=True)
            await asyncio.sleep(1.0)
            await glide_to(page, page.get_by_text("Why these tours?"), 1000, dx=0.05, only_y=True)
            await asyncio.sleep(1.0)
            await shot(page, out, "admin-why")
            await wheel(page, 420, 10)
            await asyncio.sleep(2.0)
            await glide_to(page, page.get_by_text(re.compile(r"^Tool calls")), 1000, dx=0.05, only_y=True)
            await asyncio.sleep(1.2)
            await shot(page, out, "admin-tools")
            await glide_to(page, page.get_by_text("Model · tokens · cost · duration"), 1400, dx=0.05, only_y=True)
            await asyncio.sleep(1.5)
            await shot(page, out, "admin-model")

        await narrate(rec, seg["18_admin_why"], why)

        async def outro():
            await click(page, page.get_by_role("link", name="Hike all about").first, 900)
            await page.wait_for_timeout(1500)
            await glide(page, 760, 420, 1800)

        await narrate(rec, seg["19_outro"], outro, pad=1.5)
        await rec.stop(tail=1.0)

        await cleanup(page, base, before)
        await browser.close()

    render(rec, SEGMENTS, out / "hikeallabout-user.mp4")
    print("wrote", out / "hikeallabout-user.mp4", f"{rec.shift(rec.end):.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3104", help="web app (production build)")
    ap.add_argument("--api", default="http://localhost:8004", help="API, only checked for /health")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    a = ap.parse_args()
    asyncio.run(main(a.base.rstrip("/"), a.api, a.out.resolve()))
