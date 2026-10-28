.PHONY: test lint

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check
