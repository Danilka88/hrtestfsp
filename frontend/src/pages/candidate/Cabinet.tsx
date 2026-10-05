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
import { AIButton, AISourceNote, AIStatusBadge, aiToastPayload } from "../../components/ai";
import { TasksPanel, VacanciesPanel } from "../../components/marketplace";
import { useToast } from "../../components/toast";
import { Alert, Button, Card, Field, StatusBadge, TextArea, gradesLabel, money } from "../../components/ui";

type Tab = "category" | "test" | "invitations" | "vacancies" | "tasks" | "profile";

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
        <div className="flex items-center gap-3">
          <AIStatusBadge />
          <Button variant="ghost" onClick={() => void logout()}>
            Выйти
          </Button>
        </div>
      </header>

      <nav className="flex flex-wrap gap-2">
        {(
          [
            ["category", "Категория и грейд"],
            ["test", "Тестирование"],
            ["invitations", "Приглашения"],
            ["vacancies", "Вакансии"],
            ["tasks", "Задания"],
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
      {tab === "vacancies" ? <VacanciesPanel role="candidate" /> : null}
      {tab === "tasks" ? <TasksPanel role="candidate" /> : null}
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
  const toast = useToast();
  const [invitations, setInvitations] = useState<CandidateInvitation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await apiClient.myInvitations();
      // Открытие вкладки означает фактический просмотр: приглашения в статусе
      // «отправлено» переводятся в «просмотрено», чтобы работодатель видел,
      // что приглашение доставлено и открыто, а не проигнорировано.
      const marked = await Promise.all(
        list.map(async (invitation) =>
          invitation.status === "sent" ? await apiClient.viewInvitation(invitation.id) : invitation,
        ),
      );
      setInvitations(marked);
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
      if (status === "accepted") {
        toast.success(
          "Приглашение принято",
          "Работодатель получил ваши контакты — свяжется по указанному способу",
        );
      } else {
        toast.info("Приглашение отклонено", "Работодатель увидит ваш отказ");
      }
      await load();
    } catch (err) {
      toast.error("Не удалось изменить решение", errorMessage(err));
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
  const toast = useToast();
  const [resumeText, setResumeText] = useState("");
  const [aiResult, setAiResult] = useState<apiClient.AIResult | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [privacy, setPrivacy] = useState<Record<string, boolean>>({});
  const [privacyBusy, setPrivacyBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const profile = await apiClient.getCandidateProfile();
      setFullName(profile.full_name ?? "");
      setSpecialization(profile.specialization ?? "");
      setGrade(profile.grade ?? "");
      setStack(profile.stack.join(", "));
      setSummary(profile.summary ?? "");
      setPrivacy(profile.privacy ?? {});
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

  /** ИИ-разбор текста: заполняет поля профиля и подсказывает, что дополнить. */
  async function analyze() {
    setAiBusy(true);
    setAiResult(null);
    setSuggestions([]);
    try {
      const result = await apiClient.aiProfileAnalyze(resumeText);
      setAiResult(result);
      const data = result.data as {
        stack?: string[];
        summary?: string;
        full_name?: string | null;
        suggestions?: string[];
      };
      if (data.stack?.length) setStack(data.stack.join(", "));
      if (data.summary && !summary) setSummary(data.summary);
      if (data.full_name && !fullName) setFullName(data.full_name);
      setSuggestions(data.suggestions ?? []);
      const payload = aiToastPayload(result, "Разбор готов");
      toast.push(payload.kind, payload.text, payload.detail);
    } catch (err) {
      toast.error("Не удалось разобрать текст", errorMessage(err));
    } finally {
      setAiBusy(false);
    }
  }

  /** Сохранение настроек видимости профиля для работодателя. */
  async function savePrivacy(next: Record<string, boolean>) {
    setPrivacy(next);
    setPrivacyBusy(true);
    try {
      const updated = await apiClient.patchPrivacy({
        show_stack: Boolean(next.show_stack),
        show_experience: Boolean(next.show_experience),
        show_fsp: Boolean(next.show_fsp),
        show_contacts: Boolean(next.show_contacts),
      });
      setPrivacy(updated.privacy ?? next);
      toast.success("Настройки приватности сохранены", "Работодатель увидит профиль согласно этим настройкам");
    } catch (err) {
      toast.error("Не удалось сохранить настройки", errorMessage(err));
    } finally {
      setPrivacyBusy(false);
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

      <Card title="Приватность: что видно работодателю">
        <p className="mb-3 text-xs text-slate-500">
          Настройки управляют только тем, какие блоки профиля показывает выдача. Контакты в любом
          случае раскрываются лишь после того, как вы приняли приглашение или откликнулись сами.
        </p>
        <div className="space-y-2">
          {(
            [
              ["show_stack", "Стек технологий", "какие технологии указаны в профиле"],
              ["show_experience", "Стаж и опыт", "сколько лет опыта видит работодатель"],
              ["show_fsp", "Достижения ФСП", "подтверждённые результаты соревнований"],
              ["show_contacts", "Контакты в PDF-профиле", "показывать контакты в скачиваемом PDF"],
            ] as Array<[string, string, string]>
          ).map(([key, label, hint]) => (
            <label
              key={key}
              className="flex items-start gap-3 rounded-lg border border-slate-800 p-3 text-sm"
            >
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 rounded border-slate-700 bg-slate-950"
                checked={Boolean(privacy[key])}
                disabled={privacyBusy}
                onChange={(event) => void savePrivacy({ ...privacy, [key]: event.target.checked })}
              />
              <span>
                <span className="text-slate-200">{label}</span>
                <span className="block text-xs text-slate-500">{hint}</span>
              </span>
            </label>
          ))}
        </div>
      </Card>

      <Card title="ИИ-разбор резюме">
        <p className="mb-3 text-xs text-slate-500">
          Вставьте текст резюме — модель извлечёт стек и роли и подскажет, что дополнить.
          Разбор ускоряет заполнение профиля, но не заменяет обязательное тестирование:
          грейд присваивается только по результату теста.
        </p>
        <TextArea
          label="Текст резюме или описания профиля"
          value={resumeText}
          onChange={setResumeText}
          rows={5}
        />
        <div className="mt-3">
          <AIButton
            onClick={() => void analyze()}
            busy={aiBusy}
            disabled={resumeText.trim().length < 20}
            title="Извлечь поля профиля из текста"
          >
            Разобрать текст
          </AIButton>
        </div>
        <AISourceNote result={aiResult} />
        {suggestions.length ? (
          <ul className="mt-2 space-y-1 text-xs text-amber-300/90">
            {suggestions.map((item) => (
              <li key={item}>· {item}</li>
            ))}
          </ul>
        ) : null}
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
