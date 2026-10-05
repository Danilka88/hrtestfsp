#!/usr/bin/env bash
# Чистая демонстрация: пересобирает стек с нуля и загружает демо-данные.
#
# Зачем: сквозные проверки (scripts/smoke-*.sh) работают на том же стеке и той же
# базе, что и демонстрация, поэтому после них в кабинетах остаются тестовые
# компании, вакансии и задания. Перед показом запустите этот скрипт — вернётся
# ровно то состояние, которое описано в документации.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="http://localhost:8000"

echo "== остановка стенда и удаление данных =="
docker compose down -v

echo
echo "== сборка и запуск =="
docker compose up -d --build

echo
echo "== ожидание готовности API =="
ready=0
for _ in $(seq 1 60); do
  status=$(curl -s --max-time 3 "$BASE/api/v1/health/ready" || true)
  case "$status" in
    *'"status":"ok"'*) ready=1; break ;;
  esac
  sleep 2
done
if [ "$ready" != "1" ]; then
  echo "API не поднялся за отведённое время. Посмотрите логи: docker compose logs backend"
  exit 1
fi
echo "API отвечает"

echo
echo "== демонстрационные данные =="
docker compose exec -T backend python scripts/seed_demo.py

cat <<'DONE'

Готово. Чистое состояние для демонстрации:
  платформа:    http://localhost:8080
  документация: http://localhost:8000/docs
  работодатель: hr@fintech-demo.ru / demo12345   (и hr@digital-demo.ru)
  кандидат:     anna.kovaleva@demo.ru / demo12345
DONE
