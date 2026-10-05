import { useCallback, useEffect, useState } from "react";

import * as apiClient from "../../api/client";
import type { CandidateCard, EmployerInvitation, Selection, Specialization } from "../../api/client";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  Alert,
  Button,
  Card,
  Field,
  ReasonList,
  StatusBadge,
  TextArea,
  gradesLabel,
  money,
} from "../../components/ui";

type Tab = "profile" | "selection" | "invitations";

export function EmployerCabinet() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("selection");

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Кабинет работодателя</h1>
          <p className="text-sm text-slate-400">{user?.email}</p>
        </div>
        <Button variant="ghost" onClick={() => void logout()}>
          Выйти
        </Button>
      </header>

      <nav className="flex flex-wrap gap-2">
        {(
          [
            ["selection", "Подбор кандидатов"],
            ["invitations", "Приглашения"],
            ["profile", "Профиль компании"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <Button key={key} variant={tab === key ? "primary" : "ghost"} onClick={() => setTab(key)}>
            {label}
          </Button>
        ))}
      </nav>

      {tab === "selection" ? <SelectionTab /> : null}
      {tab === "invitations" ? <InvitationsTab /> : null}
      {tab === "profile" ? <CompanyTab /> : null}
    </div>
  );
}

function SelectionTab() {
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [title, setTitle] = useState("Backend-разработчик (Python)");
  const [description, setDescription] = useState("Команда платежей");
  const [specialization, setSpecialization] = useState("backend");
  const [grade, setGrade] = useState("middle");
  const [stack, setStack] = useState("Python, PostgreSQL, Docker");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [inviteFor, setInviteFor] = useState<CandidateCard | null>(null);
  const [salaryFrom, setSalaryFrom] = useState("250000");
  const [salaryTo, setSalaryTo] = useState("320000");
  const [inviteMessage, setInviteMessage] = useState("Приглашаем в команду платежей");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiClient
      .listSpecializations()
      .then(setSpecializations)
      .catch(() => undefined);
  }, []);

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
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [title, description, specialization, grade, stack]);

  const refine = useCallback(async () => {
    if (!selection) return;
    setBusy(true);
    setError(null);
    try {
      const refined = await apiClient.getSelection(selection.id);
      setSelection(refined);
      setNotice("Прежняя подборка сохранена: уточнение создаёт новую версию");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [selection]);

  async function invite() {
    if (!inviteFor) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.sendInvitation({
        candidate_reference: inviteFor.reference,
        message: inviteMessage,
        salary_from: Number(salaryFrom),
        salary_to: Number(salaryTo),
        contact_method: "hr@company.ru",
      });
      setNotice(`Приглашение отправлено кандидату ${inviteFor.reference}`);
      setInviteFor(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Потребность">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Название роли" value={title} onChange={setTitle} />
          <label className="text-sm">
            <span className="mb-1 block text-slate-400">Специализация</span>
            <select
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
              value={specialization}
              onChange={(event) => setSpecialization(event.target.value)}
            >
              {specializations.map((spec) => (
                <option key={spec.code} value={spec.code}>
                  {spec.title}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-slate-400">Грейд</span>
            <select
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
              value={grade}
              onChange={(event) => setGrade(event.target.value)}
            >
              {["intern", "junior", "junior_plus", "middle", "senior", "lead"].map((code) => (
                <option key={code} value={code}>
                  {gradesLabel(code)}
                </option>
              ))}
            </select>
          </label>
          <Field label="Стек (через запятую)" value={stack} onChange={setStack} />
        </div>
        <div className="mt-3">
          <TextArea label="Чем занимается команда и кто нужен" value={description} onChange={setDescription} rows={3} />
        </div>
        <div className="mt-3 flex gap-2">
          <Button onClick={() => void build()} disabled={busy}>
            Сформировать подборку
          </Button>
          <Button variant="ghost" onClick={() => void refine()} disabled={busy || !selection}>
            Показать уточнённую (прежняя сохраняется)
          </Button>
        </div>
      </Card>

      {notice ? <Alert kind="ok">{notice}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}

      {selection ? (
        <Card title={`Подборка · ${selection.candidates.length} кандидатов`} accent>
          <p className="mb-3 text-xs text-slate-500">
            Рубрика {selection.rubric_version} · рекомендуемые категории:{" "}
            {selection.recommended_categories.join(", ") || "—"} · веса критериев зафиксированы до
            просмотра пула
          </p>
          <div className="space-y-3">
            {selection.candidates.map((candidate) => (
              <div key={candidate.reference} className="rounded-lg border border-slate-800 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">
                      #{candidate.rank} · {candidate.full_name ?? candidate.reference}
                    </p>
                    <p className="text-xs text-slate-400">
                      {candidate.specialization ?? "—"} / {gradesLabel(candidate.grade)} · балл{" "}
                      {candidate.score}
                      {candidate.fsp_achievements !== null
                        ? ` · достижений ФСП: ${candidate.fsp_achievements}`
                        : ""}
                    </p>
                    {candidate.stack.length ? (
                      <p className="mt-1 text-xs text-slate-500">{candidate.stack.join(", ")}</p>
                    ) : null}
                  </div>
                  <Button onClick={() => setInviteFor(candidate)} disabled={busy}>
                    Пригласить
                  </Button>
                </div>
                <ReasonList reasons={candidate.reasons} missing={candidate.missing} />
                <p className="mt-1 text-xs text-slate-600">Контакты скрыты до принятия приглашения</p>
              </div>
            ))}
            {selection.candidates.length === 0 ? (
              <p className="text-sm text-slate-500">Кандидатов по этой потребности пока нет.</p>
            ) : null}
          </div>
        </Card>
      ) : null}

      {inviteFor ? (
        <Card title={`Приглашение для ${inviteFor.reference}`} accent>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Зарплата от, ₽ (обязательно)" value={salaryFrom} onChange={setSalaryFrom} />
            <Field label="Зарплата до, ₽ (обязательно)" value={salaryTo} onChange={setSalaryTo} />
          </div>
          <div className="mt-3">
            <TextArea label="Текст предложения" value={inviteMessage} onChange={setInviteMessage} rows={3} />
          </div>
          <div className="mt-3 flex gap-2">
            <Button onClick={() => void invite()} disabled={busy}>
              Отправить приглашение
            </Button>
            <Button variant="ghost" onClick={() => setInviteFor(null)}>
              Отмена
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function InvitationsTab() {
  const [invitations, setInvitations] = useState<EmployerInvitation[]>([]);
  const [error, setError] = useState<string | null>(null);

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

  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-4">
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
        <p className="text-sm text-slate-500">Приглашений пока нет.</p>
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
            <StatusBadge status={invitation.status} />
          </div>
        </Card>
      ))}
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
