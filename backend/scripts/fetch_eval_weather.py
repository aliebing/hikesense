"""One-off helper that wrote data/eval/weather.json: real Open-Meteo daily values for every stage
place of the long-distance trails (data/curated/trails.yaml), 2026-11-02 to 2026-11-15, in ONE
forecast request. The eval run reads the file through evaluation.FixtureWeather and never asks
Open-Meteo itself. Values are stored as fetched; a day changed by hand must carry
"edited": true and a "reason" (none so far unless the file says so).

Run: cd backend && uv run python scripts/fetch_eval_weather.py [out.json]
"""

import json
import sys
from datetime import date
from pathlib import Path

import yaml

from hikeall.adapters.http import make_http_client
from hikeall.adapters.open_meteo import OpenMeteoClient

REPO = Path(__file__).resolve().parents[2]
# Open-Meteo forecasts at most 16 days incl. today: fetched on 2026-10-31, 2026-11-15 is the
# last day it serves (2026-11-16 was refused with HTTP 400), so the file ends one day early.
START, END = date(2026, 11, 2), date(2026, 11, 15)


def stage_places() -> list[dict]:
    data = yaml.safe_load((REPO / "data/curated/trails.yaml").read_text(encoding="utf-8"))
    seen: dict[str, dict] = {}
    for trail in data["trails"]:
        if trail.get("kind") != "long_distance":
            continue
        for stage in trail["stages"]:
            for p in (stage["start"], stage["end"]):
                seen.setdefault(p["name"], {"name": p["name"], "lat": p["lat"], "lon": p["lon"]})
    return list(seen.values())


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "data/eval/weather.json"
    places = stage_places()
    with make_http_client(30) as http:
        series = OpenMeteoClient(http).daily_many(
            [(p["lat"], p["lon"]) for p in places], START, END
        )
    for p, days in zip(places, series, strict=True):
        p["days"] = [
            {
                "date": w.date.isoformat(),
                "code": w.code,
                "t_min_c": w.t_min_c,
                "t_max_c": w.t_max_c,
                "precip_mm": w.precip_mm,
                "precip_prob_pct": w.precip_prob_pct,
            }
            for w in days
        ]
    doc = {
        "source": "Open-Meteo.com (CC BY 4.0)",
        "url": "https://open-meteo.com/",
        "retrieved_at": date.today().isoformat(),
        "start": START.isoformat(),
        "end": END.isoformat(),
        "lookup": "nächster gespeicherter Ort innerhalb von 25 km Luftlinie, sonst Fehler",
        "places": places,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(places)} Orte, {START} bis {END} -> {out}")


if __name__ == "__main__":
    main()
