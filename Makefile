.PHONY: test lint up down import scan knowledge tags smoke smoke-user admin-user eval osm-extract places groups

test:
	cd backend && uv run pytest -q
	cd web && npm test

lint:
	cd backend && uv run ruff check
	cd web && npm run lint

up:
	npx supabase start
	docker compose up -d --build --renew-anon-volumes

down:
	docker compose down
	npx supabase stop

# Long-running (public APIs). Scanning + curation of day hikes is manual: see `make scan`.
# Places, POIs and lodgings come from the local extracts: `make places` after this.
import:
	cd backend && uv run hikeall import-trails
	cd backend && uv run hikeall import-day-hikes
	cd backend && uv run hikeall import-shares
	cd backend && uv run hikeall import-photos

scan:
	cd backend && uv run hikeall scan-day-hikes

# Wissensindex (Wikipedia/Wikivoyage + eigene Texte); lädt beim ersten Lauf das Embedding-Modell.
knowledge:
	cd backend && uv run hikeall build-knowledge

# Merkmal- und Belag-Tags je Tour neu berechnen.
tags:
	cd backend && uv run hikeall build-tags

# Durchstich gegen das echte Modell (OPENROUTER_API_KEY in .env; kostet wenige Cent).
# Meldet sich als smoke@hikeall.local an (vorher einmal `make smoke-user`).
smoke:
	cd backend && uv run hikeall smoke

# Eval-Testsatz (data/eval/cases.yaml) gegen das echte Modell; Wetter aus data/eval/weather.json,
# festes „heute“ 2026-11-02. Ergebnisse und Bericht unter docs/evaluation/. Braucht `make smoke-user`.
eval:
	cd backend && uv run hikeall eval

# Testkonto smoke@hikeall.local in der lokalen Supabase-Auth (Passwort: HIKEALL_SMOKE_PASSWORD).
smoke-user:
	cd backend && uv run hikeall smoke-user

# Lokaler Admin (Anmeldename „admin“ = admin@hikeall.local). In .env steht nur der bcrypt-Hash
# des Passworts (HIKEALL_ADMIN_PASSWORD_HASH), nie das Passwort selbst. Setzt auch die Rolle admin
# in profiles.
admin-user:
	cd backend && uv run hikeall admin-user

# Geofabrik-Extrakte für alle Regionen (ODbL, zusammen ~2 GB): Baden-Württemberg (Schwarzwald,
# Bodensee DE, Rand der Pfalz-Box), Rheinland-Pfalz, Schwaben (Lindau), Schweiz, Österreich.
# FORCE=1 lädt neu. Welche Region welche Extrakte braucht: `extracts` in backend/src/hikeall/regions.py.
OSM_DIR = data/osm
OSM_EXTRACTS = germany/baden-wuerttemberg germany/rheinland-pfalz germany/bayern/schwaben switzerland austria
osm-extract:
	mkdir -p $(OSM_DIR)
	for e in $(OSM_EXTRACTS); do f=$(OSM_DIR)/$$(basename $$e)-latest.osm.pbf; \
	  [ -f $$f ] && [ -z "$(FORCE)" ] || { curl -L -f -o $$f.part https://download.geofabrik.de/europe/$$e-latest.osm.pbf && mv $$f.part $$f; } || exit 1; \
	done

# Orte, POIs und Unterkünfte aus den lokalen Extrakten (statt Overpass), danach Tags neu berechnen.
places: osm-extract
	cd backend && uv run hikeall import-places --pbf-dir $(OSM_DIR)
	cd backend && uv run hikeall import-lodgings --pbf-dir $(OSM_DIR)
	cd backend && uv run hikeall build-tags

# Kuratierte Gruppenliste (data/curated/groups.csv) in die DB.
groups:
	cd backend && uv run hikeall import-groups
