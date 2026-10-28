.PHONY: test lint up down

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check

up:
	npx supabase start

down:
	npx supabase stop
