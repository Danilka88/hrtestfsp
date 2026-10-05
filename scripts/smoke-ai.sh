#!/usr/bin/env bash
# Сквозная проверка ИИ-функций: состояние модели, черновики, разбор профиля, эмбеддинги.
# Ключевое, что проверяется: при недоступной модели эндпоинты всё равно отвечают
# и помечают ответ degraded=true (демо-данные), не ломая основной сценарий.
#
# Использование: bash scripts/smoke-ai.sh [base_url]
set -uo pipefail

BASE="${1:-http://localhost:8000}"
JSON="Content-Type: application/json"
STAMP=$(date +%s)
EMP_EMAIL="hr.ai.$STAMP@example.com"
CAND_EMAIL="cand.ai.$STAMP@example.com"
PASSWORD="secret12345"
FAILED=0

jqv() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null; }

register_and_login() {
  local email="$1" role="$2"
  local payload reg token login
  payload=$(printf '{"email":"%s","password":"%s","role":"%s","consent_pdn":true}' "$email" "$PASSWORD" "$role")
  reg=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "$JSON" -d "$payload")
  token=$(printf '%s' "$reg" | jqv "['verification_token']")
  if [ -n "$token" ] && [ "$token" != "None" ]; then
    curl -s -o /dev/null -X POST "$BASE/api/v1/auth/verify-email" -H "$JSON" -d "{\"token\":\"$token\"}"
  fi
  login=$(printf '{"email":"%s","password":"%s"}' "$email" "$PASSWORD")
  curl -s -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$login" | jqv "['access_token']"
}

# Вызов ИИ-эндпоинта: печатает источник, задержку и признак деградации.
call_ai() {
  local label="$1" method="$2" path="$3" token="$4" body="${5:-}"
  local started finished out
  started=$(date +%s%N 2>/dev/null || date +%s)
  if [ "$method" = "GET" ]; then
    out=$(curl -s -X GET "$BASE/api/v1$path" -H "Authorization: Bearer $token")
  else
    out=$(curl -s -X POST "$BASE/api/v1$path" -H "$JSON" -H "Authorization: Bearer $token" -d "$body")
  fi
  finished=$(date +%s%N 2>/dev/null || date +%s)
  local ms=$(( (finished - started) / 1000000 ))

  local provider degraded note
  provider=$(printf '%s' "$out" | jqv "['provider']")
  degraded=$(printf '%s' "$out" | jqv "['degraded']")
  note=$(printf '%s' "$out" | jqv "['note']")

  if [ -z "$provider" ]; then
    echo "  [ОШИБКА] $label — нет ответа: $(printf '%s' "$out" | head -c 200)"
    FAILED=1
    return
  fi
  local source_text="модель"
  [ "$degraded" = "True" ] && source_text="ДЕМО-ДАННЫЕ"
  echo "  [ok] $label: источник=$provider ($source_text), ${ms} мс${note:+ — $note}"
}

echo "== подготовка: работодатель и кандидат =="
EMP=$(register_and_login "$EMP_EMAIL" employer)
CAND=$(register_and_login "$CAND_EMAIL" candidate)
[ -n "$EMP" ] && [ -n "$CAND" ] || { echo "ОШИБКА: не получены токены"; exit 1; }
echo "готово"

echo
echo "== состояние ИИ-слоя =="
curl -s -X GET "$BASE/api/v1/ai/status" -H "Authorization: Bearer $EMP" |
  python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"  провайдер: {d['provider']} | модель: {d.get('model') or '—'}\")
print(f\"  доступна: {d['available']} | деградация: {d['degraded']}\")
print(f\"  подсказка: {d['hint']}\")
" 2>/dev/null || { echo "  [ОШИБКА] /ai/status"; FAILED=1; }

echo
echo "== ИИ-функции работодателя =="
call_ai "черновик потребности" POST "/ai/need/draft" "$EMP" \
  '{"brief":"Нужен backend-разработчик на Python, FastAPI, PostgreSQL и Docker, грейд middle"}'
call_ai "заготовка задания" POST "/ai/task/draft" "$EMP" \
  '{"need_title":"Backend-разработчик","stack":["Python","PostgreSQL"],"grade":"middle"}'
call_ai "черновик приглашения" POST "/ai/invitation/draft" "$EMP" \
  '{"company":"ООО «Тестовая Компания»","candidate_grade":"middle","stack":["Python","Docker"],"salary_from":250000,"salary_to":320000,"role_title":"Backend-разработчик"}'

echo
echo "== ИИ-функции кандидата =="
call_ai "разбор профиля" POST "/ai/profile/analyze" "$CAND" \
  '{"text":"Меня зовут Иван Петров, работаю backend-разработчиком 5 лет. Пишу на Python, использую FastAPI, PostgreSQL, Docker и Redis. В команде отвечал за интеграции."}'
call_ai "сопроводительное письмо" POST "/ai/cover-letter" "$CAND" \
  '{"vacancy_title":"Backend-разработчик","company":"ООО «Тестовая Компания»","required_stack":["Python","FastAPI","Docker"],"candidate_stack":["Python","PostgreSQL","Docker"],"candidate_grade":"middle"}'

echo
echo "== семантическое сопоставление (эмбеддинги) =="
call_ai "косинус потребность↔профили" POST "/ai/semantic/scores" "$EMP" \
  '{"need_text":"Backend-разработчик Python FastAPI PostgreSQL","candidate_texts":["Python FastAPI PostgreSQL разработчик","Дизайнер интерфейсов Figma"]}'
curl -s -X POST "$BASE/api/v1/ai/semantic/scores" -H "$JSON" -H "Authorization: Bearer $EMP" \
  -d '{"need_text":"Backend-разработчик Python FastAPI PostgreSQL","candidate_texts":["Python FastAPI PostgreSQL разработчик","Дизайнер интерфейсов Figma"]}' |
  python3 -c "
import sys, json
d = json.load(sys.stdin)['data']
if d.get('scores'):
    print(f\"  метод: {d['method']} | первый (близкий): {d['scores'][0]} | второй (далёкий): {d['scores'][1]}\")
    print('  порядок корректен:' , 'да' if d['scores'][0] > d['scores'][1] else 'НЕТ')
else:
    print('  [ОШИБКА] нет оценок')
" 2>/dev/null

echo
if [ "$FAILED" -eq 0 ]; then
  echo "== OK: ИИ-функции отвечают =="
else
  echo "== ЕСТЬ ОШИБКИ =="
fi
exit "$FAILED"
