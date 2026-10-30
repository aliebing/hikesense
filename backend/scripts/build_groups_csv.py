"""One-off helper that wrote data/curated/groups.csv: verifies each candidate group against its OWN
web page and takes the coordinate from the `places` table (never guessed).

A group is kept only if robots.txt allows the fetch, the page answers HTTP 200 and the group's
name stands on the page (whitespace and case ignored); the place must be exactly one town/village
row in `places`. Everything else is printed as "LEFT OUT". Fetches are 3 s apart, with a proper
User-Agent. Run: cd backend && uv run python scripts/build_groups_csv.py [out.csv]
"""

import csv
import html
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date

import psycopg

UA = os.environ.get("HIKEALL_USER_AGENT") or "HikeAllAbout/0.1 (student project)"
# (id, name as written on the page, kind, place as named in `places`, own page)
CANDIDATES = [
    ("swv-freiburg", "Schwarzwaldverein Freiburg", "wanderverein", "Freiburg im Breisgau", "https://schwarzwaldverein-freiburg.de/"),
    ("swv-lahr", "Schwarzwaldverein Lahr", "wanderverein", "Lahr/Schwarzwald", "https://www.schwarzwaldverein-lahr.de"),
    ("swv-baden-baden", "Schwarzwaldverein Baden-Baden", "wanderverein", "Baden-Baden", "https://schwarzwaldverein-baden-baden.de/"),
    ("swv-offenburg", "Schwarzwaldverein Offenburg", "wanderverein", "Offenburg", "https://schwarzwaldverein-offenburg.de/"),
    ("swv-villingen-schwenningen", "Schwarzwaldverein Villingen-Schwenningen", "wanderverein", "Villingen-Schwenningen", "https://www.schwarzwaldverein-vs.de/"),
    ("swv-gengenbach", "Schwarzwaldverein Gengenbach", "wanderverein", "Gengenbach", "https://schwarzwaldverein-gengenbach.de/"),
    ("swv-emmendingen", "Schwarzwaldverein Emmendingen", "wanderverein", "Emmendingen", "https://swv-em.de/"),
    ("swv-todtnau", "Schwarzwaldverein Todtnau", "wanderverein", "Todtnau", "https://schwarzwaldverein-todtnau.de/"),
    ("swv-kandern", "Schwarzwaldverein Kandern", "wanderverein", "Kandern", "https://swv-kandern.de/"),
    ("swv-waldkirch", "Schwarzwaldverein Waldkirch-Kandel", "wanderverein", "Waldkirch", "https://schwarzwaldverein-waldkirch.de/"),
    ("swv-oberkirch", "Schwarzwaldverein Oberkirch", "wanderverein", "Oberkirch", "https://schwarzwaldverein-oberkirch.de/"),
    ("swv-calw", "Schwarzwaldverein Calw", "wanderverein", "Calw", "https://schwarzwaldverein-calw.de/"),
    ("swv-st-georgen", "Schwarzwaldverein St. Georgen", "wanderverein", "St. Georgen", "https://www.schwarzwaldverein-st-georgen.de"),
    ("swv-furtwangen", "Schwarzwaldverein Ortsgruppe Furtwangen", "wanderverein", "Furtwangen", "https://www.schwarzwaldverein-furtwangen.de"),
    ("swv-hausach", "Schwarzwaldverein Hausach", "wanderverein", "Hausach", "https://schwarzwaldverein-hausach.de/"),
    ("swv-wolfach", "Schwarzwaldverein Wolfach", "wanderverein", "Wolfach", "https://schwarzwaldverein-wolfach.de/"),
    ("swv-gernsbach", "Schwarzwaldverein Gernsbach", "wanderverein", "Gernsbach", "https://schwarzwaldverein-gernsbach.de/"),
    ("swv-schramberg", "Schwarzwaldverein Schramberg", "wanderverein", "Schramberg", "https://www.schwarzwaldverein-schramberg.de/de/Home"),
    ("swv-donaueschingen", "Schwarzwaldverein Donaueschingen", "wanderverein", "Donaueschingen", "https://schwarzwaldverein-donaueschingen.de/"),
    ("swv-titisee", "Schwarzwaldverein Ortsgruppe Titisee", "wanderverein", "Titisee", "https://www.schwarzwaldverein-titisee.de"),
    ("swv-elzach", "Schwarzwaldverein Elzach", "wanderverein", "Elzach", "https://www.schwarzwaldverein-elzach.de"),
    ("dav-freiburg-breisgau", "Sektion Freiburg-Breisgau des Deutschen Alpenvereins", "alpenverein", "Freiburg im Breisgau", "https://www.dav-freiburg.de/de/"),
    ("dav-pforzheim", "Deutscher Alpenverein Sektion Pforzheim", "alpenverein", "Pforzheim", "https://alpenverein-pforzheim.de/"),
    ("dav-baden-baden", "Alpenverein Baden-Baden", "alpenverein", "Baden-Baden", "https://alpenverein-baden-baden.de/"),
    ("dav-offenburg", "Sektion Offenburg", "alpenverein", "Offenburg", "https://www.dav-offenburg.de"),
    ("dav-lahr", "Sektion Lahr", "alpenverein", "Lahr/Schwarzwald", "https://www.dav-lahr.de"),
]  # fmt: skip


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(s)).strip().lower()


def fetch(url: str) -> tuple[int, str] | str:
    p = urllib.parse.urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": UA})
        rp.parse(urllib.request.urlopen(req, timeout=10).read().decode("utf8", "ignore").splitlines())
    except Exception:  # noqa: BLE001 - no readable robots.txt: nothing forbidden
        rp.parse([])
    if not rp.can_fetch(UA, url):
        return "robots.txt verbietet den Abruf"
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15)
        body = r.read(1_000_000).decode("utf8", "ignore")
        return r.status, body
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:60]}"


def main(out: str) -> None:
    conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])
    today = date.today().isoformat()
    kept, left = [], []
    for gid, name, kind, place, url in CANDIDATES:
        got = fetch(url)
        time.sleep(3)
        if isinstance(got, str):
            left.append((gid, got))
            continue
        status, body = got
        text = norm(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", body, flags=re.DOTALL))
        if status != 200 or norm(name) not in text:
            left.append((gid, f"HTTP {status}, Name nicht auf der Seite"))
            continue
        rows = conn.execute(
            "select st_y(geom), st_x(geom) from places where name = %s and kind in ('town','village')",
            (place,),
        ).fetchall()
        if len(rows) != 1:
            left.append((gid, f"Ort „{place}“ nicht eindeutig in places ({len(rows)} Treffer)"))
            continue
        lat, lon = rows[0]
        print(f"OK       {gid}: HTTP 200, Name auf der Seite, {place} {lat:.4f},{lon:.4f}")
        kept.append({
            "id": gid, "name": name, "kind": kind, "place": place,
            "lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "url": url, "source_url": url,
            "checked_at": today, "status": "vorschlag",
            "note": "Vorschlag Claude: Name und Seite am Prüfdatum abgerufen (HTTP 200); bitte prüfen",
        })  # fmt: skip
    for gid, why in left:
        print(f"LEFT OUT {gid}: {why}")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(kept[0]))
        w.writeheader()
        w.writerows(kept)
    print(f"{len(kept)} kept, {len(left)} left out -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../data/curated/groups.csv")
