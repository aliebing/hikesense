.PHONY: test lint up down import scan knowledge tags smoke smoke-user osm-extract places groups

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
import:
	cd backend && uv run hikeall import-trails
	cd backend && uv run hikeall import-day-hikes
	cd backend && uv run hikeall import-shares
	cd backend && uv run hikeall import-lodgings
	cd backend && uv run hikeall import-places
	cd backend && uv run hikeall build-tags
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

# Testkonto smoke@hikeall.local in der lokalen Supabase-Auth (Passwort: HIKEALL_SMOKE_PASSWORD).
smoke-user:
	cd backend && uv run hikeall smoke-user

# Geofabrik-Extrakt Baden-Württemberg (ODbL, ~700 MB); FORCE=1 lädt neu.
OSM_PBF = data/osm/baden-wuerttemberg-latest.osm.pbf
osm-extract:
	mkdir -p data/osm
	[ -f $(OSM_PBF) ] && [ -z "$(FORCE)" ] || { curl -L -f -o $(OSM_PBF).part https://download.geofabrik.de/europe/germany/baden-wuerttemberg-latest.osm.pbf && mv $(OSM_PBF).part $(OSM_PBF); }

# Orte und POIs aus dem lokalen Extrakt (statt Overpass), danach Tags neu berechnen.
places: osm-extract
	cd backend && uv run hikeall import-places --pbf $(OSM_PBF)
	cd backend && uv run hikeall build-tags

# Kuratierte Gruppenliste (data/curated/groups.csv) in die DB.
groups:
	cd backend && uv run hikeall import-groups
