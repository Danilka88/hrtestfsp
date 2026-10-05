# Платформа-агрегатор ИТ-вакансий с верифицированным профилем (хакатон, MVP)

Рабочее название: **IT-Talent Match** — платформа обратного подбора.

## Что это

Веб-сервис подбора ИТ-специалистов с **обратной механикой**: соискатели
автоматически распределяются по категориям (специализация × грейд) на основе
объективно подтверждаемого профиля (опрос + тест + достижения), а **работодатель
сам** находит нужную категорию и направляет приглашение с уровнем заработной
платы. Прямой отклик кандидата — дополнительный сценарий.

## Документация

| Файл | Содержание |
|---|---|
| `docs/lean-canvas.html` | **Визуальный лэндинг проекта** (для демонстрации): исследование, механики, Lean Canvas, архитектура, критерии |
| `docs/00-research.md` | Исследование рынка и практик + Lean Canvas |
| `docs/01-architecture.md` | Функциональная и компонентная архитектура |
| `docs/02-tech-stack.md` | Технологический стек и версии |
| `docs/03-mvp-plan.md` | План MVP, демо-сценарий, критерии готовности |

## Структура репозитория

```
project/
  backend/                # FastAPI — API бизнес-логики
    app/
      api/v1/endpoints/   # HTTP-эндпоинты (health)
      core/               # конфигурация, логирование
      db/                 # сессия, declarative base
      providers/          # внешние зависимости: интерфейсы + mock-реализации
      services/           # бизнес-логика: тестирование, ранжирование, объяснимость
    alembic/              # миграции
    tests/                # pytest
  frontend/               # React + TypeScript + Vite SPA
    src/{api,pages,styles}/
  seed/                   # генераторы демонстрационных данных
  scripts/                # smoke-проверки
  docs/                   # сопроводительная документация
  docker-compose.yml
  .env.example
```

## Быстрый старт

### Вариант 1 — весь стек в Docker

```bash
cp .env.example .env
docker compose up --build
```

- SPA: http://localhost:8080
- API и Swagger: http://localhost:8000/docs

### Вариант 2 — локальный запуск

Backend (нужен Python 3.12; удобнее через `uv`):

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
env -u PYTHONPATH .venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

> `env -u PYTHONPATH` нужен, если в окружении задан `PYTHONPATH` — иначе в
> `sys.path` попадают чужие site-packages и импорты разрешаются неверно.

Frontend:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (проксирует /api на :8000)
```

Проверки:

```bash
cd backend && env -u PYTHONPATH .venv/bin/python -m pytest -q   # тесты
bash scripts/smoke-api.sh                                       # smoke-проверка API
cd frontend && npm run build                                    # сборка SPA
```

## Статус

| Этап | Состояние |
|---|---|
| 0. Каркас и инфраструктура | **готово** |
| 1. Аутентификация, роли, согласия | не начат |
| 2. Профиль кандидата | не начат |
| 3. Тестирование и категоризация | ядро заложено (адаптивная модель + тесты) |
| 4. Подбор, ранжирование, объяснимость | ядро заложено (рубрика + evidence-trail) |
| 5–8. Приглашения, доп. функционал, демо, валидация | не начато |

Что уже работает: живой API с OpenAPI и health-пробами, SPA с двумя страницами,
mock-провайдеры внешних сервисов, чистое ядро ранжирования и адаптивного
тестирования под тестами (20 тестов), docker-compose, smoke-скрипт.

