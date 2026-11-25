.PHONY: install dev test lint build clean

install: backend-install frontend-install

backend-install:
	cd backend && uv sync --extra dev

frontend-install:
	cd frontend && pnpm install

dev:
	cd backend && uv run uvicorn should_cost.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

test: backend-test frontend-test

backend-test:
	cd backend && uv run pytest

frontend-test:
	cd frontend && pnpm test

lint: backend-lint frontend-lint

backend-lint:
	cd backend && uv run ruff check . && uv run mypy should_cost

frontend-lint:
	cd frontend && pnpm lint && pnpm typecheck

build: frontend-build openapi-client

frontend-build:
	cd frontend && pnpm build

openapi-client:
	cd backend && uv run python -m should_cost.scripts.export_openapi > ../frontend/openapi.json
	cd frontend && pnpm generate-client

cli:
	cd backend && uv run python -m should_cost.cli $(ARGS)

docker-build:
	docker build -t should-cost:local .

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} \;
	rm -rf backend/.venv backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache frontend/dist frontend/node_modules
