.PHONY: help up down logs build backend-dev frontend-dev test test-cov lint fmt seed clean

# Интерпретатор и инструменты берём из окружения проекта, а не из PATH:
# так исключается подмешивание посторонних site-packages и версий.
# `env -u PYTHONPATH` безвреден там, где переменная не задана.
PY      := env -u PYTHONPATH .venv/bin/python
RUFF    := env -u PYTHONPATH .venv/bin/ruff
VULTURE := env -u PYTHONPATH .venv/bin/vulture

help:
	@echo "make up            — поднять весь стек (docker compose up -d --build)"
	@echo "make down          — остановить стек"
	@echo "make logs          — логи всех сервисов"
	@echo "make seed          — загрузить демонстрационные данные"
	@echo "make backend-dev   — запустить API локально (uvicorn --reload)"
	@echo "make frontend-dev  — запустить SPA локально (vite)"
	@echo "make test          — тесты backend"
	@echo "make test-cov      — тесты backend с отчётом о покрытии"
	@echo "make lint          — линтер, формат, поиск мёртвого кода"
	@echo "make fmt           — автоформатирование"
	@echo "make clean         — удалить кэши и артефакты сборки"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

seed:
	docker compose exec -T backend python scripts/seed_demo.py

backend-dev:
	cd backend && $(PY) -m uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && $(PY) -m pytest -q

test-cov:
	cd backend && $(PY) -m pytest -q --cov=app --cov-report=term-missing:skip-covered

lint:
	cd backend && $(RUFF) check . && $(RUFF) format --check . && $(VULTURE) app --min-confidence 80

fmt:
	cd backend && $(RUFF) format . && $(RUFF) check . --fix

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.coverage frontend/dist
