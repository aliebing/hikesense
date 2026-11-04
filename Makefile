.PHONY: test lint up down import scan knowledge tags smoke smoke-user admin-secrets users-migrate eval osm-extract places groups

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
	cd backend && uv run hikesense import-trails
	cd backend && uv run hikesense import-day-hikes
	cd backend && uv run hikesense import-shares
	cd backend && uv run hikesense import-photos

scan:
	cd backend && uv run hikesense scan-day-hikes

# Wissensindex (Wikipedia/Wikivoyage + eigene Texte); lädt beim ersten Lauf das Embedding-Modell.
knowledge:
	cd backend && uv run hikesense build-knowledge

# Merkmal- und Belag-Tags je Tour neu berechnen.
tags:
	cd backend && uv run hikesense build-tags

# Durchstich gegen das echte Modell (OPENROUTER_API_KEY in .env; kostet wenige Cent).
# Meldet sich als smoke@hikesense.local an (vorher einmal `make smoke-user`).
smoke:
	cd backend && uv run hikesense smoke

# Eval-Testsatz (data/eval/cases.yaml) gegen das echte Modell; Wetter aus data/eval/weather.json,
# festes „heute“ 2026-11-02. Ergebnisse und Bericht unter docs/evaluation/. Braucht `make smoke-user`.
eval:
	cd backend && uv run hikesense eval

# Testkonto smoke@hikesense.local in der lokalen Supabase-Auth (Passwort: HIKESENSE_SMOKE_PASSWORD).
users-migrate:
	cd backend && uv run hikesense users-migrate

smoke-user:
	cd backend && uv run hikesense smoke-user

# Backend-Anmeldung (/backend, Name „admin“): fragt ein Passwort und gibt Hash und
# Sitzungsgeheimnis zum Eintragen in .env aus. Schreibt nichts in die Datenbank.
admin-secrets:
	cd backend && uv run hikesense admin-secrets

# Geofabrik-Extrakte für alle Regionen (ODbL, zusammen ~2 GB): Baden-Württemberg (Schwarzwald,
# Bodensee DE, Rand der Pfalz-Box), Rheinland-Pfalz, Schwaben (Lindau), Schweiz, Österreich.
# FORCE=1 lädt neu. Welche Region welche Extrakte braucht: `extracts` in backend/src/hikesense/regions.py.
OSM_DIR = data/osm
OSM_EXTRACTS = germany/baden-wuerttemberg germany/rheinland-pfalz germany/bayern/schwaben switzerland austria
osm-extract:
	mkdir -p $(OSM_DIR)
	for e in $(OSM_EXTRACTS); do f=$(OSM_DIR)/$$(basename $$e)-latest.osm.pbf; \
	  [ -f $$f ] && [ -z "$(FORCE)" ] || { curl -L -f -o $$f.part https://download.geofabrik.de/europe/$$e-latest.osm.pbf && mv $$f.part $$f; } || exit 1; \
	done

# Orte, POIs und Unterkünfte aus den lokalen Extrakten (statt Overpass), danach Tags neu berechnen.
places: osm-extract
	cd backend && uv run hikesense import-places --pbf-dir $(OSM_DIR)
	cd backend && uv run hikesense import-lodgings --pbf-dir $(OSM_DIR)
	cd backend && uv run hikesense build-tags

# Kuratierte Gruppenliste (data/curated/groups.csv) in die DB.
groups:
	cd backend && uv run hikesense import-groups
