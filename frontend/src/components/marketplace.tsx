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
import { VacancyHints } from "./hints";
import { Button, Card, EmptyState, Field, InfoTip, Modal, SectionNote, StatusBadge, TextArea, gradesLabel, money } from "./ui";

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

      <VacancyHints onApply={setApplyFor} />

      <Modal
        open={applyFor !== null}
        title={applyFor ? `Отклик на «${applyFor.title}»` : "Отклик на вакансию"}
        description="Отклик раскрывает работодателю ваши контакты: вместе с сообщением он увидит email и телефон из профиля."
        onClose={() => setApplyFor(null)}
        footer={
          <>
            <Button onClick={() => void send()} disabled={busy}>
              Отправить отклик
            </Button>
            <Button variant="ghost" onClick={() => setApplyFor(null)}>
              Отмена
            </Button>
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          <AIButton onClick={() => void writeCoverLetter()} busy={aiBusy}>
            Написать сопроводительное
          </AIButton>
          <span className="text-xs text-slate-500">
            письмо соберётся из реального пересечения стека
          </span>
        </div>
        <TextArea label="Сообщение работодателю" value={message} onChange={setMessage} rows={6} />
        <AISourceNote result={aiResult} />
      </Modal>

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
  // Если задано — форма работает в режиме правки уже опубликованной вакансии
  const [editing, setEditing] = useState<string | null>(null);
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

  async function save() {
    setBusy(true);
    const payload = {
      title,
      description,
      specialization_code: specialization,
      grade,
      stack: stack.split(",").map((item) => item.trim()).filter(Boolean),
      salary_from: Number(salaryFrom),
      salary_to: Number(salaryTo),
    };
    try {
      if (editing) {
        await apiClient.updateVacancy(editing, payload);
        toast.success("Вакансия обновлена", "Кандидаты увидят новую редакцию");
      } else {
        await apiClient.publishVacancy(payload);
        toast.success("Вакансия опубликована", "Кандидаты увидят её в разделе «Вакансии»");
      }
      setTitle("");
      setDescription("");
      setBrief("");
      setAiResult(null);
      setEditing(null);
      await load();
    } catch (err) {
      toast.error(editing ? "Не удалось сохранить изменения" : "Не удалось опубликовать вакансию", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  /** Подставляет вакансию в форму — правка идёт через ту же форму, что публикация. */
  function startEditing(vacancy: Vacancy) {
    setEditing(vacancy.id);
    setTitle(vacancy.title);
    setDescription(vacancy.description ?? "");
    setSpecialization(vacancy.specialization_code ?? "");
    setGrade(vacancy.grade ?? "");
    setStack((vacancy.stack ?? []).join(", "));
    setSalaryFrom(String(vacancy.salary_from));
    setSalaryTo(String(vacancy.salary_to));
    setBrief("");
    setAiResult(null);
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
      <SectionNote>
        Вакансия — открытое предложение: кандидат может откликнуться сам. Зарплата обязательна, а
        отклик сразу раскрывает вам контакты кандидата.
      </SectionNote>

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
          <Button onClick={() => void save()} disabled={busy || !title}>
            {editing ? "Сохранить изменения" : "Опубликовать вакансию"}
          </Button>
          {editing ? (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setEditing(null);
                setTitle("");
                setDescription("");
              }}
            >
              Отмена
            </Button>
          ) : null}
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
                    <>
                      <Button variant="ghost" onClick={() => startEditing(vacancy)}>
                        Изменить
                      </Button>
                      <Button variant="danger" onClick={() => void close(vacancy.id)}>
                        Закрыть
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>

            </div>
          ))}
          {vacancies.length === 0 ? (
            <EmptyState
              title="Вы ещё не публиковали вакансии"
              hint="Публикация нужна, чтобы кандидат мог откликнуться сам — это дополнительный сценарий к приглашениям."
            />
          ) : null}
        </div>
      </Card>

      <Modal
        open={openVacancy !== null}
        title={`Отклики: ${vacancies.find((item) => item.id === openVacancy)?.title ?? "вакансия"}`}
        description="Кандидат откликнулся сам — его контакты уже раскрыты, потому что отклик означает согласие на контакт."
        onClose={() => setOpenVacancy(null)}
        wide
      >
        {(openVacancy ? (applications[openVacancy] ?? []) : []).map((application) => (
          <div key={application.id} className="rounded-lg border border-slate-800 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium">
                  #{application.candidate_reference} · {application.candidate_name ?? "кандидат"}
                </p>
                <p className="text-xs text-slate-400">
                  {application.candidate_specialization ?? "—"} / {gradesLabel(application.candidate_grade)}
                  {application.candidate_stack.length ? ` · ${application.candidate_stack.join(", ")}` : ""}
                </p>
                {application.message ? (
                  <p className="mt-2 text-sm text-slate-300">{application.message}</p>
                ) : null}
                {application.contacts_revealed ? (
                  <p className="mt-1 text-xs text-emerald-300">
                    Контакты: {application.candidate_contacts?.email ?? "—"}
                    {application.candidate_contacts?.phone ? ` · ${application.candidate_contacts.phone}` : ""}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-col items-end gap-2">
                <StatusBadge status={application.status} />
                {application.status === "submitted" || application.status === "viewed" ? (
                  <div className="flex gap-2">
                    <Button onClick={() => void decide(application.id, openVacancy ?? "", "accepted")}>
                      Принять
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() => void decide(application.id, openVacancy ?? "", "declined")}
                    >
                      Отклонить
                    </Button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ))}
        {openVacancy && (applications[openVacancy] ?? []).length === 0 ? (
          <EmptyState
            title="Откликов пока нет"
            hint="Кандидаты увидят вакансию в своём кабинете и смогут откликнуться."
          />
        ) : null}
      </Modal>
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
      <SectionNote>
        Короткие задания от работодателей поддерживают профиль в актуальном состоянии: система
        учитывает, как давно вы решали задания, и это влияет на позицию в подборке. Отвечать можно
        текстом — описывать подход, а не только готовый код.
      </SectionNote>

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
            <EmptyState
              title="Пока заданий нет"
              hint="Работодатели публикуют короткие задачи. Когда появится задание под вашу специализацию, оно окажется здесь."
            />
          ) : null}
        </div>
      </Card>

      <Modal
        open={active !== null}
        title={active ? `Решение: ${active.title}` : "Решение задания"}
        description="Отправка решения обновляет дату активности профиля — работодатель видит, что вы работаете с задачами."
        onClose={() => setActive(null)}
        footer={
          <>
            <Button onClick={() => void send()} disabled={busy || solution.trim().length === 0}>
              Отправить решение
            </Button>
            <Button variant="ghost" onClick={() => setActive(null)}>
              Отмена
            </Button>
          </>
        }
      >
        {active?.description ? (
          <p className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-sm text-slate-300">
            {active.description}
          </p>
        ) : null}
        {active ? (
          <p className="text-xs text-slate-400">
            Компания: {active.company_name ?? "не указана"} · уровень: {gradesLabel(active.grade)}
          </p>
        ) : null}
        <TextArea
          label="Решение или подход к решению"
          value={solution}
          onChange={setSolution}
          rows={8}
        />
      </Modal>
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
      <SectionNote>
        Короткое задание — способ поддержать контакт с кандидатами: работодатель видит, кто и как
        решает задачи, а кандидат подтверждает актуальность профиля. Задание можно сформулировать
        вручную или дать платформе собрать черновик по специализации и грейду.
      </SectionNote>

      <Card
        title={
          <>
            Новое задание
            <InfoTip text="Задание увидят кандидаты вашей специализации и уровня, либо все кандидаты, если специализацию не указывать. Решение приходит текстом и попадает в раздел «Решения»." />
          </>
        }
      >
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
            </div>
          ))}
          {tasks.length === 0 ? (
            <EmptyState
              title="Вы ещё не создавали заданий"
              hint="Задания помогают поддерживать контакт с кандидатами и видеть, как они рассуждают."
            />
          ) : null}
        </div>
      </Card>

      <Modal
        open={openTask !== null}
        title="Решения кандидатов"
        description="Решение приходит текстом от кандидата, которому предложено задание."
        onClose={() => setOpenTask(null)}
        wide
      >
        {(openTask ? (submissions[openTask] ?? []) : []).map((submission) => (
          <div key={submission.id} className="rounded-lg border border-slate-800 p-3">
            <p className="text-sm font-medium">
              {submission.candidate_name ?? submission.candidate_reference} ·{" "}
              {gradesLabel(submission.candidate_grade)}
            </p>
            <p className="mt-1 text-sm whitespace-pre-wrap text-slate-300">{submission.solution}</p>
          </div>
        ))}
        {openTask && (submissions[openTask] ?? []).length === 0 ? (
          <EmptyState
            title="Решений пока нет"
            hint="Кандидат увидит задание в своём кабинете и сможет прислать решение — оно появится здесь."
          />
        ) : null}
      </Modal>
    </div>
  );
}
