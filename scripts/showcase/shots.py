"""Re-takes docs/showcase/01–12 against the local app (EN UI, real model).

    python -m venv /tmp/pw && /tmp/pw/bin/pip install playwright
    /tmp/pw/bin/python scripts/showcase/shots.py docs/showcase [01 02 …]

Needs the local stack (make up), the test account from `make smoke-user` (password from .env) and
guest chats left for today (10 per IP): about 12 chat turns, a few tenths of a cent. A saved plan
used for "Unterwegs" is deleted again at the end.
"""
import asyncio, re, sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://localhost:3000"
OUT = Path(sys.argv[1])
ONLY = set(sys.argv[2:])
env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parents[2] / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
USER, PW = "smoke@hikesense.local", env["HIKESENSE_SMOKE_PASSWORD"].strip().strip('"')
ON_DAY1 = {"latitude": 48.2511, "longitude": 8.1740, "accuracy": 15}


def want(n):
    return not ONLY or n in ONLY


async def shot(page, name, **kw):
    await page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=85, **kw)
    print("shot", name)


async def done(page):
    await page.wait_for_timeout(1200)
    await page.get_by_role("button", name="Stop").wait_for(state="detached", timeout=240_000)
    await page.wait_for_timeout(2500)


async def send(page, text):
    await page.get_by_label("Message", exact=True).fill(text)
    await page.get_by_role("button", name="Send").click()
    await done(page)


async def sign_in(page):
    await page.goto(BASE + "/anmelden")
    await page.get_by_label("E-mail", exact=True).fill(USER)
    await page.get_by_label("Password").fill(PW)
    await page.get_by_role("button", name="Sign in", exact=True).click()
    await page.wait_for_url(re.compile(r"/$"), timeout=20_000)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        desk = await b.new_context(viewport={"width": 1920, "height": 1080}, locale="en-GB", timezone_id="Europe/Berlin")
        page = await desk.new_page()
        if want("01") or want("02") or want("07") or want("08"):
            await page.goto(BASE + "/")
            await page.wait_for_timeout(3000)
            if want("01"):
                await shot(page, "01-startseite")
            await send(page, "A round walk near Titisee, about 10 km")
            await send(page, "Under 300 m ascent, please")
            await shot(page, "02-tagestouren")
            await page.locator("article a[href^='/t/']").first.click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(5000)
            await shot(page, "08-routenkarte")
            photos = page.get_by_role("heading", name=re.compile("Photos", re.I)).first
            if await photos.count():
                await photos.scroll_into_view_if_needed()
                await page.evaluate("window.scrollBy(0, -120)")
            else:
                await page.evaluate("window.scrollBy(0, 900)")
            await page.wait_for_timeout(2500)
            await shot(page, "07-routenseite-fotos")
        if want("03") or want("04"):
            await page.goto(BASE + "/")
            await page.get_by_role("button", name=re.compile("New search")).click() if await page.get_by_role("button", name=re.compile("New search")).count() else None
            await page.wait_for_timeout(1500)
            await send(page, "Round walk, under 200 m ascent, over 15 km, Feldberg")
            await page.get_by_role("button", name=re.compile(r"^Feldberg \(Schwarzwald\)")).first.click()
            await done(page)
            await shot(page, "03-unerfuellbar-chat")
            await page.locator("[data-results-scroll]").evaluate("el => el.scrollTo(0, 0)")
            await shot(page, "04-unerfuellbar-ausweichtouren")
        if want("09"):
            fresh = await (await b.new_context(viewport={"width": 1920, "height": 1080}, locale="en-GB", timezone_id="Europe/Berlin")).new_page()
            await fresh.goto(BASE + "/")
            await fresh.wait_for_timeout(2500)
            await send(fresh, "How did the Westweg come about?")
            await fresh.locator("summary", has_text="sources").last.click()
            await fresh.wait_for_timeout(600)
            await fresh.locator("[data-chat-scroll]").evaluate("el => el.scrollTo(0, el.scrollHeight)")
            await fresh.wait_for_timeout(1200)
            await shot(fresh, "09-wissensfrage-quellen")
        plan_id = None
        if want("05") or want("06") or want("10") or want("11"):
            await sign_in(page)
            nb = page.get_by_role("button", name=re.compile("New search"))
            if await nb.count():
                await nb.click()
            await page.wait_for_timeout(1500)
            await send(page, "3 days on the Westweg from Hausach")
            await shot(page, "05-mehrtagesplan")
            await page.get_by_role("link", name=re.compile("View plan with map")).click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(6000)
            await shot(page, "06-tagesabschnitte-karte")
            await page.get_by_role("button", name=re.compile("^Save")).first.click()
            await page.wait_for_timeout(2500)
            await page.goto(BASE + "/meine-plaene")
            await page.wait_for_timeout(2500)
            hrefs = await page.eval_on_selector_all("li a[href^='/plan?id=']", "els => els.map(a => a.getAttribute('href'))")
            plan_id = hrefs[0].split("id=")[1] if hrefs else None
            print("plan", plan_id)
        state = await desk.storage_state()
        phone = await b.new_context(
            viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
            locale="en-GB", timezone_id="Europe/Berlin", storage_state=state,
            geolocation=ON_DAY1, permissions=["geolocation"],
        )
        ph = await phone.new_page()
        if want("12"):
            await ph.context.clear_cookies()
            await ph.goto(BASE + "/")
            await ph.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            await ph.goto(BASE + "/")
            await ph.wait_for_timeout(3500)
            await shot(ph, "12-startseite-handy")
        if plan_id and (want("10") or want("11")):
            await ph.context.add_cookies([])
            ph2 = await (await b.new_context(
                viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                locale="en-GB", timezone_id="Europe/Berlin", storage_state=state,
                geolocation=ON_DAY1, permissions=["geolocation"],
            )).new_page()
            await ph2.clock.set_fixed_time(datetime(2026, 11, 6, 10, 0))
            await ph2.goto(f"{BASE}/unterwegs?plan={plan_id}&day=1")
            await ph2.get_by_role("button", name="Start", exact=True).click()
            await ph2.get_by_text(re.compile("km to go")).wait_for(timeout=30_000)
            await ph2.wait_for_timeout(4000)
            await shot(ph2, "10-unterwegs-handy", clip={"x": 0, "y": 0, "width": 390, "height": 410})
            await ph2.get_by_text("Map", exact=False).last.click()
            await ph2.wait_for_timeout(5000)
            await ph2.evaluate("window.scrollBy(0, 330)")
            await ph2.wait_for_timeout(1500)
            await shot(ph2, "11-unterwegs-karte-handy")
            # clean up: the saved plan of this run
            await page.goto(BASE + "/meine-plaene")
            await page.wait_for_timeout(2500)
            for _ in range(5):  # this run's plan and any left over from an aborted run
                li = page.locator("li", has=page.locator("a[href^='/plan?id=']"))
                if not await li.count():
                    break
                await li.first.get_by_role("button").first.click()
                await page.wait_for_timeout(1500)
                print("deleted a plan")
        await b.close()

asyncio.run(main())
