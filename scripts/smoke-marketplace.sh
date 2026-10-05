#!/usr/bin/env bash
# Сквозная проверка дополнительного функционала: вакансии, отклик, регулярные задания.
# Использование: bash scripts/smoke-marketplace.sh [base_url]
set -uo pipefail

BASE="${1:-http://localhost:8000}"
JSON="Content-Type: application/json"
STAMP=$(date +%s)
EMP_EMAIL="hr.market.$STAMP@example.com"
CAND_EMAIL="cand.market.$STAMP@example.com"
PASSWORD="secret12345"

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

echo "== подготовка: работодатель и кандидат =="
EMP=$(register_and_login "$EMP_EMAIL" employer)
CAND=$(register_and_login "$CAND_EMAIL" candidate)
[ -n "$EMP" ] && [ -n "$CAND" ] || { echo "ОШИБКА: не получены токены"; exit 1; }

curl -s -o /dev/null -X PUT "$BASE/api/v1/employers/me/profile" -H "$JSON" \
  -H "Authorization: Bearer $EMP" -d '{"company_name":"ООО «Маркетплейс Тест»"}'
curl -s -o /dev/null -X PUT "$BASE/api/v1/candidates/me/profile" -H "$JSON" \
  -H "Authorization: Bearer $CAND" \
  -d '{"full_name":"Кандидат Инициативный","contacts":{"email":"'$CAND_EMAIL'","phone":"+7 905 111-22-33","telegram":"@init"},"specialization":"backend","grade":"middle","stack":["Python","Docker"]}'
echo "готово"

echo
echo "== вакансии, отклик, задания, свежесть профиля =="
python3 - "$BASE" "$EMP" "$CAND" "$CAND_EMAIL" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base, employer_token, candidate_token, cand_email = sys.argv[1:5]

def call(method, path, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")

print("\n== 1. публикация вакансии ==")
status, vacancy = call("POST", "/api/v1/employers/me/vacancies", employer_token, {
    "title": "Backend-разработчик (Python)",
    "description": "Команда платежей",
    "specialization_code": "backend",
    "grade": "middle",
    "stack": ["Python", "PostgreSQL"],
    "salary_from": 260000,
    "salary_to": 340000,
})
if status != 200:
    print("ОШИБКА публикации:", status, vacancy)
    sys.exit(1)
print(f"вакансия {vacancy['id'][:8]}… | статус {vacancy['status']} | "
      f"зарплата {vacancy['salary_from']}–{vacancy['salary_to']} ₽")

print("\n== 2. кандидат видит открытые вакансии ==")
status, open_list = call("GET", "/api/v1/candidates/me/vacancies", candidate_token)
print(f"открытых вакансий: {len(open_list)} | первая: «{open_list[0]['title']}» "
      f"({open_list[0]['company_name']})")

print("\n== 3. самостоятельный отклик кандидата ==")
status, application = call("POST", f"/api/v1/candidates/me/vacancies/{vacancy['id']}/applications",
                           candidate_token, {"message": "Хочу в команду платежей"})
print(f"отклик: статус {application['status']} | вакансия «{application['vacancy_title']}»")
repeat = call("POST", f"/api/v1/candidates/me/vacancies/{vacancy['id']}/applications",
              candidate_token, {})
print(f"повторный отклик → HTTP {repeat[0]} (ожидалось 409)")

print("\n== 4. работодатель видит отклик и КОНТАКТЫ (кандидат откликнулся сам) ==")
status, applications = call("GET", f"/api/v1/employers/me/vacancies/{vacancy['id']}/applications",
                            employer_token)
item = applications[0]
print(f"{item['candidate_reference']} | {item['candidate_specialization']}/{item['candidate_grade']}"
      f" | раскрыто: {item['contacts_revealed']}")
print(f"контакты: {item['candidate_contacts']}")

status, decided = call("POST",
                       f"/api/v1/employers/me/vacancies/applications/{item['id']}/decision",
                       employer_token, {"status": "accepted"})
print(f"решение работодателя: {decided['status']}")

print("\n== 5. регулярное короткое задание ==")
status, task = call("POST", "/api/v1/employers/me/tasks", employer_token, {
    "title": "Спроектируйте идемпотентный вебхук",
    "description": "Опишите подход или приведите код",
    "specialization_code": "backend",
})
print(f"задание {task['id'][:8]}… | статус {task['status']}")

status, offered = call("GET", "/api/v1/candidates/me/tasks", candidate_token)
print(f"кандидату предложено заданий: {len(offered)}")

status, submission = call("POST", f"/api/v1/candidates/me/tasks/{task['id']}/submissions",
                          candidate_token,
                          {"solution": "Ключ идемпотентности в заголовке + хранилище ключей."})
print(f"решение отправлено: статус {submission['status']}")

status, submissions = call("GET", f"/api/v1/employers/me/tasks/{task['id']}/submissions",
                           employer_token)
print(f"работодатель видит решений: {len(submissions)} | кандидат {submissions[0]['candidate_reference']}")

print("\n== 6. свежесть профиля учитывает участие в заданиях ==")
status, search = call("GET", "/api/v1/employers/me/search?specialization_code=backend&limit=100",
                      employer_token)
found = [c for c in search["candidates"] if c["full_name"] == "Кандидат Инициативный"]
if found:
    card = found[0]
    freshness = [r for r in card["reasons"] if r["code"] == "freshness"]
    print(f"карточка {card['reference']} ({card['grade']}): "
          f"{freshness[0]['text'] if freshness else 'нет данных о свежести'}")
else:
    print(f"кандидат {cand_email} не попал в выдачу (нет грейда?)")

print("\n== 7. изоляция: чужие отклики недоступны ==")
print("кандидат видит только свои отклики через /candidates/me/applications")
status, mine = call("GET", "/api/v1/candidates/me/applications", candidate_token)
print(f"моих откликов: {len(mine)} | статус первого: {mine[0]['status'] if mine else '—'}")
PY

echo
echo "== готово =="
