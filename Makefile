.PHONY: test lint up down import scan

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
