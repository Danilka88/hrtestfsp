import { useCallback, useEffect, useState } from "react";

import * as apiClient from "../../api/client";
import type {
  CandidateCard,
  EmployerInvitation,
  Selection,
  SelectionSummary,
} from "../../api/client";
import { errorMessage } from "../../api/client";
import { AIButton, AISourceNote, AIText, aiToastPayload } from "../../components/ai";
import { TasksPanel, VacanciesPanel } from "../../components/marketplace";
import { useGrades, useSpecializations } from "../../api/hooks";
import { CabinetShell } from "../../components/cabinet";
import { CandidateHints } from "../../components/hints";
import { Dashboard, InvitationBars, Kpi } from "../../components/overview";
import { useToast } from "../../components/toast";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  Field,
  GRADE_CODES,
  InfoTip,
  Modal,
  ReasonList,
  SectionNote,
  SelectField,
  StatusBadge,
  TextArea,
  gradesLabel,
  money,
  score,
} from "../../components/ui";

type Tab = "overview" | "selection" | "search" | "invitations" | "vacancies" | "tasks" | "profile";

export function EmployerCabinet() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <CabinetShell
      title="Кабинет работодателя"
      active={tab}
      onSelect={setTab}
      tabs={
        [
          ["overview", "Обзор"],
          ["selection", "Подбор кандидатов"],
          ["search", "Поиск по банку"],
          ["invitations", "Приглашения"],
          ["vacancies", "Вакансии"],
          ["tasks", "Задания"],
          ["profile", "Профиль компании"],
        ] as [Tab, string][]
      }
    >

      {tab === "overview" ? <OverviewTab /> : null}
      {tab === "selection" ? <SelectionTab /> : null}
      {tab === "search" ? <SearchTab /> : null}
      {tab === "invitations" ? <InvitationsTab /> : null}
      {tab === "vacancies" ? <VacanciesPanel role="employer" /> : null}
      {tab === "tasks" ? <TasksPanel role="employer" /> : null}
      {tab === "profile" ? <CompanyTab /> : null}
    </CabinetShell>
  );
}

/**
 * Дашборд компании: что происходит с её запросами и приглашениями.
 *
 * Полезен как сводка перед работой с подборкой: видно, сколько запросов, где ждут
 * ответа и какова доля ответов кандидатов.
 */
function OverviewTab() {
  const [selections, setSelections] = useState<apiClient.SelectionSummary[]>([]);
  const [invitations, setInvitations] = useState<EmployerInvitation[]>([]);
  const [vacancies, setVacancies] = useState<apiClient.Vacancy[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [selectionsData, invitationsData, vacanciesData] = await Promise.all([
          apiClient.listSelections(),
          apiClient.employerInvitations(),
          apiClient.listMyVacancies(),
        ]);
        setSelections(selectionsData);
        setInvitations(invitationsData);
        setVacancies(vacanciesData);
      } catch (err) {
        setError(errorMessage(err));
      }
    })();
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;

  const candidatesInSelections = selections.reduce((sum, item) => sum + item.candidates_count, 0);
  const answered = invitations.filter(
    (item) => item.status === "accepted" || item.status === "declined",
  ).length;
  const waiting = invitations.filter(
    (item) => item.status === "sent" || item.status === "viewed",
  ).length;
  const responseRate = invitations.length
    ? Math.round((answered / invitations.length) * 100)
    : null;
  const openVacancies = vacancies.filter((item) => item.status === "published").length;

  return (
    <Dashboard
      lead={
        <>
          Сводка по вашим запросам: сколько потребностей описано, сколько кандидатов в подборках,
          как отвечают на приглашения. Основная механика — приглашение конкретному человеку, а не
          ожидание отклика.
        </>
      }
      kpis={
        <>
          <Kpi
            label="Потребности и подборки"
            value={selections.length}
            hint={`кандидатов в подборках: ${candidatesInSelections}`}
          />
          <Kpi label="Приглашения" value={invitations.length} hint={`ждут ответа: ${waiting}`} />
          <Kpi
            label="Доля ответов"
            value={responseRate === null ? "нет данных" : `${responseRate}%`}
            hint={
              responseRate === null
                ? "приглашений ещё не было"
                : `ответили: ${answered} из ${invitations.length}`
            }
            tone={responseRate !== null && responseRate >= 50 ? "ok" : "default"}
          />
          <Kpi label="Открытые вакансии" value={openVacancies} hint={`всего вакансий: ${vacancies.length}`} />
        </>
      }
      ai={<CandidateHints />}
    >
      <Card title="Приглашения по статусам">
        {invitations.length === 0 ? (
          <p className="text-sm text-slate-400">
            Приглашений пока нет. Отправьте первое из подборки — кандидат увидит компанию и зарплату
            до начала общения.
          </p>
        ) : (
          <InvitationBars invitations={invitations} />
        )}
      </Card>
    </Dashboard>
  );
}

function SelectionTab() {
  const toast = useToast();
  const specializations = useSpecializations();
  const grades = useGrades();
  const [history, setHistory] = useState<SelectionSummary[]>([]);
  const [explanations, setExplanations] = useState<Record<string, string>>({});
  const [aiBusyFor, setAiBusyFor] = useState<string | null>(null);
  const [brief, setBrief] = useState("");
  const [needAiBusy, setNeedAiBusy] = useState(false);
  const [needAiResult, setNeedAiResult] = useState<apiClient.AIResult | null>(null);
  const [title, setTitle] = useState("Backend-разработчик (Python)");
  const [description, setDescription] = useState("Команда платежей");
  const [specialization, setSpecialization] = useState("backend");
  const [grade, setGrade] = useState("middle");
  const [stack, setStack] = useState("Python, PostgreSQL, Docker");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [inviteFor, setInviteFor] = useState<CandidateCard | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await apiClient.listSelections());
    } catch {
      // История — вспомогательный блок: её недоступность не должна ломать экран.
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const build = useCallback(async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await apiClient.createNeed({
        title,
        description,
        specialization_code: specialization,
        grade,
        stack: stack.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setSelection(result);
      setNotice(
        `Подборка сформирована: ${result.candidates.length} кандидатов, рубрика ${result.rubric_version}`,
      );
      toast.success(
        "Подборка сформирована",
        `${result.candidates.length} кандидатов · рубрика ${result.rubric_version}`,
      );
      void loadHistory();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [title, description, specialization, grade, stack, loadHistory]);

  const refine = useCallback(async () => {
    if (!selection) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const stackList = stack
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      // Уточнение создаёт новую подборку на сервере: прежняя сохраняется
      // и остаётся доступной в истории (parent_selection_id).
      const refined = await apiClient.refineSelection(selection.id, {
        ...(stackList.length ? { stack: stackList } : {}),
        ...(grade ? { grade } : {}),
      });
      setSelection(refined);
      setNotice(
        `Уточнённая подборка: ${refined.candidates.length} кандидатов` +
          (refined.parent_selection_id ? ` · прежняя версия сохранена` : ""),
      );
      toast.success("Подборка уточнена", "Прежняя версия сохранена в истории подборок");
      void loadHistory();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [selection, stack, grade, loadHistory]);

  /** Объяснение попадания кандидата человеческим языком (на основе сохранённых критериев). */
  const explain = useCallback(
    async (candidate: CandidateCard) => {
      if (!selection) return;
      setAiBusyFor(candidate.reference);
      try {
        const result = await apiClient.aiMatchExplain({
          selection_id: selection.id,
          candidate_reference: candidate.reference,
        });
        const data = result.data as { summary?: string; points?: string[] };
        const text = [data.summary, ...(data.points ?? []).map((point) => `· ${point}`)]
          .filter(Boolean)
          .join(" ");
        setExplanations((prev) => ({ ...prev, [candidate.reference]: text }));
        const payload = aiToastPayload(result, "Объяснение готово");
        toast.push(payload.kind, payload.text, payload.detail);
      } catch (err) {
        toast.error("Не удалось сформулировать объяснение", errorMessage(err));
      } finally {
        setAiBusyFor(null);
      }
    },
    [selection, toast],
  );

  /** ИИ-сборка потребности из короткой заметки: заполняет форму, но её можно править. */
  const draftNeed = useCallback(async () => {
    if (brief.trim().length < 5) return;
    setNeedAiBusy(true);
    setNeedAiResult(null);
    try {
      const result = await apiClient.aiNeedDraft(brief);
      setNeedAiResult(result);
      const data = result.data as {
        title?: string;
        description?: string;
        stack?: string[];
        specialization_code?: string;
        grade?: string;
      };
      if (data.title) setTitle(data.title);
      if (data.description) setDescription(data.description);
      if (data.stack?.length) setStack(data.stack.join(", "));
      if (data.specialization_code) setSpecialization(data.specialization_code);
      if (data.grade) setGrade(data.grade);
      const payload = aiToastPayload(result, "Потребность собрана");
      toast.push(payload.kind, payload.text, payload.detail);
    } catch (err) {
      toast.error("Не удалось собрать потребность", errorMessage(err));
    } finally {
      setNeedAiBusy(false);
    }
  }, [brief, toast]);

  /** Открывает сохранённую версию подборки — прежние результаты не теряются. */
  const openVersion = useCallback(
    async (id: string) => {
      try {
        setSelection(await apiClient.getSelection(id));
        toast.info("Показана сохранённая версия подборки");
      } catch (err) {
        toast.error("Не удалось открыть версию", errorMessage(err));
      }
    },
    [toast],
  );

  return (
    <div className="space-y-4">
      <SectionNote>
        Опишите потребность — платформа соберёт подборку кандидатов. Порядок в подборке не случайный:
        сначала идут кандидаты <b>запрошенной категории</b> (специализация × грейд), внутри категории —
        по силе подтверждённого профиля. Контакты скрыты до принятия приглашения.
      </SectionNote>

      <Card
        title={
          <>
            Потребность
            <InfoTip text="Чем точнее описание — специализация, грейд и стек, — тем осмысленнее подборка: эти признаки участвуют в расчёте соответствия. Зарплата в приглашении обязательна." />
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Название роли" value={title} onChange={setTitle} />
          <SelectField
            label="Специализация"
            value={specialization}
            onChange={setSpecialization}
            options={specializations.map((item) => ({ value: item.code, label: item.title }))}
          />
          <SelectField
            label="Грейд"
            value={grade}
            onChange={setGrade}
            options={
              grades.length
                ? grades.map((item) => ({ value: item.code, label: item.title }))
                : GRADE_CODES.map((code) => ({ value: code, label: gradesLabel(code) }))
            }
          />
          <Field label="Стек (через запятую)" value={stack} onChange={setStack} />
        </div>
        <div className="mt-3">
          <TextArea label="Чем занимается команда и кто нужен" value={description} onChange={setDescription} rows={3} />
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <Field label="Коротко: кого ищете (для ИИ)" value={brief} onChange={setBrief} />
          <AIButton
            onClick={() => void draftNeed()}
            busy={needAiBusy}
            disabled={brief.trim().length < 5}
            title="Собрать потребность из заметки"
          >
            Собрать потребность
          </AIButton>
        </div>
        <AISourceNote result={needAiResult} />
        <div className="mt-3 flex gap-2">
          <Button onClick={() => void build()} disabled={busy}>
            Сформировать подборку
          </Button>
          <Button variant="ghost" onClick={() => void refine()} disabled={busy || !selection}>
            Уточнить подборку (прежняя сохраняется)
          </Button>
        </div>
      </Card>

      {notice ? <Alert kind="ok">{notice}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}

      {selection ? (
        <Card
          title={
            <>
              Подборка · {selection.candidates.length} кандидатов
              <InfoTip text="Веса фиксированы заранее: сила подтверждённого профиля 0.45, достижения ФСП 0.20, свежесть решений 0.10, соответствие потребности 0.25. Первым ключом идёт категория, поэтому кандидат запрошенного грейда и специализации всегда выше." />
            </>
          }
          accent
        >
          <p className="mb-3 text-xs text-slate-500">
            Рубрика {selection.rubric_version} · рекомендуемые категории:{" "}
            {selection.recommended_categories.join(", ") || "—"} · веса критериев зафиксированы до
            просмотра пула
          </p>
          <div className="space-y-3">
            {selection.candidates.map((candidate) => (
              <CandidateRow
                key={candidate.reference}
                candidate={candidate}
                busy={busy}
                onInvite={setInviteFor}
                onExplain={(item) => void explain(item)}
                explanation={explanations[candidate.reference]}
                aiBusy={aiBusyFor === candidate.reference}
              />
            ))}
            {selection.candidates.length === 0 ? (
              <EmptyState
                title="Кандидатов по этой потребности пока нет"
                hint="Попробуйте уточнить стек или расширить грейд — подборка формируется по категории и подтверждённому профилю."
              />
            ) : null}
          </div>
        </Card>
      ) : null}

      {history.length ? (
        <Card title="История подборок">
          <p className="mb-2 text-xs text-slate-500">
            Уточнение не перезаписывает результат: каждая версия хранится отдельно.
          </p>
          <ul className="space-y-1 text-sm">
            {history.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => void openVersion(item.id)}
                  className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-slate-800 p-3 text-left text-slate-300 transition hover:border-sky-500/60 hover:text-white"
                >
                  <span className="font-medium">{item.title}</span>
                  <span className="text-xs text-slate-500">
                    {item.candidates_count} кандидатов
                    {item.parent_selection_id ? " · уточнение предыдущей версии" : " · первичная"}
                  </span>
                  <span className="ml-auto text-xs text-sky-400">открыть</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <CandidateHints onInvite={setInviteFor} />

      {inviteFor ? (
        <InvitePanel
          candidate={inviteFor}
          onClose={() => setInviteFor(null)}
          onSent={(text) => {
            setInviteFor(null);
            setNotice(text);
          }}
        />
      ) : null}
    </div>
  );
}

function InvitationsTab() {
  const toast = useToast();
  const [invitations, setInvitations] = useState<EmployerInvitation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [revokeFor, setRevokeFor] = useState<EmployerInvitation | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setInvitations(await apiClient.employerInvitations());
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function revoke() {
    if (!revokeFor) return;
    setBusy(true);
    try {
      await apiClient.revokeInvitation(revokeFor.id);
      toast.success(
        "Приглашение отозвано",
        "Кандидат больше не сможет его принять — можно отправить новое с другими условиями",
      );
      setRevokeFor(null);
      await load();
    } catch (err) {
      toast.error("Не удалось отозвать приглашение", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-4">
      <SectionNote>
        Приглашение — основная механика сервиса: инициативу проявляет работодатель. Кандидат видит
        компанию, предложение и зарплату <b>до</b> начала общения. Статусы: отправлено → просмотрено →
        принято или отклонено. Пока кандидат не принял решение, приглашение можно отозвать — например,
        если условия изменились.
      </SectionNote>
      <Alert kind="info">
        Контакты кандидата появляются здесь только после того, как он принял приглашение или
        откликнулся сам.
      </Alert>
      <div className="flex justify-end">
        <Button variant="ghost" onClick={() => void load()}>
          Обновить
        </Button>
      </div>
      {invitations.length === 0 ? (
        <EmptyState
          title="Приглашений пока нет"
          hint="Приглашение отправляется из подборки или из поиска по банку: кандидат увидит компанию и зарплату до начала общения."
        />
      ) : null}
      {invitations.map((invitation) => (
        <Card key={invitation.id}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-medium">
                {invitation.candidate_name ?? invitation.candidate_reference}
              </p>
              <p className="text-xs text-slate-400">
                {invitation.candidate_specialization ?? "—"} / {gradesLabel(invitation.candidate_grade)}{" "}
                · {money(invitation.salary_from)} – {money(invitation.salary_to)}
              </p>
              {invitation.message ? (
                <p className="mt-1 text-sm text-slate-400">{invitation.message}</p>
              ) : null}
              {invitation.contacts_revealed && invitation.candidate_contacts ? (
                <p className="mt-2 text-sm text-emerald-300">
                  Контакты: {invitation.candidate_contacts.email ?? "—"} ·{" "}
                  {invitation.candidate_contacts.phone ?? "—"} ·{" "}
                  {invitation.candidate_contacts.telegram ?? "—"}
                </p>
              ) : (
                <p className="mt-2 text-xs text-slate-600">Контакты скрыты</p>
              )}
            </div>
            <div className="flex flex-col items-end gap-2">
              <StatusBadge status={invitation.status} />
              {invitation.can_revoke ? (
                <Button variant="danger" onClick={() => setRevokeFor(invitation)}>
                  Отозвать
                </Button>
              ) : null}
            </div>
          </div>
        </Card>
      ))}

      <Modal
        open={revokeFor !== null}
        title="Отозвать приглашение?"
        onClose={() => setRevokeFor(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRevokeFor(null)}>
              Оставить
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => void revoke()}>
              {busy ? "Отзываю…" : "Отозвать"}
            </Button>
          </>
        }
      >
        <p>
          Приглашение кандидату{" "}
          <b>{revokeFor?.candidate_name ?? revokeFor?.candidate_reference}</b> будет отозвано: кандидат
          больше не сможет его принять, а вы получите возможность отправить новое приглашение с другими
          условиями.
        </p>
        <p className="mt-2 text-sm text-slate-400">
          Если кандидат уже принял или отклонил приглашение, отозвать его нельзя — решение остаётся в
          истории у обеих сторон.
        </p>
      </Modal>
    </div>
  );
}

function CompanyTab() {
  const [companyName, setCompanyName] = useState("");
  const [description, setDescription] = useState("");
  const [website, setWebsite] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiClient
      .getEmployerProfile()
      .then((profile) => {
        setCompanyName(String(profile.company_name ?? ""));
        setDescription(String(profile.description ?? ""));
        setWebsite(String(profile.website ?? ""));
        setContactEmail(String(profile.contact_email ?? ""));
      })
      .catch(() => undefined);
  }, []);

  async function save() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await apiClient.putEmployerProfile({
        company_name: companyName || null,
        description: description || null,
        industry: "it",
        website: website || null,
        contact_email: contactEmail || null,
      });
      setMessage("Профиль компании сохранён");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Профиль компании">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Название организации" value={companyName} onChange={setCompanyName} />
        <Field label="Контактный email" value={contactEmail} onChange={setContactEmail} />
        <Field label="Сайт" value={website} onChange={setWebsite} />
      </div>
      <div className="mt-3">
        <TextArea label="Направление деятельности" value={description} onChange={setDescription} rows={3} />
      </div>
      <div className="mt-3">
        <Button onClick={() => void save()} disabled={busy}>
          Сохранить
        </Button>
      </div>
      {message ? <p className="mt-2 text-sm text-emerald-300">{message}</p> : null}
      {error ? <p className="mt-2 text-sm text-rose-300">{error}</p> : null}
    </Card>
  );
}

/** Карточка кандидата с объяснением — одна и та же в подборке и в поиске. */
function CandidateRow({
  candidate,
  busy,
  onInvite,
  onExplain,
  explanation,
  aiBusy,
}: {
  candidate: CandidateCard;
  busy: boolean;
  onInvite: (candidate: CandidateCard) => void;
  onExplain?: (candidate: CandidateCard) => void;
  explanation?: string;
  aiBusy?: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-800 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            #{candidate.rank} · {candidate.full_name ?? candidate.reference}
          </p>
          <p className="text-xs text-slate-400">
            {candidate.specialization ?? "—"} / {gradesLabel(candidate.grade)} · балл{" "}
            {score(candidate.score)}
            {candidate.fsp_achievements !== null
              ? ` · достижений ФСП: ${candidate.fsp_achievements}`
              : ""}
          </p>
          {candidate.stack.length ? (
            <p className="mt-1 text-xs text-slate-500">{candidate.stack.join(", ")}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onExplain ? (
            <AIButton
              onClick={() => onExplain(candidate)}
              busy={aiBusy}
              title="Сформулировать причину попадания в подборку"
            >
              Объяснить словами
            </AIButton>
          ) : null}
          <Button onClick={() => onInvite(candidate)} disabled={busy}>
            Пригласить
          </Button>
        </div>
      </div>
      <ReasonList reasons={candidate.reasons} missing={candidate.missing} />
      {explanation ? (
        <p className="mt-2 rounded-lg border border-violet-500/40 bg-violet-500/[0.06] p-3 text-xs text-violet-100">
          <AIText>{explanation}</AIText>
        </p>
      ) : null}
      <p className="mt-1 text-xs text-slate-600">Контакты скрыты до принятия приглашения</p>
    </div>
  );
}

/**
 * Форма приглашения. Общая для подборки и поиска: обязательность зарплаты и
 * правила раскрытия контактов должны совпадать во всех сценариях.
 */
function InvitePanel({
  candidate,
  onClose,
  onSent,
}: {
  candidate: CandidateCard;
  onClose: () => void;
  onSent: (message: string) => void;
}) {
  const toast = useToast();
  const [salaryFrom, setSalaryFrom] = useState("250000");
  const [salaryTo, setSalaryTo] = useState("320000");
  const [message, setMessage] = useState("Приглашаем в команду");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [company, setCompany] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiResult, setAiResult] = useState<apiClient.AIResult | null>(null);

  useEffect(() => {
    apiClient
      .getEmployerProfile()
      .then((profile) => setCompany(String(profile.company_name ?? "")))
      .catch(() => undefined);
  }, []);

  /** Черновик текста предложения: компания, грейд и зарплата подставляются из формы. */
  async function draftText() {
    setAiBusy(true);
    setAiResult(null);
    try {
      const result = await apiClient.aiInvitationDraft({
        company: company || "компания",
        candidate_grade: candidate.grade,
        stack: candidate.stack,
        salary_from: Number(salaryFrom),
        salary_to: Number(salaryTo),
      });
      setAiResult(result);
      const text = String((result.data as { message?: string }).message ?? "");
      if (text) setMessage(text);
      const payload = aiToastPayload(result, "Текст приглашения готов");
      toast.push(payload.kind, payload.text, payload.detail);
    } catch (err) {
      toast.error("Не удалось подготовить текст", errorMessage(err));
    } finally {
      setAiBusy(false);
    }
  }

  async function send() {
    setBusy(true);
    setError(null);
    try {
      await apiClient.sendInvitation({
        candidate_reference: candidate.reference,
        message,
        salary_from: Number(salaryFrom),
        salary_to: Number(salaryTo),
        contact_method: "hr@company.ru",
      });
      const sentTo = candidate.reference;
      onSent(`Приглашение отправлено кандидату ${sentTo}`);
      toast.success(
        "Приглашение отправлено",
        "Кандидат увидит компанию и зарплату до начала общения; контакты раскроются после принятия",
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      title={`Приглашение кандидату ${candidate.reference}`}
      description={
        <>
          Кандидат увидит название компании и зарплату <b>до начала общения</b>. Контакты
          раскроются только после того, как он примет приглашение.
        </>
      }
      onClose={onClose}
      footer={
        <>
          <Button onClick={() => void send()} disabled={busy}>
            Отправить приглашение
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
        </>
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <AIButton onClick={() => void draftText()} busy={aiBusy} title="Собрать текст предложения">
          Сгенерировать текст
        </AIButton>
        <span className="text-xs text-slate-500">
          компания, грейд и зарплата подставятся из формы
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Зарплата от, ₽ (обязательно)" value={salaryFrom} onChange={setSalaryFrom} />
        <Field label="Зарплата до, ₽ (обязательно)" value={salaryTo} onChange={setSalaryTo} />
      </div>
      <TextArea label="Текст предложения" value={message} onChange={setMessage} rows={4} />
      <AISourceNote result={aiResult} />
      {error ? <Alert kind="error">{error}</Alert> : null}
    </Modal>
  );
}

/** Поиск по банку кандидатов: фильтры по специализации, грейду, стеку и ФСП. */
function SearchTab() {
  const specializations = useSpecializations();
  const grades = useGrades();
  const [specialization, setSpecialization] = useState("");
  const [grade, setGrade] = useState("");
  const [stack, setStack] = useState("");
  const [hasFsp, setHasFsp] = useState(false);
  const [result, setResult] = useState<{ total: number; candidates: CandidateCard[] } | null>(null);
  const [inviteFor, setInviteFor] = useState<CandidateCard | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const search = useCallback(async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const stackList = stack
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const params: Record<string, string | number | boolean | string[]> = { limit: 20 };
      if (specialization) params.specialization_code = specialization;
      if (grade) params.grade = grade;
      if (stackList.length) params.stack = stackList;
      if (hasFsp) params.has_fsp = true;
      const found = await apiClient.searchCandidates(params);
      setResult(found);
      setNotice(`Найдено кандидатов: ${found.total}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [specialization, grade, stack, hasFsp]);

  return (
    <div className="space-y-4">
      <Card title="Поиск по банку кандидатов">
        <p className="mb-3 text-xs text-slate-500">
          Основная механика платформы — обратный подбор: работодатель видит кандидатов по их
          подтверждённой категории. Поиск нужен, когда требуется точечно проверить банк.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField
            label="Специализация"
            value={specialization}
            onChange={setSpecialization}
            options={specializations.map((item) => ({ value: item.code, label: item.title }))}
            placeholder="Любая"
          />
          <SelectField
            label="Грейд"
            value={grade}
            onChange={setGrade}
            options={grades.map((item) => ({ value: item.code, label: item.title }))}
            placeholder="Любой"
          />
          <Field label="Стек (через запятую)" value={stack} onChange={setStack} />
          <label className="flex items-center gap-2 self-end text-sm text-slate-300">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-700 bg-slate-950"
              checked={hasFsp}
              onChange={(event) => setHasFsp(event.target.checked)}
            />
            Только с подтверждёнными достижениями ФСП
          </label>
        </div>
        <div className="mt-3">
          <Button onClick={() => void search()} disabled={busy}>
            Найти
          </Button>
        </div>
      </Card>

      {notice ? <Alert kind="ok">{notice}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}

      {result ? (
        <Card title={`Результаты · ${result.candidates.length} из ${result.total}`} accent>
          <div className="space-y-3">
            {result.candidates.map((candidate) => (
              <CandidateRow
                key={candidate.reference}
                candidate={candidate}
                busy={busy}
                onInvite={setInviteFor}
              />
            ))}
            {result.candidates.length === 0 ? (
              <EmptyState
                title="По заданным условиям кандидатов нет"
                hint="Ослабьте один из фильтров — например, снимите требование по достижениям ФСП."
              />
            ) : null}
          </div>
        </Card>
      ) : null}

      {inviteFor ? (
        <InvitePanel
          candidate={inviteFor}
          onClose={() => setInviteFor(null)}
          onSent={(text) => {
            setInviteFor(null);
            setNotice(text);
          }}
        />
      ) : null}
    </div>
  );
}
