#!/usr/bin/env bash
# Smoke-проверка API: поднимает сервер, дёргает ключевые эндпоинты, останавливает.
# Использование: bash scripts/smoke-api.sh [порт]
set -uo pipefail

PORT="${1:-8000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
LOG="${TMPDIR:-/tmp}/it-talent-match-uvicorn.log"
BASE="http://127.0.0.1:${PORT}"

cd "$BACKEND" || exit 1

# Изоляция от родительского PYTHONPATH (иначе подмешиваются чужие site-packages)
env -u PYTHONPATH .venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port "$PORT" > "$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT

echo "== ожидание готовности API на порту $PORT =="
ok=0
for _ in $(seq 1 60); do
  if curl -sf "$BASE/api/v1/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 0.5
done

if [ "$ok" -ne 1 ]; then
  echo "ОШИБКА: API не поднялся. Лог:"; tail -20 "$LOG"; exit 1
fi

echo "--- GET / ---"
curl -s "$BASE/"
echo
echo "--- GET /api/v1/health ---"
curl -s "$BASE/api/v1/health"
echo
echo "--- GET /api/v1/health/ready ---"
curl -s "$BASE/api/v1/health/ready"
echo
echo "--- коды ответов ---"
curl -s -o /dev/null -w "openapi.json: %{http_code}\n" "$BASE/api/v1/openapi.json"
curl -s -o /dev/null -w "docs:         %{http_code}\n" "$BASE/docs"
echo "--- фрагмент OpenAPI ---"
curl -s "$BASE/api/v1/openapi.json" | head -c 180
echo
echo "== OK: API отвечает =="
