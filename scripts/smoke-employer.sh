#!/usr/bin/env bash
# Сквозная проверка кабинета работодателя: потребность → подборка → уточнение → поиск.
# Перед запуском полезно наполнить банк: docker compose exec -T backend python scripts/seed_demo.py
# Использование: bash scripts/smoke-employer.sh [base_url]
set -uo pipefail

BASE="${1:-http://localhost:8000}"
EMAIL="hr.$(date +%s)@example.com"
PASSWORD="secret12345"
JSON="Content-Type: application/json"

REG_PAYLOAD=$(printf '{"email":"%s","password":"%s","role":"employer","consent_pdn":true}' "$EMAIL" "$PASSWORD")
LOGIN_PAYLOAD=$(printf '{"email":"%s","password":"%s"}' "$EMAIL" "$PASSWORD")

jqv() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null; }

echo "== 1. регистрация работодателя и вход =="
REG=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "$JSON" -d "$REG_PAYLOAD")
TOKEN=$(printf '%s' "$REG" | jqv "['verification_token']")
curl -s -o /dev/null -X POST "$BASE/api/v1/auth/verify-email" -H "$JSON" -d "{\"token\":\"$TOKEN\"}"
ACCESS=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$LOGIN_PAYLOAD" | jqv "['access_token']")
[ -n "$ACCESS" ] || { echo "ОШИБКА: нет access_token"; exit 1; }
echo "получен access-токен"

echo
echo "== 2. профиль компании =="
curl -s -X PUT "$BASE/api/v1/employers/me/profile" -H "$JSON" -H "Authorization: Bearer $ACCESS" \
  -d '{"company_name":"ООО «Смоук Тест»","description":"Проверка подборки","industry":"it","contact_email":"hr@smoke.ru"}'
echo

echo
echo "== 3-6. потребность → подборка → уточнение → поиск =="
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
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


status, selection = call("POST", "/api/v1/employers/me/needs", {
    "title": "Backend-разработчик (Python)",
    "description": "Нужен человек в команду платежей",
    "specialization_code": "backend",
    "grade": "middle",
    "stack": ["Python", "PostgreSQL", "Docker"],
    "salary_from": 250000,
    "salary_to": 350000,
})
if status != 200:
    print("ОШИБКА создания подборки:", status, selection)
    sys.exit(1)

print(f"подборка {selection['id'][:8]}… | рубрика {selection['rubric_version']} | "
      f"рекомендованные категории: {selection['recommended_categories']}")
print(f"кандидатов: {len(selection['candidates'])}")
print()

for card in selection["candidates"][:3]:
    print(f"  #{card['rank']} {card['reference']} | {card['specialization']} / {card['grade']} "
          f"| балл {card['score']}")
    print(f"      стек: {', '.join(card['stack']) or '—'} | достижений ФСП: {card['fsp_achievements']}")
    print(f"      контакты видны: {card['contacts_visible']}")
    for reason in card["reasons"]:
        print(f"      · [{reason['code']}] {reason['text']} (вклад {reason['contribution']})")
    if card["missing"]:
        print(f"      ! нет данных: {', '.join(card['missing'])}")
    print()

blob = json.dumps(selection, ensure_ascii=False)
print(f"контакты в выдаче: email={'@demo.ru' in blob} phone={'+7 900' in blob}")

# уточнение запроса: прежняя подборка должна сохраниться
first_id = selection["id"]
status, refined = call("POST", f"/api/v1/employers/me/selections/{first_id}/refine"
                       "?stack=Python&stack=Kubernetes&stack=Redis", None)
if status != 200:
    print("ОШИБКА уточнения:", status, refined)
    sys.exit(1)
print(f"\nуточнение → новая подборка {refined['id'][:8]}… (родитель {refined['parent_selection_id'][:8]}…)")
print(f"кандидатов в уточнённой: {len(refined['candidates'])}")

status, previous = call("GET", f"/api/v1/employers/me/selections/{first_id}")
print(f"прежняя подборка доступна: HTTP {status}, кандидатов {len(previous['candidates'])}")

status, listing = call("GET", "/api/v1/employers/me/selections")
print(f"всего подборок у работодателя: {len(listing)}")

# поиск по банку
status, found = call("GET", "/api/v1/employers/me/search?has_fsp=true&limit=10")
print(f"\nпоиск с подтверждёнными достижениями ФСП: всего {found['total']}")
for card in found["candidates"][:3]:
    print(f"  {card['reference']} | {card['specialization']}/{card['grade']} "
          f"| ФСП: {card['fsp_achievements']}")

status, by_grade = call("GET", "/api/v1/employers/me/search?grade=senior&limit=10")
print(f"поиск по грейду senior: всего {by_grade['total']}")

status, bank = call("GET", "/api/v1/employers/me/search?limit=100")
print(f"весь банк кандидатов: {bank['total']}")
blob = json.dumps(bank, ensure_ascii=False)
print(f"утечка контактов в поиске: email={'@demo.ru' in blob} phone={'+7 900' in blob}")
PY

echo
echo "== готово =="
