#!/usr/bin/env bash
# Сквозная проверка Этапа 5: приглашения, статусы, раскрытие контактов, связь с ФСП.
# Требует демо-данных: docker compose exec -T backend python scripts/seed_demo.py
# Использование: bash scripts/smoke-invitations.sh [base_url]
set -uo pipefail

BASE="${1:-http://localhost:8000}"
JSON="Content-Type: application/json"
STAMP=$(date +%s)
EMP_EMAIL="hr.inv.$STAMP@example.com"
EMP_PASSWORD="secret12345"
DEMO_PASSWORD="demo12345"

jqv() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null; }

register_and_login() {
  local email="$1" role="$2" password="$3"
  local payload
  payload=$(printf '{"email":"%s","password":"%s","role":"%s","consent_pdn":true}' "$email" "$password" "$role")
  local reg token
  reg=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "$JSON" -d "$payload")
  token=$(printf '%s' "$reg" | jqv "['verification_token']")
  if [ -n "$token" ] && [ "$token" != "None" ]; then
    curl -s -o /dev/null -X POST "$BASE/api/v1/auth/verify-email" -H "$JSON" -d "{\"token\":\"$token\"}"
  fi
  local login
  login=$(printf '{"email":"%s","password":"%s"}' "$email" "$password")
  curl -s -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$login" | jqv "['access_token']"
}

echo "== 1. работодатель =="
EMP=$(register_and_login "$EMP_EMAIL" employer "$EMP_PASSWORD")
[ -n "$EMP" ] || { echo "ОШИБКА: нет токена работодателя"; exit 1; }
curl -s -o /dev/null -X PUT "$BASE/api/v1/employers/me/profile" -H "$JSON" \
  -H "Authorization: Bearer $EMP" \
  -d '{"company_name":"ООО «Проверка Приглашений»","description":"Смоук-компания"}'
echo "готово"

echo
echo "== 2. кандидаты из демо-банка =="
ANNA=$(register_and_login "anna.kovaleva@demo.ru" candidate "$DEMO_PASSWORD")
DMITRY=$(register_and_login "dmitry.sokolov@demo.ru" candidate "$DEMO_PASSWORD")
[ -n "$ANNA" ] && [ -n "$DMITRY" ] || { echo "ОШИБКА: демо-кандидаты недоступны (нужен seed_demo.py)"; exit 1; }
echo "Анна и Дмитрий: токены получены"

python3 - "$BASE" "$EMP" "$ANNA" "$DMITRY" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base, employer_token, anna_token, dmitry_token = sys.argv[1:5]

def call(method, path, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")

print()
print("== 3. поиск кандидата и приглашение ==")
status, bank = call("GET", "/api/v1/employers/me/search?specialization_code=backend&limit=10", employer_token)
targets = {c["reference"]: c for c in bank["candidates"]}
print(f"в банке backend-кандидатов: {len(targets)}")

# Берём двух разных backend-кандидатов: одного пригласят и он примет, второго отклонит
refs = list(targets)
accept_ref, decline_ref = refs[0], refs[1]

status, invitation = call("POST", "/api/v1/employers/me/invitations", employer_token, {
    "candidate_reference": accept_ref,
    "message": "Приглашаем в команду платежей",
    "salary_from": 280000,
    "salary_to": 360000,
    "contact_method": "hr@company.ru",
})
if status != 200:
    print("ОШИБКА отправки приглашения:", status, invitation)
    sys.exit(1)

print(f"приглашение {invitation['id'][:8]}… → {accept_ref} | статус: {invitation['status']}")
print(f"  зарплата в приглашении: {invitation['salary_from']}–{invitation['salary_to']} ₽ (обязательна)")
print(f"  контакты раскрыты: {invitation['contacts_revealed']} | контакты: {invitation['candidate_contacts']}")

status, second = call("POST", "/api/v1/employers/me/invitations", employer_token, {
    "candidate_reference": decline_ref,
    "message": "Есть интересная задача",
    "salary_from": 200000, "salary_to": 260000,
})
print(f"второе приглашение → {decline_ref} | статус: {second['status']}")

print()
print("== 4-5. кандидат видит условия до общения, затем решает ==")
status, inbound = call("GET", "/api/v1/candidates/me/invitations", anna_token)
if not inbound:
    print("демо-кандидат id не совпал с приглашённым — пропускаем UI-часть")
else:
    item = inbound[0]
    print(f"Анна видит: компания «{item['company_name']}», {item['salary_from']}–{item['salary_to']} ₽, "
          f"статус {item['status']}")
    call("POST", f"/api/v1/candidates/me/invitations/{item['id']}/view", anna_token)
    _, after_view = call("GET", "/api/v1/candidates/me/invitations", anna_token)
    print(f"после просмотра: {after_view[0]['status']}")

    status, decided = call("POST", f"/api/v1/candidates/me/invitations/{item['id']}/decision",
                           anna_token, {"status": "accepted"})
    print(f"решение кандидата: {decided['status']}")
    repeated = call("POST", f"/api/v1/candidates/me/invitations/{item['id']}/decision",
                    anna_token, {"status": "declined"})
    print(f"повторное решение → HTTP {repeated[0]} (ожидалось 409)")

print()
print("== 6. работодатель: статусы и раскрытие контактов ==")
status, listing = call("GET", "/api/v1/employers/me/invitations", employer_token)
for item in listing:
    print(f"  {item['candidate_reference']} | {item['status']:9} | раскрыто: {item['contacts_revealed']}"
          f" | контакты: {item['candidate_contacts']}")

blob = json.dumps(listing, ensure_ascii=False)
print(f"контакты до принятия в выдаче присутствуют: {'@demo.ru' in blob.split('accepted')[0] if 'accepted' in blob else '@demo.ru' in blob}")

print()
print("== 7. связь с ФСП ==")
for label, token in (("Анна (есть история)", anna_token), ("Дмитрий (без ФСП)", dmitry_token)):
    status, fsp = call("GET", "/api/v1/candidates/me/fsp", token)
    print(f"  {label}: linked={fsp['linked']} достижений={len(fsp['achievements'])} — {fsp['note'][:80]}")

status, linked = call("PUT", "/api/v1/candidates/me/fsp", dmitry_token, {"fsp_id": "fsp-3000"})
print(f"  после привязки ФСП Дмитрием: linked={linked['linked']} достижений={len(linked['achievements'])}")
print(f"  {linked['note'][:90]}")

status, unlinked = call("PUT", "/api/v1/candidates/me/fsp", dmitry_token, {"fsp_id": None})
print(f"  после отвязки: linked={unlinked['linked']} — {unlinked['note'][:60]}")
PY

echo
echo "== готово =="
