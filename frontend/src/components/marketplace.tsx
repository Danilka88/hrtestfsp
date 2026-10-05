import { useCallback, useEffect, useState } from "react";

import * as apiClient from "../api/client";
import type {
  ApplicationCandidate,
  ApplicationEmployer,
  RegularTask,
  Specialization,
  TaskSubmission,
  Vacancy,
} from "../api/client";
import { errorMessage } from "../api/client";
import { AIButton, AISourceNote, aiToastPayload } from "./ai";
import { useToast } from "./toast";
import { Alert, Button, Card, Field, StatusBadge, TextArea, gradesLabel, money } from "./ui";

/**
 * Панели дополнительного функционала: вакансии с откликами и регулярные короткие
 * задания. Обе роли работают в одном компоненте, потому что предметная область
 * одна — различаются только доступные действия.
 */

type Role = "candidate" | "employer";

// --- Вакансии ---------------------------------------------------------------

export function VacanciesPanel({ role }: { role: Role }) {
  return role === "employer" ? <EmployerVacancies /> : <CandidateVacancies />;
}

function CandidateVacancies() {
  const toast = useToast();
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [specialization, setSpecialization] = useState("");
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [applications, setApplications] = useState<ApplicationCandidate[]>([]);
  const [applyFor, setApplyFor] = useState<Vacancy | null>(null);
  const [message, setMessage] = useState("");
  const [aiResult, setAiResult] = useState<apiClient.AIResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [open, mine] = await Promise.all([
        apiClient.listOpenVacancies(specialization || undefined),
        apiClient.myApplications(),
      ]);
      setVacancies(open);
      setApplications(mine);
    } catch (err) {
      toast.error("Не удалось загрузить вакансии", errorMessage(err));
    }
  }, [specialization, toast]);

  useEffect(() => {
    apiClient
      .listSpecializations()
      .then(setSpecializations)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const appliedIds = new Set(applications.map((item) => item.vacancy_id));

  async function writeCoverLetter() {
    if (!applyFor) return;
    setAiBusy(true);
    setAiResult(null);
    try {
      const profile = await apiClient.getCandidateProfile();
      const result = await apiClient.aiCoverLetter({
        vacancy_title: applyFor.title,
        company: applyFor.company_name ?? "компания",
        required_stack: applyFor.stack,
        candidate_stack: profile.stack ?? [],
        candidate_grade: profile.grade,
      });
      setAiResult(result);
      const letter = String((result.data as { letter?: string }).letter ?? "");
      if (letter) setMessage(letter);
      const payload = aiToastPayload(result, "Сопроводительное письмо готово");
      toast.push(payload.kind, payload.text, payload.detail);
    } catch (err) {
      toast.error("Не удалось подготовить письмо", errorMessage(err));
    } finally {
      setAiBusy(false);
    }
  }

  async function send() {
    if (!applyFor) return;
    setBusy(true);
    try {
      await apiClient.applyToVacancy(applyFor.id, message);
      toast.success("Отклик отправлен", "Работодатель видит ваши контакты: вы проявили инициативу сами");
      setApplyFor(null);
      setMessage("");
      setAiResult(null);
      await load();
    } catch (err) {
      toast.error("Отклик не отправлен", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Открытые вакансии">
        <p className="mb-3 text-xs text-slate-500">
          Дополнительный сценарий: если приглашений пока нет, кандидат может проявить инициативу
          сам. Контакты при этом раскрываются работодателю.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-slate-400">Специализация</span>
            <select
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
              value={specialization}
              onChange={(event) => setSpecialization(event.target.value)}
            >
              <option value="">Все</option>
              {specializations.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <Button variant="ghost" onClick={() => void load()}>
            Обновить
          </Button>
        </div>

        <div className="mt-4 space-y-3">
          {vacancies.map((vacancy) => (
            <div key={vacancy.id} className="rounded-lg border border-slate-800 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{vacancy.title}</p>
                  <p className="text-xs text-slate-400">
                    {vacancy.company_name ?? "компания"} · {vacancy.specialization_code ?? "—"} /{" "}
                    {gradesLabel(vacancy.grade)} · {money(vacancy.salary_from)} – {money(vacancy.salary_to)}
                  </p>
                  {vacancy.stack.length ? (
                    <p className="mt-1 text-xs text-slate-500">{vacancy.stack.join(", ")}</p>
                  ) : null}
                  {vacancy.description ? (
                    <p className="mt-2 max-w-2xl text-sm text-slate-300">{vacancy.description}</p>
                  ) : null}
                </div>
                <div className="flex flex-col items-end gap-2">
                  {appliedIds.has(vacancy.id) ? (
                    <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs text-emerald-300">
                      отклик отправлен
                    </span>
                  ) : (
                    <Button
                      onClick={() => {
                        setApplyFor(vacancy);
                        setMessage("");
                        setAiResult(null);
                      }}
                    >
                      Откликнуться
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {vacancies.length === 0 ? (
            <p className="text-sm text-slate-500">Открытых вакансий пока нет.</p>
          ) : null}
        </div>
      </Card>

      {applyFor ? (
        <Card title={`Отклик на «${applyFor.title}»`} accent>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <AIButton onClick={() => void writeCoverLetter()} busy={aiBusy}>
              Написать сопроводительное
            </AIButton>
            <span className="text-xs text-slate-500">
              письмо соберётся из реального пересечения стека
            </span>
          </div>
          <TextArea label="Сообщение работодателю" value={message} onChange={setMessage} rows={5} />
          <AISourceNote result={aiResult} />
          <div className="mt-3 flex gap-2">
            <Button onClick={() => void send()} disabled={busy}>
              Отправить отклик
            </Button>
            <Button variant="ghost" onClick={() => setApplyFor(null)}>
              Отмена
            </Button>
          </div>
        </Card>
      ) : null}

      <Card title={`Мои отклики · ${applications.length}`}>
        <div className="space-y-2">
          {applications.map((application) => (
            <div
              key={application.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 p-3"
            >
              <div>
                <p className="text-sm font-medium">{application.vacancy_title ?? "Вакансия"}</p>
                <p className="text-xs text-slate-500">{application.company_name ?? "компания"}</p>
              </div>
              <StatusBadge status={application.status} />
            </div>
          ))}
          {applications.length === 0 ? (
            <p className="text-sm text-slate-500">Вы ещё не откликались на вакансии.</p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

function EmployerVacancies() {
  const toast = useToast();
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [brief, setBrief] = useState("");
  const [specialization, setSpecialization] = useState("backend");
  const [grade, setGrade] = useState("middle");
  const [stack, setStack] = useState("");
  const [salaryFrom, setSalaryFrom] = useState("250000");
  const [salaryTo, setSalaryTo] = useState("320000");
  const [applications, setApplications] = useState<Record<string, ApplicationEmployer[]>>({});
  const [openVacancy, setOpenVacancy] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiResult, setAiResult] = useState<apiClient.AIResult | null>(null);

  const load = useCallback(async () => {
    try {
      setVacancies(await apiClient.listMyVacancies());
    } catch (err) {
      toast.error("Не удалось загрузить вакансии", errorMessage(err));
    }
  }, [toast]);

  useEffect(() => {
    apiClient
      .listSpecializations()
      .then(setSpecializations)
      .catch(() => undefined);
    void load();
  }, [load]);

  async function draft() {
    setAiBusy(true);
    setAiResult(null);
    try {
      const result = await apiClient.aiTaskDraft({ need_title: brief || "вакансия", stack: [] });
      setAiResult(result);
      const payload = aiToastPayload(result, "Черновик описания готов");
      toast.push(payload.kind, payload.text, payload.detail);
      const statement = String((result.data as { statement?: string }).statement ?? "");
      if (statement && !description) setDescription(statement);
      if (brief && !title) setTitle(brief.slice(0, 80));
    } catch (err) {
      toast.error("Не удалось собрать черновик", errorMessage(err));
    } finally {
      setAiBusy(false);
    }
  }

  async function publish() {
    setBusy(true);
    try {
      await apiClient.publishVacancy({
        title,
        description,
        specialization_code: specialization,
        grade,
        stack: stack.split(",").map((item) => item.trim()).filter(Boolean),
        salary_from: Number(salaryFrom),
        salary_to: Number(salaryTo),
      });
      toast.success("Вакансия опубликована", "Кандидаты увидят её в разделе «Вакансии»");
      setTitle("");
      setDescription("");
      setBrief("");
      setAiResult(null);
      await load();
    } catch (err) {
      toast.error("Не удалось опубликовать вакансию", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function loadApplications(vacancyId: string) {
    try {
      const rows = await apiClient.vacancyApplications(vacancyId);
      setApplications((prev) => ({ ...prev, [vacancyId]: rows }));
      setOpenVacancy(vacancyId);
    } catch (err) {
      toast.error("Не удалось загрузить отклики", errorMessage(err));
    }
  }

  async function decide(applicationId: string, vacancyId: string, status: "accepted" | "declined") {
    try {
      await apiClient.decideApplication(applicationId, status);
      toast.success(status === "accepted" ? "Отклик принят" : "Отклик отклонён");
      await loadApplications(vacancyId);
    } catch (err) {
      toast.error("Не удалось изменить статус отклика", errorMessage(err));
    }
  }

  async function close(vacancyId: string) {
    try {
      await apiClient.closeVacancy(vacancyId);
      toast.success("Вакансия закрыта");
      await load();
    } catch (err) {
      toast.error("Не удалось закрыть вакансию", errorMessage(err));
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Публикация вакансии">
        <p className="mb-3 text-xs text-slate-500">
          Вакансия с обязательной зарплатой. Кандидат видит условия до начала общения.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Название вакансии" value={title} onChange={setTitle} />
          <Field label="Стек (через запятую)" value={stack} onChange={setStack} />
          <label className="text-sm">
            <span className="mb-1 block text-slate-400">Специализация</span>
            <select
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
              value={specialization}
              onChange={(event) => setSpecialization(event.target.value)}
            >
              {specializations.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.title}
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
          <Field label="Зарплата от, ₽" value={salaryFrom} onChange={setSalaryFrom} />
          <Field label="Зарплата до, ₽" value={salaryTo} onChange={setSalaryTo} />
        </div>
        <div className="mt-3">
          <TextArea label="Описание вакансии" value={description} onChange={setDescription} rows={3} />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Field label="Коротко: кого ищете (для ИИ)" value={brief} onChange={setBrief} />
          <AIButton onClick={() => void draft()} busy={aiBusy} title="Собрать черновик описания">
            Собрать описание
          </AIButton>
        </div>
        <AISourceNote result={aiResult} />
        <div className="mt-3">
          <Button onClick={() => void publish()} disabled={busy || !title}>
            Опубликовать вакансию
          </Button>
        </div>
      </Card>

      <Card title={`Мои вакансии · ${vacancies.length}`}>
        <div className="space-y-3">
          {vacancies.map((vacancy) => (
            <div key={vacancy.id} className="rounded-lg border border-slate-800 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {vacancy.title} <StatusBadge status={vacancy.status} />
                  </p>
                  <p className="text-xs text-slate-400">
                    {gradesLabel(vacancy.grade)} · {money(vacancy.salary_from)} – {money(vacancy.salary_to)}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" onClick={() => void loadApplications(vacancy.id)}>
                    Отклики
                  </Button>
                  {vacancy.status === "published" ? (
                    <Button variant="danger" onClick={() => void close(vacancy.id)}>
                      Закрыть
                    </Button>
                  ) : null}
                </div>
              </div>

              {openVacancy === vacancy.id ? (
                <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
                  {(applications[vacancy.id] ?? []).map((application) => (
                    <div key={application.id} className="rounded-lg border border-slate-800 p-2">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium">
                            #{application.candidate_reference} · {application.candidate_name ?? "кандидат"}
                          </p>
                          <p className="text-xs text-slate-400">
                            {application.candidate_specialization ?? "—"} /{" "}
                            {gradesLabel(application.candidate_grade)}
                            {application.candidate_stack.length
                              ? ` · ${application.candidate_stack.join(", ")}`
                              : ""}
                          </p>
                          {application.message ? (
                            <p className="mt-1 max-w-xl text-sm text-slate-300">{application.message}</p>
                          ) : null}
                          {application.contacts_revealed ? (
                            <p className="mt-1 text-xs text-emerald-300">
                              Контакты открыты: {application.candidate_contacts?.email ?? "—"}
                              {application.candidate_contacts?.phone
                                ? ` · ${application.candidate_contacts.phone}`
                                : ""}
                            </p>
                          ) : (
                            <p className="mt-1 text-xs text-slate-600">Контакты скрыты</p>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <StatusBadge status={application.status} />
                          {application.status === "submitted" || application.status === "viewed" ? (
                            <div className="flex gap-2">
                              <Button
                                onClick={() => void decide(application.id, vacancy.id, "accepted")}
                              >
                                Принять
                              </Button>
                              <Button
                                variant="danger"
                                onClick={() => void decide(application.id, vacancy.id, "declined")}
                              >
                                Отклонить
                              </Button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))}
                  {(applications[vacancy.id] ?? []).length === 0 ? (
                    <p className="text-sm text-slate-500">Откликов на вакансию пока нет.</p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
          {vacancies.length === 0 ? (
            <p className="text-sm text-slate-500">Вы ещё не публиковали вакансии.</p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

// --- Регулярные короткие задания --------------------------------------------

export function TasksPanel({ role }: { role: Role }) {
  return role === "employer" ? <EmployerTasks /> : <CandidateTasks />;
}

function CandidateTasks() {
  const toast = useToast();
  const [tasks, setTasks] = useState<RegularTask[]>([]);
  const [active, setActive] = useState<RegularTask | null>(null);
  const [solution, setSolution] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setTasks(await apiClient.offeredTasks());
    } catch (err) {
      toast.error("Не удалось загрузить задания", errorMessage(err));
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  async function send() {
    if (!active) return;
    setBusy(true);
    try {
      await apiClient.submitTask(active.id, solution);
      toast.success("Решение отправлено", "Задание обновляет актуальность вашего профиля");
      setActive(null);
      setSolution("");
      await load();
    } catch (err) {
      toast.error("Не удалось отправить решение", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Alert kind="info">
        Регулярные короткие задания поддерживают профиль в актуальном состоянии: работодатель
        видит свежий сигнал о ваших навыках.
      </Alert>

      <Card title={`Задания от работодателей · ${tasks.length}`}>
        <div className="space-y-3">
          {tasks.map((task) => (
            <div key={task.id} className="rounded-lg border border-slate-800 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{task.title}</p>
                  <p className="text-xs text-slate-400">
                    {task.company_name ?? "компания"} · {gradesLabel(task.grade)}
                  </p>
                  {task.description ? (
                    <p className="mt-2 max-w-2xl text-sm text-slate-300">{task.description}</p>
                  ) : null}
                </div>
                <Button onClick={() => setActive(task)}>Решить</Button>
              </div>
            </div>
          ))}
          {tasks.length === 0 ? (
            <p className="text-sm text-slate-500">Пока заданий нет.</p>
          ) : null}
        </div>
      </Card>

      {active ? (
        <Card title={`Решение: ${active.title}`} accent>
          <TextArea
            label="Решение или подход к решению"
            value={solution}
            onChange={setSolution}
            rows={6}
          />
          <div className="mt-3 flex gap-2">
            <Button onClick={() => void send()} disabled={busy || solution.trim().length === 0}>
              Отправить решение
            </Button>
            <Button variant="ghost" onClick={() => setActive(null)}>
              Отмена
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function EmployerTasks() {
  const toast = useToast();
  const [specializations, setSpecializations] = useState<Specialization[]>([]);
  const [tasks, setTasks] = useState<RegularTask[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [specialization, setSpecialization] = useState("backend");
  const [grade, setGrade] = useState("middle");
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiResult, setAiResult] = useState<apiClient.AIResult | null>(null);
  const [submissions, setSubmissions] = useState<Record<string, TaskSubmission[]>>({});
  const [openTask, setOpenTask] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setTasks(await apiClient.listMyTasks());
    } catch (err) {
      toast.error("Не удалось загрузить задания", errorMessage(err));
    }
  }, [toast]);

  useEffect(() => {
    apiClient
      .listSpecializations()
      .then(setSpecializations)
      .catch(() => undefined);
    void load();
  }, [load]);

  async function draft() {
    setAiBusy(true);
    setAiResult(null);
    try {
      const result = await apiClient.aiTaskDraft({
        need_title: title || "ИТ-специалист",
        stack: [],
        grade,
      });
      setAiResult(result);
      const payload = aiToastPayload(result, "Задание предложено моделью");
      toast.push(payload.kind, payload.text, payload.detail);
      const data = result.data as { title?: string; statement?: string };
      if (data.title && !title) setTitle(data.title);
      if (data.statement && !description) setDescription(data.statement);
    } catch (err) {
      toast.error("Не удалось подготовить задание", errorMessage(err));
    } finally {
      setAiBusy(false);
    }
  }

  async function create() {
    setBusy(true);
    try {
      await apiClient.createTask({ title, description, specialization_code: specialization, grade });
      toast.success("Задание создано", "Кандидаты увидят его в своём кабинете");
      setTitle("");
      setDescription("");
      setAiResult(null);
      await load();
    } catch (err) {
      toast.error("Не удалось создать задание", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function openSubmissions(taskId: string) {
    try {
      const rows = await apiClient.taskSubmissions(taskId);
      setSubmissions((prev) => ({ ...prev, [taskId]: rows }));
      setOpenTask(taskId);
    } catch (err) {
      toast.error("Не удалось загрузить решения", errorMessage(err));
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Новое короткое задание">
        <p className="mb-3 text-xs text-slate-500">
          Задание до 20 минут: проверяет практическое мышление. Модель может предложить заготовку —
          её можно отредактировать перед публикацией.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Название задания" value={title} onChange={setTitle} />
          <label className="text-sm">
            <span className="mb-1 block text-slate-400">Специализация</span>
            <select
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
              value={specialization}
              onChange={(event) => setSpecialization(event.target.value)}
            >
              {specializations.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.title}
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
        </div>
        <div className="mt-3">
          <TextArea label="Формулировка задания" value={description} onChange={setDescription} rows={4} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={() => void create()} disabled={busy || !title}>
            Создать задание
          </Button>
          <AIButton onClick={() => void draft()} busy={aiBusy}>
            Предложить задание
          </AIButton>
        </div>
        <AISourceNote result={aiResult} />
      </Card>

      <Card title={`Мои задания · ${tasks.length}`}>
        <div className="space-y-3">
          {tasks.map((task) => (
            <div key={task.id} className="rounded-lg border border-slate-800 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {task.title} <StatusBadge status={task.status} />
                  </p>
                  <p className="text-xs text-slate-400">
                    {gradesLabel(task.grade)}
                    {task.description ? ` · ${task.description.slice(0, 120)}` : ""}
                  </p>
                </div>
                <Button variant="ghost" onClick={() => void openSubmissions(task.id)}>
                  Решения
                </Button>
              </div>

              {openTask === task.id ? (
                <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
                  {(submissions[task.id] ?? []).map((submission) => (
                    <div key={submission.id} className="rounded-lg border border-slate-800 p-2">
                      <p className="text-sm font-medium">
                        {submission.candidate_name ?? submission.candidate_reference} ·{" "}
                        {gradesLabel(submission.candidate_grade)}
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-300">
                        {submission.solution}
                      </p>
                    </div>
                  ))}
                  {(submissions[task.id] ?? []).length === 0 ? (
                    <p className="text-sm text-slate-500">Решений пока нет.</p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
          {tasks.length === 0 ? (
            <p className="text-sm text-slate-500">Вы ещё не создавали заданий.</p>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
