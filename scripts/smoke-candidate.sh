#!/usr/bin/env bash
# Сквозная проверка кабинета кандидата на запущенном API:
# регистрация → профиль по форме → загрузка PDF-резюме → генерация PDF-профиля.
# Использование: bash scripts/smoke-candidate.sh [base_url]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${1:-http://localhost:8000}"
EMAIL="cand.$(date +%s)@example.com"
PASSWORD="secret12345"
JSON="Content-Type: application/json"
RESUME="${TMPDIR:-/tmp}/it-talent-sample-resume.pdf"

jqv() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)" 2>/dev/null; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

REG_PAYLOAD=$(printf '{"email":"%s","password":"%s","role":"candidate","consent_pdn":true}' "$EMAIL" "$PASSWORD")
LOGIN_PAYLOAD=$(printf '{"email":"%s","password":"%s"}' "$EMAIL" "$PASSWORD")

echo "== 0. подготовка образца резюме =="
if ! env -u PYTHONPATH "$ROOT/backend/.venv/bin/python" \
     "$ROOT/scripts/make-sample-resume.py" "$RESUME" >/dev/null; then
  echo "ОШИБКА: не удалось создать образец резюме"; exit 1
fi
[ -f "$RESUME" ] || { echo "ОШИБКА: файл резюме не создан"; exit 1; }
echo "создан $RESUME ($(wc -c < "$RESUME" | tr -d ' ') байт)"
echo

echo "== 1. регистрация и подтверждение =="
REG=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "$JSON" -d "$REG_PAYLOAD")
TOKEN=$(printf '%s' "$REG" | jqv "['verification_token']")
VERIFY_PAYLOAD=$(printf '{"token":"%s"}' "$TOKEN")
curl -s -o /dev/null -X POST "$BASE/api/v1/auth/verify-email" -H "$JSON" -d "$VERIFY_PAYLOAD"
LOGIN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$LOGIN_PAYLOAD")
ACCESS=$(printf '%s' "$LOGIN" | jqv "['access_token']")
[ -n "$ACCESS" ] || { echo "ОШИБКА: не получен access_token"; exit 1; }
echo "получен access-токен"
echo

echo "== 2. профиль по форме (PUT) =="
curl -s -X PUT "$BASE/api/v1/candidates/me/profile" -H "$JSON" -H "Authorization: Bearer $ACCESS" \
  -d '{"full_name":"Мария Сидорова","contacts":{"telegram":"@maria"},"specialization":"backend","grade":"middle","experience_years":4,"stack":["Python","Django"],"roles":["backend"],"summary":"Разрабатываю сервисы."}'
echo

echo "== 3. загрузка PDF-резюме (автораспознавание) =="
UPLOAD=$(curl -s -X POST "$BASE/api/v1/candidates/me/resume" -H "Authorization: Bearer $ACCESS" \
  -F "file=@$RESUME;type=application/pdf")
echo "$UPLOAD" | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps({'parsed':d['parsed'],'resume_source':d['profile']['resume_source'],'text_chars':d['text_chars']},ensure_ascii=False,indent=1))" 2>/dev/null || echo "$UPLOAD"

echo
echo "== 4. приватность: раскрыть контакты =="
curl -s -X PATCH "$BASE/api/v1/candidates/me/privacy" -H "$JSON" -H "Authorization: Bearer $ACCESS" \
  -d '{"show_contacts":true}' | python3 -c "import sys,json;print(json.load(sys.stdin)['privacy'])" 2>/dev/null
echo

echo "== 5. генерация PDF-профиля =="
OUT="${TMPDIR:-/tmp}/it-talent-generated-profile.pdf"
HTTP=$(curl -s -o "$OUT" -w '%{http_code}' "$BASE/api/v1/candidates/me/profile/pdf" \
  -H "Authorization: Bearer $ACCESS")
echo "HTTP $HTTP"
if [ -f "$OUT" ]; then
  head -c 5 "$OUT"; echo "  <- сигнатура файла"
  echo "размер: $(wc -c < "$OUT" | tr -d ' ') байт"
else
  echo "ОШИБКА: файл не создан"
fi
env -u PYTHONPATH "$ROOT/backend/.venv/bin/python" - "$OUT" <<'PY' 2>/dev/null || true
import sys
from pypdf import PdfReader
r = PdfReader(sys.argv[1])
text = "\n".join(p.extract_text() or "" for p in r.pages)
print("страниц:", len(r.pages), "| ФИО в PDF:", ("Иван Петров" in text) or ("Мария Сидорова" in text))
PY

echo
echo "== 6. доступ без роли кандидата (работодатель, ожидаем 403) =="
E_EMAIL="emp.$(date +%s)@example.com"
E_PAYLOAD=$(printf '{"email":"%s","password":"%s","role":"employer","consent_pdn":true}' "$E_EMAIL" "$PASSWORD")
EREG=$(curl -s -X POST "$BASE/api/v1/auth/register" -H "$JSON" -d "$E_PAYLOAD")
ETOKEN=$(printf '%s' "$EREG" | jqv "['verification_token']")
curl -s -o /dev/null -X POST "$BASE/api/v1/auth/verify-email" -H "$JSON" -d "{\"token\":\"$ETOKEN\"}"
ELOGIN_PAYLOAD=$(printf '{"email":"%s","password":"%s"}' "$E_EMAIL" "$PASSWORD")
EACCESS=$(curl -s -X POST "$BASE/api/v1/auth/login" -H "$JSON" -d "$ELOGIN_PAYLOAD" | jqv "['access_token']")
echo "HTTP $(code "$BASE/api/v1/candidates/me/profile" -H "Authorization: Bearer $EACCESS")"

echo
echo "== готово =="
