.PHONY: test lint up down import scan

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check

up:
	npx supabase start
	docker compose up -d --build

down:
	docker compose down
	npx supabase stop

# Long-running (public APIs). Scanning + curation of day hikes is manual: see `make scan`.
import:
	cd backend && uv run hikeall import-trails
	cd backend && uv run hikeall import-day-hikes
	cd backend && uv run hikeall import-lodgings
	cd backend && uv run hikeall import-photos

scan:
	cd backend && uv run hikeall scan-day-hikes
