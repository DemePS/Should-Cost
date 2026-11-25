.PHONY: install dev test lint build clean

install: backend-install frontend-install

backend-install:
	cd backend && pip install -e ".[dev]"

frontend-install:
	cd frontend && pnpm install

dev:
	cd backend && uvicorn should_cost.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

test: backend-test frontend-test

backend-test:
	cd backend && pytest

frontend-test:
	cd frontend && pnpm test

lint: backend-lint frontend-lint

backend-lint:
	cd backend && ruff check . && mypy should_cost

frontend-lint:
	cd frontend && pnpm lint && pnpm typecheck

build: frontend-build openapi-client

frontend-build:
	cd frontend && pnpm build

openapi-client:
	cd backend && python -m should_cost.scripts.export_openapi > ../frontend/openapi.json
	cd frontend && pnpm generate-client

docker-build:
	docker build -t should-cost:local .

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} \;
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache frontend/dist frontend/node_modules
