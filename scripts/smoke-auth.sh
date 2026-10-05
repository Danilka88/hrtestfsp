#!/usr/bin/env bash
# Сквозная проверка сценария аутентификации на запущенном API.
# Использование: bash scripts/smoke-auth.sh [base_url]
set -uo pipefail

BASE="${1:-http://localhost:8000}"
EMAIL="smoke.$(date +%s)@example.com"
PASSWORD="secret12345"
JSON="Content-Type: application/json"

REG_PAYLOAD=$(printf '{"email":"%s","password":"%s","role":"candidate","consent_pdn":true}' "$EMAIL" "$PASSWORD")
LOGIN_PAYLOAD=$(printf '{"email":"%s","password":"%s"}' "$EMAIL" "$PASSWORD")

jqv() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "== 1. регистрация ($EMAIL) =="
REG=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "$JSON" -d "$REG_PAYLOAD")
echo "$REG"
TOKEN=$(printf '%s' "$REG" | jqv "['verification_token']")
if [ -z "$TOKEN" ] || [ "$TOKEN" = "None" ]; then
  echo "ОШИБКА: нет verification_token (EXPOSE_DEV_TOKENS выключен?)"; exit 1
fi

echo
echo "== 2. вход до подтверждения (ожидаем 403) =="
echo "HTTP $(code -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$LOGIN_PAYLOAD")"

echo
echo "== 3. подтверждение email =="
VERIFY_PAYLOAD=$(printf '{"token":"%s"}' "$TOKEN")
curl -s -X POST "$BASE/api/v1/auth/verify-email" -H "$JSON" -d "$VERIFY_PAYLOAD"
echo

echo
echo "== 4. вход =="
LOGIN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$LOGIN_PAYLOAD")
echo "$LOGIN"
ACCESS=$(printf '%s' "$LOGIN" | jqv "['access_token']")
REFRESH=$(printf '%s' "$LOGIN" | jqv "['refresh_token']")
[ -n "$ACCESS" ] || { echo "ОШИБКА: не получен access_token"; exit 1; }

echo
echo "== 5. GET /me с токеном =="
curl -s "$BASE/api/v1/auth/me" -H "Authorization: Bearer $ACCESS"
echo

echo
echo "== 6. GET /me без токена (ожидаем 401) =="
echo "HTTP $(code "$BASE/api/v1/auth/me")"

echo
echo "== 7. ротация refresh =="
REFRESH_PAYLOAD=$(printf '{"refresh_token":"%s"}' "$REFRESH")
NEW=$(curl -s -X POST "$BASE/api/v1/auth/refresh" -H "$JSON" -d "$REFRESH_PAYLOAD")
echo "$NEW" | cut -c1-80
NEW_REFRESH=$(printf '%s' "$NEW" | jqv "['refresh_token']")

echo
echo "== 8. повторное использование старого refresh (ожидаем 401) =="
echo "HTTP $(code -X POST "$BASE/api/v1/auth/refresh" -H "$JSON" -d "$REFRESH_PAYLOAD")"

echo
echo "== 9. выход =="
NEW_PAYLOAD=$(printf '{"refresh_token":"%s"}' "$NEW_REFRESH")
curl -s -X POST "$BASE/api/v1/auth/logout" -H "$JSON" -d "$NEW_PAYLOAD"
echo
echo "== 10. refresh после выхода (ожидаем 401) =="
echo "HTTP $(code -X POST "$BASE/api/v1/auth/refresh" -H "$JSON" -d "$NEW_PAYLOAD")"

echo
echo "== готово =="
