#!/usr/bin/env bash
# Проверка запущенного стека docker compose: ожидание готовности и ключевые эндпоинты.
# Использование: bash scripts/verify-stack.sh [таймаут_сек]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TIMEOUT="${1:-480}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8080}"

echo "== состояние контейнеров =="
docker compose ps --format 'table {{.Service}}\t{{.Status}}' 2>/dev/null || docker compose ps

echo
echo "== ожидание backend $BACKEND_URL (до ${TIMEOUT}с) =="
ok=0
for _ in $(seq 1 "$TIMEOUT"); do
  if curl -sf "$BACKEND_URL/api/v1/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done

if [ "$ok" -ne 1 ]; then
  echo "ОШИБКА: backend не отвечает. Логи:"
  docker compose logs --tail=40 backend
  exit 1
fi
echo "backend отвечает"

echo
echo "== ожидание frontend $FRONTEND_URL =="
fok=0
for _ in $(seq 1 120); do
  if curl -sf "$FRONTEND_URL/" >/dev/null 2>&1; then fok=1; break; fi
  sleep 1
done
[ "$fok" = "1" ] && echo "frontend отвечает" || echo "ПРЕДУПРЕЖДЕНИЕ: frontend не отвечает"

echo
echo "--- GET / ---"
curl -s "$BACKEND_URL/"
echo
echo "--- GET /api/v1/health ---"
curl -s "$BACKEND_URL/api/v1/health"
echo
echo "--- GET /api/v1/health/ready (через фронтенд-прокси) ---"
curl -s "$FRONTEND_URL/api/v1/health/ready"
echo
echo "--- коды ответов ---"
curl -s -o /dev/null -w "SPA /            : %{http_code}\n" "$FRONTEND_URL/"
curl -s -o /dev/null -w "openapi.json     : %{http_code}\n" "$BACKEND_URL/api/v1/openapi.json"
curl -s -o /dev/null -w "docs             : %{http_code}\n" "$BACKEND_URL/docs"

echo
echo "== итоговое состояние =="
docker compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || docker compose ps
