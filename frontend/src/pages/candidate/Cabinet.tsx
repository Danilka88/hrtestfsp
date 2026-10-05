import { useCallback, useEffect, useState } from "react";

import * as apiClient from "../../api/client";
import type {
  CandidateInvitation,
  CategoryStatus,
  FspStatus,
  Specialization,
  TestItem,
} from "../../api/client";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { Alert, Button, Card, Field, StatusBadge, TextArea, gradesLabel, money } from "../../components/ui";

type Tab = "category" | "test" | "invitations" | "profile";

export function CandidateCabinet() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("category");

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Кабинет соискателя</h1>
          <p className="text-sm text-slate-400">{user?.email}</p>
        </div>
        <Button variant="ghost" onClick={() => void logout()}>
          Выйти
        </Button>
      </header>

      <nav className="flex flex-wrap gap-2">
        {(
          [
            ["category", "Категория и грейд"],
            ["test", "Тестирование"],
            ["invitations", "Приглашения"],
            ["profile", "Профиль и ФСП"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <Button key={key} variant={tab === key ? "primary" : "ghost"} onClick={() => setTab(key)}>
            {label}
          </Button>
        ))}
      </nav>

      {tab === "category" ? <CategoryTab /> : null}
      {tab === "test" ? <TestTab /> : null}
      {tab === "invitations" ? <InvitationsTab /> : null}
      {tab === "profile" ? <ProfileTab /> : null}
    </div>
  );
}

function CategoryTab() {
  const [status, setStatus] = useState<CategoryStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .myCategory()
      .then(setStatus)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!status) return <p className="text-sm text-slate-500">Загрузка…</p>;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card title="Специализация">
          <p className="text-lg">{status.specialization ?? "не выбрана"}</p>
        </Card>
        <Card title="Грейд" accent>
          <p className="text-lg font-semibold text-sky-300">{gradesLabel(status.grade)}</p>
          <p className="mt-1 text-xs text-slate-500">определён тестом, не самооценкой</p>
        </Card>
        <Card title="Смена грейда">
          <p className="text-sm">
            {status.grade_change_allowed
              ? "доступна"
              : `доступна через ${status.grade_change_available_in_days ?? "—"} дн.`}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            интервал {status.grade_change_cooldown_days} дн.; понижение не применяется автоматически
          </p>
        </Card>
      </div>

      <Card title="История смены грейда">
        {status.grade_history.length ? (
          <ul className="space-y-1 text-sm">
            {status.grade_history.map((entry, index) => (
              <li key={index}>
                {gradesLabel(entry.from_grade)} → <b>{gradesLabel(entry.to_grade)}</b>{" "}
                <span className="text-xs text-slate-500">
                  {new Date(entry.at).toLocaleString("ru-RU")}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">Пока нет — грейд ещё не присваивался.</p>
        )}
      </Card>

      <Card title="История тестирования">
        {status.sessions.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="py-1">Статус</th>
                  <th className="py-1">Цель</th>
                  <th className="py-1">Результат</th>
                  <th className="py-1">Заданий</th>
                  <th className="py-1">θ</th>
                </tr>
              </thead>
              <tbody>
                {status.sessions.map((session) => (
                  <tr key={session.id} className="border-t border-slate-800">
                    <td className="py-1">
                      <StatusBadge status={session.status} />
                    </td>
                    <td className="py-1">{gradesLabel(session.target_grade)}</td>
                    <td className="py-1">{gradesLabel(session.result_grade)}</td>
                    <td className="py-1">{session.items_answered}</td>
                    <td className="py-1">{session.theta.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Тестов пока не было.</p>
        )}
      </Card>
    </div>
  );
}

function TestTab() {
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [specialization, setSpecialization] = useState("");
  const [grades, setGrades] = useState<string[]>([]);
  const [targetGrade, setTargetGrade] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [item, setItem] = useState<TestItem | null>(null);
  const [itemStartedAt, setItemStartedAt] = useState<number>(0);
  const [lastVerdict, setLastVerdict] = useState<string | null>(null);
  const [result, setResult] = useState<apiClient.SessionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiClient
      .listSpecializations()
      .then((list) => {
        setSpecializations(list);
        if (list.length) setSpecialization(list[0].code);
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const startSurvey = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const survey = await apiClient.submitSurvey(specialization);
      setGrades(survey.grade_options);
      setTargetGrade(survey.grade_options[0] ?? "");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [specialization]);

  const start = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const session = await apiClient.startSession(specialization, targetGrade);
      setSessionId(session.session_id);
      setItem(session.item);
      setItemStartedAt(Date.now());
      setResult(null);
      setLastVerdict(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [specialization, targetGrade]);

  const answer = useCallback(
    async (index: number) => {
      if (!sessionId || !item) return;
      setBusy(true);
      setError(null);
      try {
        const response = await apiClient.answerItem(
          sessionId,
          item.id,
          index,
          Date.now() - itemStartedAt,
        );
        setLastVerdict(response.correct ? "верно" : "неверно");
        if (response.finished && response.result) {
          setResult(response.result);
          setItem(null);
        } else if (response.next_item) {
          setItem(response.next_item);
          setItemStartedAt(Date.now());
        }
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [sessionId, item, itemStartedAt],
  );

  return (
    <div className="space-y-4">
      <Card title="Шаг 1. Опрос по отрасли и специализации">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-slate-400">Специализация</span>
            <select
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
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
          <Button onClick={() => void startSurvey()} disabled={busy || !specialization}>
            Пройти опрос
          </Button>
        </div>
      </Card>

      {grades.length ? (
        <Card title="Шаг 2. Заявленный грейд и тест">
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="mb-1 block text-slate-400">Грейд, на который тестируетесь</span>
              <select
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                value={targetGrade}
                onChange={(event) => setTargetGrade(event.target.value)}
              >
                {grades.map((grade) => (
                  <option key={grade} value={grade}>
                    {gradesLabel(grade)}
                  </option>
                ))}
              </select>
            </label>
            <Button onClick={() => void start()} disabled={busy || !targetGrade}>
              Начать тест
            </Button>
          </div>
        </Card>
      ) : null}

      {item ? (
        <Card title={`Задание (${item.skill_tag})`} accent>
          <p className="text-sm text-slate-200">{item.question}</p>
          <div className="mt-3 space-y-2">
            {item.options.map((option, index) => (
              <Button key={index} variant="ghost" onClick={() => void answer(index)} disabled={busy}>
                {option}
              </Button>
            ))}
          </div>
          {lastVerdict ? (
            <p className="mt-3 text-xs text-slate-500">Предыдущий ответ: {lastVerdict}</p>
          ) : null}
        </Card>
      ) : null}

      {result ? (
        <Card title="Результат теста" accent>
          <div className="grid gap-3 sm:grid-cols-2">
            <p className="text-sm">
              Грейд по результату: <b className="text-sky-300">{gradesLabel(result.result_grade)}</b>
            </p>
            <p className="text-sm">
              Текущий грейд: <b>{gradesLabel(result.current_grade)}</b>
            </p>
            <p className="text-sm">Заданий: {result.items_answered}</p>
            <p className="text-sm">
              Оценка θ = {result.theta.toFixed(3)} (ошибка ±{result.standard_error.toFixed(3)})
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-400">{result.grade_change_reason}</p>
          {result.warnings.length ? (
            <p className="mt-1 text-xs text-amber-400/80">{result.warnings.join("; ")}</p>
          ) : null}
        </Card>
      ) : null}

      {error ? <Alert kind="error">{error}</Alert> : null}
    </div>
  );
}

function InvitationsTab() {
  const [invitations, setInvitations] = useState<CandidateInvitation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setInvitations(await apiClient.myInvitations());
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(id: string, status: "accepted" | "declined") {
    setBusy(true);
    try {
      await apiClient.decideInvitation(id, status);
      await load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-4">
      <Alert kind="info">
        Зарплата и компания видны до начала общения. Контакты работодатель получает только после
        вашего согласия.
      </Alert>
      {invitations.length === 0 ? (
        <p className="text-sm text-slate-500">
          Входящих приглашений нет. Работодатель сам находит вас по подтверждённой категории.
        </p>
      ) : null}
      {invitations.map((invitation) => (
        <Card key={invitation.id} accent={invitation.status === "sent"}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-medium">{invitation.company_name ?? "Компания"}</p>
              <p className="mt-1 text-sm text-sky-300">
                {money(invitation.salary_from)} – {money(invitation.salary_to)}
              </p>
              {invitation.message ? (
                <p className="mt-2 max-w-xl text-sm text-slate-300">{invitation.message}</p>
              ) : null}
              {invitation.contact_method ? (
                <p className="mt-1 text-xs text-slate-500">Способ связи: {invitation.contact_method}</p>
              ) : null}
            </div>
            <div className="flex flex-col items-end gap-2">
              <StatusBadge status={invitation.status} />
              {invitation.status === "sent" || invitation.status === "viewed" ? (
                <div className="flex gap-2">
                  <Button disabled={busy} onClick={() => void decide(invitation.id, "accepted")}>
                    Принять
                  </Button>
                  <Button
                    variant="danger"
                    disabled={busy}
                    onClick={() => void decide(invitation.id, "declined")}
                  >
                    Отклонить
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function ProfileTab() {
  const [fullName, setFullName] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [grade, setGrade] = useState("");
  const [stack, setStack] = useState("");
  const [summary, setSummary] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [fsp, setFsp] = useState<FspStatus | null>(null);
  const [fspInput, setFspInput] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const profile = await apiClient.getCandidateProfile();
      setFullName(profile.full_name ?? "");
      setSpecialization(profile.specialization ?? "");
      setGrade(profile.grade ?? "");
      setStack(profile.stack.join(", "));
      setSummary(profile.summary ?? "");
    } catch {
      /* профиль ещё не создан */
    }
    try {
      const status = await apiClient.getFsp();
      setFsp(status);
      setFspInput(status.fsp_id ?? "");
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const contacts: Record<string, string> = {};
      if (contactEmail) contacts.email = contactEmail;
      if (contactPhone) contacts.phone = contactPhone;
      await apiClient.putCandidateProfile({
        full_name: fullName || null,
        specialization: specialization || null,
        grade: grade || null,
        experience_years: null,
        stack: stack.split(",").map((s) => s.trim()).filter(Boolean),
        roles: [],
        soft_skills: [],
        summary: summary || null,
        contacts,
      });
      setMessage("Профиль сохранён");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveFsp(next: string | null) {
    setBusy(true);
    setError(null);
    try {
      setFsp(await apiClient.linkFsp(next));
      setMessage(next ? "Идентификатор ФСП привязан" : "Идентификатор ФСП отвязан");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Профиль">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="ФИО" value={fullName} onChange={setFullName} />
          <Field label="Специализация (например backend)" value={specialization} onChange={setSpecialization} />
          <Field label="Стек (через запятую)" value={stack} onChange={setStack} />
          <Field label="Контактный email (скрыт до принятия приглашения)" value={contactEmail} onChange={setContactEmail} />
          <Field label="Телефон" value={contactPhone} onChange={setContactPhone} />
        </div>
        <div className="mt-3">
          <TextArea label="О себе" value={summary} onChange={setSummary} />
        </div>
        <div className="mt-3">
          <Button onClick={() => void save()} disabled={busy}>
            Сохранить профиль
          </Button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Грейд присваивается тестом. Значение из формы используется только как исходное для профиля.
        </p>
      </Card>

      <Card title="Связь с идентификатором ФСП">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Идентификатор участника ФСП" value={fspInput} onChange={setFspInput} />
          <Button onClick={() => void saveFsp(fspInput || null)} disabled={busy}>
            Привязать
          </Button>
          <Button variant="ghost" onClick={() => void saveFsp(null)} disabled={busy || !fsp?.linked}>
            Отвязать
          </Button>
        </div>
        {fsp ? (
          <div className="mt-3 text-sm">
            <p className="text-slate-400">{fsp.note}</p>
            {fsp.achievements.length ? (
              <ul className="mt-2 space-y-1">
                {fsp.achievements.map((achievement, index) => (
                  <li key={index} className="text-slate-300">
                    {achievement.contest} ({achievement.year})
                    {achievement.place ? ` — ${achievement.place} место` : ""}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </Card>

      {message ? <Alert kind="ok">{message}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
    </div>
  );
}
