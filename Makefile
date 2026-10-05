.PHONY: help up down logs build backend-dev frontend-dev test lint fmt clean

help:
	@echo "make up            — поднять весь стек (docker compose up --build)"
	@echo "make down          — остановить стек"
	@echo "make logs          — логи всех сервисов"
	@echo "make backend-dev   — запустить API локально (uvicorn --reload)"
	@echo "make frontend-dev  — запустить SPA локально (vite)"
	@echo "make test          — тесты backend"
	@echo "make lint          — проверки кода"
	@echo "make clean         — удалить кэши"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend-dev:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && pytest -q

lint:
	cd backend && ruff check . && ruff format --check .

fmt:
	cd backend && ruff format .

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.pytest_cache backend/.ruff_cache frontend/dist
