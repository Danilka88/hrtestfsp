"""Прикладной слой ИИ: автоматизация рутинных действий платформы.

Главный принцип: **ИИ не обязателен для работы платформы**. Каждая функция
сначала пробует локальную модель (Ollama), а при её недоступности возвращает
детерминированные демо-данные. Поэтому демонстрация проходит и на машине без
установленной модели: меняется источник текста, а не работоспособность сценария.
Признак деградации всегда возвращается наружу (`degraded`), чтобы интерфейс мог
честно показать, что сейчас работает демо-режим.

Что автоматизируется (дополнительный функционал, не ломающий основной путь):

1. разбор резюме и профиля — ускоряет заполнение у кандидата;
2. черновик описания потребности — ускоряет работу работодателя;
3. черновик приглашения — снимает «страх чистого листа»;
4. сопроводительное письмо под вакансию — помощь кандидату при отклике;
5. объяснение попадания кандидата в подборку человеческим языком;
6. заготовка короткого регулярного задания;
7. семантическое сопоставление потребности и профиля (эмбеддинги).
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.providers.mock import detect_grade, detect_roles, detect_stack
from app.providers.registry import get_llm
from app.services.reference import GRADE_ORDER, GRADE_TITLES, SPECIALIZATIONS

logger = logging.getLogger(__name__)

FENCE_RE = re.compile(r"^\s*```(?:json|json5)?\s*|\s*```\s*$", re.IGNORECASE)


class AIError(Exception):
    """Ошибка ИИ-функции: несёт HTTP-код и сообщение (как остальные доменные ошибки)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# Соответствие технологий специализациям — для демо-генерации потребности.
SPECIALIZATION_BY_STACK: dict[str, str] = {
    "Python": "backend",
    "Java": "backend",
    "Go": "backend",
    "PHP": "backend",
    "Ruby": "backend",
    "C#": "backend",
    "Kotlin": "mobile",
    "Swift": "mobile",
    "JavaScript": "frontend",
    "TypeScript": "frontend",
    "React": "frontend",
    "Vue": "frontend",
    "Angular": "frontend",
    "Kubernetes": "devops",
    "Terraform": "devops",
    "Ansible": "devops",
    "Selenium": "qa",
    "JUnit": "qa",
    "PyTorch": "data",
    "TensorFlow": "data",
    "Spark": "data",
    "Kafka": "data",
}

SPECIALIZATION_TITLES = dict(SPECIALIZATIONS)


@dataclass
class AIResult:
    """Результат вызова ИИ с признаком источника.

    `degraded=True` означает, что модель недоступна и отданы демо-данные —
    интерфейс обязан показать это пользователю, а не выдавать за работу модели.
    """

    data: dict[str, Any]
    provider: str
    degraded: bool
    latency_ms: int
    note: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "provider": self.provider,
            "degraded": self.degraded,
            "latency_ms": self.latency_ms,
            "note": self.note,
            "warnings": self.warnings,
        }


def _parse_json(text: str) -> dict[str, Any] | None:
    """Разбор ответа модели: снимает ```-обёртку, найденную на практике у Gemma."""
    cleaned = FENCE_RE.sub("", (text or "").strip()).strip()
    if not cleaned or cleaned == "{}":
        return None
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


class AIEngine:
    """Выполняет ИИ-задачи поверх LLM-провайдера с откатом на демо-данные."""

    def __init__(self) -> None:
        # Провайдер берётся из реестра: там учтены режимы auto/ollama/mock.
        pass

    async def status(self) -> dict[str, Any]:
        return await get_llm().status()

    async def _json(
        self,
        prompt: str,
        *,
        system: str,
        schema: dict,
        demo: Callable[[], dict[str, Any]],
        max_tokens: int = 700,
        note: str | None = None,
    ) -> AIResult:
        """Пробует модель; при недоступности или неразборчивом ответе — демо-данные."""
        provider = get_llm()
        started = time.perf_counter()
        try:
            raw = await provider.complete(prompt, system=system, json_schema=schema, max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001 — любая ошибка модели не должна ломать сценарий
            logger.warning("ИИ недоступен (%s), используются демо-данные", exc)
            raw = ""

        parsed = None if provider.last_degraded else _parse_json(raw)
        elapsed = int((time.perf_counter() - started) * 1000)

        if parsed is None:
            return AIResult(
                data=demo(),
                provider="demo",
                degraded=True,
                latency_ms=elapsed,
                note=note or "модель недоступна — показаны подготовленные демо-данные",
            )
        return AIResult(
            data=parsed,
            provider=provider.last_source,
            degraded=False,
            latency_ms=elapsed,
        )

    # --- 1. Разбор профиля и резюме ---------------------------------------

    async def analyze_profile(self, text: str, *, current: dict[str, Any] | None = None) -> AIResult:
        """Извлекает поля профиля и подсказывает, что стоит уточнить."""
        schema = {
            "type": "object",
            "properties": {
                "full_name": {"type": ["string", "null"]},
                "stack": {"type": "array", "items": {"type": "string"}},
                "roles": {"type": "array", "items": {"type": "string"}},
                "experience_years": {"type": ["integer", "null"]},
                "soft_skills": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
                "suggestions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["stack"],
        }
        system = (
            "Ты помогаешь ИТ-специалисту заполнить профиль. Извлекай только то, что явно "
            "есть в тексте; отсутствующее оставляй пустым. Грейд не определяй — его "
            "присваивает тест платформы. Дай 2–4 конкретных подсказки, что добавить в "
            "профиль. Отвечай по-русски, кратко."
        )
        prompt = f"Текст профиля или резюме:\n\n{text[:6000]}"
        return await self._json(
            prompt, system=system, schema=schema, demo=lambda: self._demo_profile(text, current)
        )

    def _demo_profile(self, text: str, current: dict[str, Any] | None) -> dict[str, Any]:
        stack = detect_stack(text)
        roles = detect_roles(text)
        suggestions: list[str] = []
        if not stack:
            suggestions.append("Укажите стек технологий — по нему работодатель подбирает кандидатов")
        if len(stack) < 4:
            suggestions.append("Перечислите больше технологий: чем полнее стек, тем точнее подборка")
        if not roles:
            suggestions.append("Добавьте роли, которые вы занимали в команде")
        suggestions.append("Грейд присваивается автоматически по результату тестирования")
        return {
            "full_name": (current or {}).get("full_name"),
            "stack": stack,
            "roles": roles,
            "experience_years": (current or {}).get("experience_years"),
            "soft_skills": [],
            "summary": "Демо-разбор: найдены технологии и роли по ключевым словам.",
            "suggestions": suggestions[:4],
        }

    # --- 2. Черновик потребности ------------------------------------------

    async def draft_need(self, brief: str) -> AIResult:
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "stack": {"type": "array", "items": {"type": "string"}},
                "specialization_code": {"type": "string"},
                "grade": {"type": "string"},
            },
            "required": ["title", "stack"],
        }
        system = (
            "Ты помогаешь работодателю описать потребность в специалисте. Верни короткое "
            "название роли, описание команды и задач на 2–3 предложения, список технологий "
            "и предполагаемый грейд. Отвечай по-русски."
        )
        codes = ", ".join(code for code, _ in SPECIALIZATIONS)
        prompt = (
            f"Черновик от работодателя: {brief}\n\n"
            f"Допустимые коды специализаций: {codes}. "
            f"Допустимые грейды: {', '.join(GRADE_ORDER)}."
        )
        result = await self._json(prompt, system=system, schema=schema, demo=lambda: self._demo_need(brief))
        result.data = self._normalize_need(dict(result.data))
        return result

    @staticmethod
    def _normalize_need(data: dict[str, Any]) -> dict[str, Any]:
        """Приводит ответ модели к данным платформы.

        На практике модель может не заполнить `specialization_code` или вернуть
        несуществующий код — тогда специализация выводится из стека, чтобы
        подборка не оказалась пустой из-за одного пропущенного поля.
        """
        valid_codes = {code for code, _ in SPECIALIZATIONS}
        code = str(data.get("specialization_code") or "").strip()
        if code not in valid_codes:
            votes: dict[str, int] = {}
            for technology in data.get("stack") or []:
                mapped = SPECIALIZATION_BY_STACK.get(str(technology))
                if mapped:
                    votes[mapped] = votes.get(mapped, 0) + 1
            code = max(votes, key=lambda key: votes[key]) if votes else "backend"
        data["specialization_code"] = code

        grade = str(data.get("grade") or "").strip()
        data["grade"] = grade if grade in GRADE_ORDER else "middle"
        data["stack"] = [str(item).strip() for item in (data.get("stack") or []) if str(item).strip()]
        return data

    def _demo_need(self, brief: str) -> dict[str, Any]:
        stack = detect_stack(brief)
        grade = detect_grade(brief) or "middle"
        votes: dict[str, int] = {}
        for technology in stack:
            code = SPECIALIZATION_BY_STACK.get(technology)
            if code:
                votes[code] = votes.get(code, 0) + 1
        specialization = max(votes, key=lambda k: votes[k]) if votes else "backend"
        title_role = SPECIALIZATION_TITLES.get(specialization, "Специалист")
        stack_text = ", ".join(stack) if stack else "уточните стек"
        return {
            "title": f"{title_role} ({stack_text})",
            "description": (
                f"Команда ищет {title_role.lower()} уровня «{GRADE_TITLES.get(grade, grade)}». "
                f"Ожидаемый стек: {stack_text}. "
                "Задачи — разработка и поддержка продукта, участие в код-ревью и планировании."
            ),
            "stack": stack,
            "specialization_code": specialization,
            "grade": grade,
        }

    # --- 3. Черновик приглашения ------------------------------------------

    async def draft_invitation(
        self,
        *,
        company: str,
        candidate_grade: str | None,
        stack: list[str],
        salary_from: int,
        salary_to: int,
        role_title: str | None = None,
    ) -> AIResult:
        schema = {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }
        system = (
            "Ты помогаешь работодателю написать короткое вежливое приглашение кандидату. "
            "3–5 предложений: чем занимается команда, почему кандидат интересен, условия. "
            "Без канцелярита и без обещаний, которых нет в данных. Отвечай по-русски."
        )
        prompt = (
            f"Компания: {company}\nРоль: {role_title or 'ИТ-специалист'}\n"
            f"Грейд кандидата: {candidate_grade or 'не указан'}\n"
            f"Стек: {', '.join(stack) or 'не указан'}\n"
            f"Зарплата: {salary_from}–{salary_to} ₽\n"
        )
        return await self._json(
            prompt,
            system=system,
            schema=schema,
            demo=lambda: self._demo_invitation(
                company, candidate_grade, stack, salary_from, salary_to, role_title
            ),
        )

    def _demo_invitation(
        self,
        company: str,
        candidate_grade: str | None,
        stack: list[str],
        salary_from: int,
        salary_to: int,
        role_title: str | None,
    ) -> dict[str, Any]:
        grade = GRADE_TITLES.get(candidate_grade or "", candidate_grade or "специалиста")
        role = role_title or "разработчика"
        stack_text = ", ".join(stack[:4]) if stack else "ваш профиль"
        return {
            "message": (
                f"Здравствуйте! Компания «{company}» приглашает вас на роль {role} "
                f"({grade}) в команду продукта. Мы обратили внимание на подтверждённый "
                f"профиль и опыт с {stack_text}. "
                f"Предлагаем {salary_from:,} – {salary_to:,} ₽ "
                "с обсуждением условий на собеседовании. Будем рады знакомству!"
            ).replace(",", " ")
        }

    # --- 4. Сопроводительное письмо --------------------------------------

    async def draft_cover_letter(
        self,
        *,
        vacancy_title: str,
        company: str,
        required_stack: list[str],
        candidate_stack: list[str],
        candidate_grade: str | None,
    ) -> AIResult:
        schema = {
            "type": "object",
            "properties": {
                "letter": {"type": "string"},
                "matched": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["letter"],
        }
        system = (
            "Ты помогаешь кандидату написать сопроводительное письмо. 3–4 предложения, "
            "конкретно: какие из требуемых технологий действительно есть в профиле, "
            "что кандидат готов делать. Не выдумывай опыт, которого нет. По-русски."
        )
        matched = [t for t in required_stack if t.lower() in {c.lower() for c in candidate_stack}]
        prompt = (
            f"Вакансия: {vacancy_title} в компании {company}\n"
            f"Требуемый стек: {', '.join(required_stack) or 'не указан'}\n"
            f"Стек кандидата: {', '.join(candidate_stack) or 'не указан'}\n"
            f"Грейд кандидата: {candidate_grade or 'не указан'}\n"
            f"Совпадающие технологии: {', '.join(matched) or 'нет явных совпадений'}"
        )
        return await self._json(
            prompt,
            system=system,
            schema=schema,
            demo=lambda: self._demo_cover_letter(
                vacancy_title, company, required_stack, candidate_stack, matched
            ),
        )

    def _demo_cover_letter(
        self,
        vacancy_title: str,
        company: str,
        required_stack: list[str],
        candidate_stack: list[str],
        matched: list[str],
    ) -> dict[str, Any]:
        if matched:
            match_text = f"Из требуемого стека уверенно работаю с {', '.join(matched[:4])}"
        else:
            match_text = "Требуемый стек пересекается с моим опытом"
        return {
            "letter": (
                f"Здравствуйте! Меня заинтересовала вакансия «{vacancy_title}» в компании "
                f"«{company}». {match_text}. "
                f"Дополнительно работал с {', '.join(candidate_stack[:3]) or 'профильным стеком'}. "
                "Готов обсудить задачи команды и ожидания на ближайший квартал."
            ),
            "matched": matched,
        }

    # --- 5. Объяснение попадания в подборку ------------------------------

    async def explain_match(
        self,
        *,
        candidate_summary: str,
        need_summary: str,
        reasons: list[dict[str, Any]],
    ) -> AIResult:
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "points": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary"],
        }
        system = (
            "Ты объясняешь работодателю, почему кандидат попал в подборку. Опирайся "
            "только на переданные критерии и их вклад; не добавляй качеств, которых нет "
            "в данных. 1–2 предложения вывода и 2–4 пункта. По-русски."
        )
        reason_text = "; ".join(f"{r.get('text', '')} (вклад {r.get('contribution')})" for r in reasons)
        prompt = (
            f"Потребность: {need_summary}\nКандидат: {candidate_summary}\n"
            f"Критерии ранжирования: {reason_text or 'нет данных'}"
        )
        return await self._json(
            prompt,
            system=system,
            schema=schema,
            demo=lambda: self._demo_explain(candidate_summary, reasons),
        )

    def _demo_explain(self, candidate_summary: str, reasons: list[dict[str, Any]]) -> dict[str, Any]:
        points = [f"{r.get('text')}: вклад {r.get('contribution')}" for r in reasons if r.get("contribution")]
        missing = [r.get("text") for r in reasons if not r.get("contribution")]
        summary = f"Кандидат попал в подборку по подтверждённому профилю: {candidate_summary}."
        if missing:
            summary += f" Данных нет по: {', '.join(str(m) for m in missing[:3])}."
        return {"summary": summary, "points": points[:4] or ["Критерии без вклада — данных недостаточно"]}

    # --- 6. Заготовка короткого задания ----------------------------------

    async def draft_task(self, *, need_title: str, stack: list[str], grade: str | None = None) -> AIResult:
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "statement": {"type": "string"},
                "rubric": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "statement"],
        }
        system = (
            "Ты составляешь короткое практическое задание для ИТ-специалиста (до 20 минут). "
            "Проверяй практическое мышление, а не память: описание ситуации, что нужно "
            "сделать, и 2–3 критерия оценки. Не давай готового ответа. По-русски."
        )
        prompt = f"Роль: {need_title}\nСтек: {', '.join(stack) or 'не указан'}\nГрейд: {grade or 'не указан'}"
        return await self._json(
            prompt, system=system, schema=schema, demo=lambda: self._demo_task(need_title, stack)
        )

    def _demo_task(self, need_title: str, stack: list[str]) -> dict[str, Any]:
        technology = stack[0] if stack else "вашем основном стеке"
        return {
            "title": f"Короткая задача: {need_title}",
            "statement": (
                f"Опишите подход к решению типовой задачи по направлению «{need_title}» "
                f"на {technology}: какие шаги предпримете, как проверите результат и "
                "какие риски видите. Достаточно 5–7 предложений."
            ),
            "rubric": [
                "Структурность: план из последовательных шагов",
                "Практичность: учитывает ограничения реальной эксплуатации",
                "Проверяемость: как автор убедится, что решение работает",
            ],
        }

    # --- 7. Семантическое сопоставление ----------------------------------

    async def semantic_scores(self, need_text: str, candidate_texts: list[str]) -> AIResult:
        """Косинусная близость потребности и профилей.

        С локальными эмбеддингами это семантическая близость; в демо-режиме —
        лексическая (хеш-векторизатор), о чём честно сообщает `degraded`.
        """
        provider = get_llm()
        started = time.perf_counter()
        texts = [need_text, *candidate_texts]
        try:
            vectors = await provider.embed(texts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Эмбеддинги недоступны (%s)", exc)
            vectors = []

        elapsed = int((time.perf_counter() - started) * 1000)
        if len(vectors) != len(texts):
            return AIResult(
                data={"scores": [], "method": "недоступно"},
                provider="demo",
                degraded=True,
                latency_ms=elapsed,
                note="эмбеддинги недоступны",
            )

        need_vector, candidate_vectors = vectors[0], vectors[1:]
        scores = [round(max(0.0, _cosine(need_vector, vector)), 4) for vector in candidate_vectors]
        return AIResult(
            data={
                "scores": scores,
                "method": "эмбеддинги" if not provider.last_degraded else "лексическая близость",
            },
            provider=provider.last_source,
            degraded=provider.last_degraded,
            latency_ms=elapsed,
            note=None
            if not provider.last_degraded
            else "модель эмбеддингов недоступна — применена лексическая близость",
        )

    # --- 8. Дашборд администратора ---------------------------------------

    async def platform_summary(self, metrics: dict[str, Any]) -> AIResult:
        """Сводка состояния платформы человеческим языком по посчитанным метрикам.

        Модель не считает метрики и не выдумывает числа: ей передаётся уже
        посчитанный набор, её задача — связать показатели и объяснить, что они
        означают для двустороннего рынка.
        """
        schema = {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "summary": {"type": "string"},
                "points": {"type": "array", "items": {"type": "string"}},
                "watch": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["headline", "summary"],
        }
        system = (
            "Ты аналитик двусторонней платформы подбора ИТ-специалистов. Тебе дают "
            "готовые показатели. Опиши состояние рынка платформы: что происходит с "
            "обеими сторонами, где узкое место воронки, на что смотреть. Используй "
            "только переданные числа, ничего не выдумывай. По-русски, кратко, без "
            "маркетинговых формулировок."
        )
        prompt = f"Показатели платформы (JSON):\n{_compact(metrics)}"
        return await self._json(
            prompt,
            system=system,
            schema=schema,
            demo=lambda: self._demo_summary(metrics),
            max_tokens=700,
        )

    def _demo_summary(self, metrics: dict[str, Any]) -> dict[str, Any]:
        people = metrics.get("people", {})
        liquidity = metrics.get("liquidity", {})
        candidates = int(people.get("candidates") or 0)
        employers = int(people.get("employers") or 0)
        contact_rate = liquidity.get("contact_rate")
        response_rate = liquidity.get("response_rate")
        return {
            "headline": f"{candidates} соискателей и {employers} компаний на платформе",
            "summary": (
                "Подготовленная сводка: показываются посчитанные показатели без обращения "
                "к модели. Соотношение сторон, воронка пути кандидата и ликвидность рынка "
                "рассчитаны напрямую по данным платформы."
            ),
            "points": [
                f"Соискателей: {candidates}, компаний: {employers}",
                "Доля потребностей, доведённых до приглашения: "
                f"{contact_rate if contact_rate is not None else 'нет данных'}%",
                "Доля приглашений с решением кандидата: "
                f"{response_rate if response_rate is not None else 'нет данных'}%",
            ],
            "watch": [
                "Категории без кандидатов при наличии спроса — там платформа не может помочь",
                "Приглашения без ответа дольше недели — ожидание, которое стоит снимать",
            ],
        }

    async def platform_recommendations(self, metrics: dict[str, Any]) -> AIResult:
        """Что сделать администратору: конкретные шаги по показателям."""
        schema = {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "why": {"type": "string"},
                            "how": {"type": "string"},
                        },
                        "required": ["title", "why"],
                    },
                }
            },
            "required": ["actions"],
        }
        system = (
            "Ты операционный аналитик двусторонней платформы подбора. По переданным "
            "показателям предложи 3 конкретных действия администратора. Каждое действие "
            "должно опираться на конкретный показатель и быть выполнимым: привлечение "
            "кандидатов в дефицитные категории, работа с зависшими приглашениями, "
            "активация молчащих компаний. Не выдумывай числа. По-русски."
        )
        prompt = f"Показатели платформы (JSON):\n{_compact(metrics)}"
        return await self._json(
            prompt,
            system=system,
            schema=schema,
            demo=lambda: self._demo_recommendations(metrics),
            max_tokens=800,
        )

    def _demo_recommendations(self, metrics: dict[str, Any]) -> dict[str, Any]:
        liquidity = metrics.get("liquidity", {})
        return {
            "actions": [
                {
                    "title": "Закрыть дефицит в категориях без кандидатов",
                    "why": "Есть спрос работодателей, но подборка пустая — платформа не может помочь",
                    "how": "Смотрите раздел «Категории»: строки со статусом «дефицит»",
                },
                {
                    "title": "Разобрать приглашения без ответа",
                    "why": f"Без ответа дольше недели: {liquidity.get('invitations_stale', 0)}",
                    "how": (
                        "Напомнить кандидату или отозвать приглашение, чтобы работодатель мог направить новое"
                    ),
                },
                {
                    "title": "Подключить компании, которые ещё не выходили на контакт",
                    "why": "Аккаунты есть, но основная механика — приглашение — не используется",
                    "how": "Раздел «Компании»: строки с нулём приглашений",
                },
            ]
        }


def _compact(data: dict[str, Any], limit: int = 2400) -> str:
    """Сжатое представление метрик для промпта: без форматирующих пробелов."""
    import json

    return json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":"))[:limit]


_engine: AIEngine | None = None


def get_ai() -> AIEngine:
    global _engine
    if _engine is None:
        _engine = AIEngine()
    return _engine
