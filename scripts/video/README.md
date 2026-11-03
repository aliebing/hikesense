# Demo videos

Three narrated videos with synthetic voices (edge-tts): two in English with a British voice (`en-GB-RyanNeural`), and one in English and German (`de-DE-ConradNeural`). The tooling is adapted from CineSense (`~/projects/CineSenseAi/scripts/video/`).

- `user_demo.py` records **how a hiker uses Hike all about**: a real screen recording of the running app in English. Start page with the flags, sign-in as the local admin, the chat "A round walk near Titisee, about 10 km" (understood chips, tiles with ✓ per condition), the follow-up "Under 300 m ascent, please" (near-miss card), a tour page (map, elevation profile, places to stay, photos), "A round walk near Titisee in fine weather" (weather days card), "Save result", a new conversation with "Round walk, under 200 m ascent, over 15 km, Feldberg" (clarify question, option click, fallback tours), "3 days on the Westweg from Hausach" (plan, plan page with map, Save), My plans, 🇩🇪 and back, and the Backend `/admin` with the details of the near-miss search. It writes `out/hikeallabout-user.mp4` (about 3:45) and screenshots to `out/shots/`.
- `tech_demo.py` explains **how it works inside** on animated slides (`slides.html`): architecture, data and licences, the three regions, the quality rules for day hikes, the LangGraph graph, "the code decides, the model words it", conditions and near misses, grounding in both languages, the weather day finder, roles and the admin backend, the bilingual design, evaluation, limits. Code slides show real excerpts that `code_snippets.py` reads from the repository at recording time (by function name or first/last line, highlighted with Pygments, key lines marked): `auto_decision`, the wiring in `build_graph`, `_written` and the bound check in `understand.py`, `constraints.select`, `grounding_check`, `weather.matches`. It uses the screenshots of `user_demo.py`, so run that first; with the app running it takes fresh `/admin` screenshots itself (no agent turn). It writes `out/hikeallabout-tech.mp4` (about 8 min).

- `ai_demo.py` explains **how the AI works in one chat turn**, on its own slides (`ai_slides.html`), in two languages: `--lang en` writes `out/hikeallabout-ai-en.mp4`, `--lang de` writes `out/hikeallabout-ai-de.mp4` (each about 7–8 min). The request and the server-sent `ChatEvent`s, the LangGraph graph and its routes, structured output (`RawRequest` → JSON Schema → model JSON → Pydantic), the number check in `resolve`, the search the graph calls itself, real tool calling in `react` (`TOOL_SPECS`, `AIMessage.tool_calls`, `ToolMessage` with `tool_call_id`, limit 8), evidence and grounding, the answer and the code's own sentences, the log line and `/admin`, and a summary of where JSON appears and who decides what. Code panels come from `code_snippets.py`; the JSON panels are shortened copies of real data, listed in the script's docstring: the Titisee turn of the user video (chat log) and a knowledge turn through the real graph with real tools and scripted model replies (the log has no knowledge turn with tool calls yet). Slides only, no running app; it needs `out/shots/admin-model.jpg` from `user_demo.py`/`tech_demo.py`. The cheat sheet for the review with the same examples: `docs/presentation/ki-ablauf.md`.

`out/` is git-ignored.

## Run

```bash
python3 -m venv /tmp/vtools && /tmp/vtools/bin/pip install edge-tts playwright mutagen imageio-ffmpeg pygments
/tmp/vtools/bin/playwright install chromium   # only if no Chromium is in ~/.cache/ms-playwright

# API and a production build of the web app (no Next.js dev badge), on free ports; Supabase must be running
cd backend && uv run uvicorn hikeall.api.app:app --port 8004
cd web && set -a && . ../.env && set +a && \
  API_INTERNAL_URL=http://127.0.0.1:8004 NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" npx next build && \
  API_INTERNAL_URL=http://127.0.0.1:8004 NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" npx next start --port 3104

/tmp/vtools/bin/python scripts/video/user_demo.py --base http://localhost:3104 --api http://localhost:8004
/tmp/vtools/bin/python scripts/video/tech_demo.py --base http://localhost:3104 --api http://localhost:8004
/tmp/vtools/bin/python scripts/video/ai_demo.py --lang en   # slides only, no app needed
/tmp/vtools/bin/python scripts/video/ai_demo.py --lang de
```

The Docker stack works too: `--base http://localhost:3000 --api http://localhost:8000`.

Needs the local admin (`make admin-user`, sign-in "admin" / "admin" in a local setup) and the Black Forest data. Each user-demo run makes six real chat turns with `openai/gpt-4o-mini` (about $0.0004 each, so about $0.003 per run; the backend shows the exact cost). The search and the plan it saves are deleted again after the recording (only entries that did not exist before the run). The admin page shows the searches of the chat log the API writes (`data/logs/chat.jsonl` of the checkout the API runs from); for a tidy list, run the API from a checkout whose log holds only demo searches.

Narration is cached per segment in `out/work-*/voice/`, so only changed text is synthesised again.

## Notes

- **Counts:** the numbers on the data and quality slides come from `COUNTS` in `tech_demo.py` (README "Daten und Lizenzen", Black Forest, 2026-10-31). After the import of Lake Constance and the Palatinate Forest, update `COUNTS` and the narration of `t04`–`t06` from the README, and re-record both videos.
- **Agent wait:** any part of an agent turn that outlasts the narration is cut from the video (`Screencast.wait_cut`).
- **Frames:** recorded with the Chrome DevTools screencast and encoded to 30 fps H.264 with ffmpeg. The app is rendered at 1536 × 864 CSS pixels with a device scale factor of 1.25, so its text is readable at 1920 × 1080; Chromium needs `--force-device-scale-factor` for the screencast to deliver full-resolution frames. A drawn dot stands in for the mouse pointer, because screencasts don't show the real one; it is hidden for the screenshots.
- **New conversation:** the chat lives in the tab's sessionStorage (one thread per tab). Before the Feldberg request the script clears it and reloads, so that request does not inherit the weather wish and the ascent limit of the Titisee conversation.
- **Slide timing (`ai_slides.html`):** build-in delays are fractions of the segment's narration (`--f`), so one slide file fits both languages; `go(id, seconds)` sets the duration. Each slide shrinks its code and JSON panels to one font size that fits (`fillCode`). Preview a slide in a browser with `ai_slides.html?lang=de#a07` (panels stay empty without the script).
- **Real answers vary:** the model's wording changes from run to run; tours, chips, cards and numbers come from the code and the data. The narration only describes what the code decides.
