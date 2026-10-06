import { useState } from "react";
import type { ReactNode } from "react";

import * as apiClient from "../api/client";
import type { CandidateCard, HintItem, Vacancy } from "../api/client";
import { errorMessage } from "../api/client";
import { Button, Card, SectionNote, score } from "./ui";
import { useToast } from "./toast";

/**
 * Подсказки по накопленным сигналам: что предложить каждой стороне.
 *
 * Ранжирование считает бэкенд по данным платформы (профиль, категория, отклики,
 * приглашения, стек потребностей) — у каждой позиции видно, почему она предложена.
 * Модель подключается только для семантической близости, ядро подбора не меняется.
 */
function HintList({
  items,
  renderAction,
  kind,
}: {
  items: HintItem[];
  renderAction?: (item: HintItem) => ReactNode;
  kind: "vacancy" | "candidate";
}) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div
          key={item.id ?? item.reference ?? item.title}
          className="rounded-lg border border-slate-800 p-3"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-medium">
                {kind === "vacancy"
                  ? item.title
                  : (item.full_name ?? item.reference ?? "кандидат")}
              </p>
              <p className="text-xs text-slate-400">
                {kind === "vacancy" ? (
                  <>
                    {item.company_name ?? "компания"} · {item.grade ?? "грейд не указан"} ·{" "}
                    {item.salary_from !== undefined && item.salary_to !== undefined
                      ? `${item.salary_from.toLocaleString("ru-RU")} – ${item.salary_to.toLocaleString("ru-RU")} ₽`
                      : "зарплата не указана"}
                  </>
                ) : (
                  <>
                    {item.specialization ?? "—"} / {item.grade ?? "грейд не определён"} ·{" "}
                    балл {score(item.score)}
                    {item.already_invited ? " · уже приглашали" : ""}
                  </>
                )}
              </p>
              <ul className="mt-1 space-y-0.5 text-xs text-slate-400">
                {item.reasons.map((reason) => (
                  <li key={reason}>· {reason}</li>
                ))}
              </ul>
            </div>
            <div className="flex flex-col items-end gap-2">
              {kind === "vacancy" ? (
                <span className="text-xs text-slate-500">близость {score(item.score, 2)}</span>
              ) : null}
              {renderAction ? renderAction(item) : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Кандидату: вакансии, близкие к его интересам и категории.
 *
 * На дашборде действие может отсутствовать: тогда панель подсказывает, где откликнуться,
 * а сам отклик остаётся в рабочем разделе «Вакансии».
 */
export function VacancyHints({ onApply }: { onApply?: (vacancy: Vacancy) => void }) {
  const toast = useToast();
  const [items, setItems] = useState<HintItem[] | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const data = await apiClient.candidateVacancyHints(5);
      setItems(data.items);
      setNote(data.note);
    } catch (err) {
      toast.error("Не удалось получить подсказки", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function asVacancy(item: HintItem): Vacancy {
    return {
      id: item.id ?? "",
      title: item.title ?? "",
      description: null,
      specialization_code: item.specialization ?? null,
      grade: item.grade ?? null,
      stack: item.stack ?? [],
      salary_from: item.salary_from ?? 0,
      salary_to: item.salary_to ?? 0,
      status: "published",
      company_name: item.company_name ?? null,
      created_at: new Date().toISOString(),
    };
  }

  return (
    <Card title="Подсказать близкие вакансии">
      <SectionNote>
        Платформа смотрит на ваши действия: какие вакансии вы уже выбирали, какая у вас категория и
        стек — и предлагает похожие. Это надстройка над общим списком, ничего не заменяет.
      </SectionNote>
      <div className="mt-3">
        <Button variant="ghost" disabled={busy} onClick={() => void load()}>
          {busy ? "Подбираю…" : "Показать подсказки"}
        </Button>
      </div>
      {items ? (
        items.length ? (
          <div className="mt-3">
            {note ? <p className="mb-2 text-xs text-slate-500">{note}</p> : null}
            {onApply ? null : (
              <p className="mb-2 text-xs text-slate-500">
                Откликнуться можно в разделе «Вакансии» — список откроется с теми же вакансиями.
              </p>
            )}
            <HintList
              kind="vacancy"
              items={items}
              renderAction={
                onApply
                  ? (item) => <Button onClick={() => onApply(asVacancy(item))}>Откликнуться</Button>
                  : undefined
              }
            />
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-400">{note || "Подсказок пока нет."}</p>
        )
      ) : null}
    </Card>
  );
}

/** Работодателю: кандидаты, близкие к его собственным действиям. */
export function CandidateHints({ onInvite }: { onInvite?: (candidate: CandidateCard) => void }) {
  const toast = useToast();
  const [items, setItems] = useState<HintItem[] | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    try {
      const data = await apiClient.employerCandidateHints(5);
      setItems(data.items);
      setNote(data.note);
    } catch (err) {
      toast.error("Не удалось получить подсказки", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function asCard(item: HintItem): CandidateCard {
    return {
      reference: item.reference ?? "",
      full_name: item.full_name ?? null,
      specialization: item.specialization ?? null,
      grade: item.grade ?? null,
      category_id: null,
      stack: item.stack ?? [],
      experience_years: null,
      fsp_achievements: null,
      contacts_visible: false,
      rank: 0,
      score: item.score,
      reasons: [],
      missing: [],
    };
  }

  return (
    <Card title="Кандидаты по вашим действиям">
      <SectionNote>
        Отбор идёт по тому, что вы уже делали: описанные потребности, стеки и те, кого вы приглашали.
        Уже приглашённые не повторяются — ручная работа не дублируется.
      </SectionNote>
      <div className="mt-3">
        <Button variant="ghost" disabled={busy} onClick={() => void load()}>
          {busy ? "Подбираю…" : "Показать подсказки"}
        </Button>
      </div>
      {items ? (
        items.length ? (
          <div className="mt-3">
            {note ? <p className="mb-2 text-xs text-slate-500">{note}</p> : null}
            {onInvite ? null : (
              <p className="mb-2 text-xs text-slate-500">
                Пригласить можно в разделе «Подбор кандидатов» — подсказки остаются теми же.
              </p>
            )}
            <HintList
              kind="candidate"
              items={items}
              renderAction={
                onInvite
                  ? (item) => <Button onClick={() => onInvite(asCard(item))}>Пригласить</Button>
                  : undefined
              }
            />
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-400">{note || "Подсказок пока нет."}</p>
        )
      ) : null}
    </Card>
  );
}
