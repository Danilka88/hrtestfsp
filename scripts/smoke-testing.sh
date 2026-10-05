#!/usr/bin/env bash
# Сквозная проверка механики тестирования на запущенном API:
# опрос → сессия → адаптивные ответы → результат → категория.
# Использование: bash scripts/smoke-testing.sh [base_url]
set -uo pipefail

BASE="${1:-http://localhost:8000}"
EMAIL="test.$(date +%s)@example.com"
PASSWORD="secret12345"
JSON="Content-Type: application/json"

REG_PAYLOAD=$(printf '{"email":"%s","password":"%s","role":"candidate","consent_pdn":true}' "$EMAIL" "$PASSWORD")
LOGIN_PAYLOAD=$(printf '{"email":"%s","password":"%s"}' "$EMAIL" "$PASSWORD")

jqv() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null; }

echo "== 1. регистрация, подтверждение, вход =="
REG=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "$JSON" -d "$REG_PAYLOAD")
TOKEN=$(printf '%s' "$REG" | jqv "['verification_token']")
curl -s -o /dev/null -X POST "$BASE/api/v1/auth/verify-email" -H "$JSON" -d "{\"token\":\"$TOKEN\"}"
ACCESS=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$LOGIN_PAYLOAD" | jqv "['access_token']")
[ -n "$ACCESS" ] || { echo "ОШИБКА: нет access_token"; exit 1; }
echo "получен access-токен"

echo
echo "== 2. справочники (специализации) =="
curl -s "$BASE/api/v1/testing/specializations" | python3 -c "import sys,json;d=json.load(sys.stdin);print('специализаций:',len(d));print(', '.join(s['code'] for s in d[:8]))"

echo
echo "== 3. справочник грейдов =="
curl -s "$BASE/api/v1/testing/grades" | python3 -c "import sys,json;d=json.load(sys.stdin);print(' → '.join(g['code'] for g in d))"

echo
echo "== 4. опрос =="
curl -s -X POST "$BASE/api/v1/testing/survey" -H "$JSON" -H "Authorization: Bearer $ACCESS" \
  -d '{"industry":"it","specialization_code":"backend","answers":{"experience":"3-5 лет","preference":"api"}}'
echo

echo
echo "== 5-6. сессия теста: адаптивная выдача и результат =="
python3 - "$BASE" "$ACCESS" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base, token = sys.argv[1], sys.argv[2]
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


def call(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


status, started = call("POST", "/api/v1/testing/sessions",
                       {"specialization_code": "backend", "target_grade": "middle"})
if status != 200:
    print("ОШИБКА запуска сессии:", status, started)
    sys.exit(1)

session_id = started["session_id"]
item = started["item"]
print(f"сессия {session_id[:8]}… | первое задание: {item['question'][:70]}…")
print(f"вариантов ответа: {len(item['options'])}")

result = None
for step in range(1, 21):
    # Отвечаем первым вариантом: цель — проверить механику, а не набрать балл.
    status, body = call("POST", f"/api/v1/testing/sessions/{session_id}/answers",
                        {"item_id": item["id"], "answer_index": 0, "response_time_ms": 4200})
    if status != 200:
        print("ОШИБКА ответа:", status, body)
        sys.exit(1)
    verdict = "верно" if body["correct"] else "неверно"
    print(f"  шаг {step}: {verdict}")
    if body["finished"]:
        result = body["result"]
        break
    item = body["next_item"]

if result is None:
    print("ОШИБКА: сессия не завершилась")
    sys.exit(1)

print()
print("РЕЗУЛЬТАТ:")
for key in ("status", "items_answered", "theta", "standard_error", "converged",
            "result_grade", "current_grade", "grade_change_applied", "grade_change_reason"):
    print(f"  {key}: {result[key]}")
print(f"  warnings: {result['warnings']}")

status, again = call("POST", f"/api/v1/testing/sessions/{session_id}/answers",
                     {"item_id": item["id"], "answer_index": 0, "response_time_ms": 1000})
print(f"\nответ в завершённую сессию → HTTP {status} (ожидалось 409)")

status, category = call("GET", "/api/v1/testing/me/category")
print("\nКАТЕГОРИЯ КАНДИДАТА:")
print(f"  специализация: {category['specialization']} | грейд: {category['grade']}")
print(f"  смена грейда разрешена: {category['grade_change_allowed']}"
      f" (через {category['grade_change_available_in_days']} дн., "
      f"интервал {category['grade_change_cooldown_days']} дн.)")
print(f"  допустимые уровни теста: {category['grade_options']}")
print(f"  история грейдов: {[(h['from_grade'], h['to_grade']) for h in category['grade_history']]}")
print(f"  сессий в истории: {len(category['sessions'])}")
PY

echo
echo "== готово =="
