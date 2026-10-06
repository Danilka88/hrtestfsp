import { useCallback, useEffect, useState } from "react";

import * as apiClient from "../../api/client";
import type { CategoryStatus, FspStatus, TestItem } from "../../api/client";
import { errorMessage } from "../../api/client";
import { AIButton, AISourceNote, aiToastPayload } from "../../components/ai";
import { TasksPanel, VacanciesPanel } from "../../components/marketplace";
import { useToast } from "../../components/toast";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  Field,
  InfoTip,
  Modal,
  SectionNote,
  SelectField,
  StatusBadge,
  TextArea,
  gradesLabel,
  money,
  score,
} from "../../components/ui";
import { useResource, useSpecializations } from "../../api/hooks";
import { VacancyHints } from "../../components/hints";
import { CabinetShell } from "../../components/cabinet";
import { Dashboard, InvitationBars, Kpi } from "../../components/overview";

type Tab = "overview" | "category" | "test" | "invitations" | "vacancies" | "tasks" | "profile";

export function CandidateCabinet() {
  const [tab, setTab] = useState<Tab>("overview");
  // Возврат в незавершённый тест: переносим кандидата в тест на том же задании
  const [resume, setResume] = useState<{ specialization: string; targetGrade: string } | null>(null);

  const continueTest = useCallback((specialization: string, targetGrade: string) => {
    setResume({ specialization, targetGrade });
    setTab("test");
  }, []);

  return (
    <CabinetShell
      title="Кабинет соискателя"
      active={tab}
      onSelect={setTab}
      tabs={
        [
          ["overview", "Обзор"],
          ["category", "Категория и грейд"],
          ["test", "Тестирование"],
          ["invitations", "Приглашения"],
          ["vacancies", "Вакансии"],
          ["tasks", "Задания"],
          ["profile", "Профиль и ФСП"],
        ] as [Tab, string][]
      }
    >

      {tab === "overview" ? <OverviewTab /> : null}
      {tab === "category" ? <CategoryTab onContinueTest={continueTest} /> : null}
      {tab === "test" ? <TestTab resume={resume} onResumeConsumed={() => setResume(null)} /> : null}
      {tab === "invitations" ? <InvitationsTab /> : null}
      {tab === "vacancies" ? <VacanciesPanel role="candidate" /> : null}
      {tab === "tasks" ? <TasksPanel role="candidate" /> : null}
      {tab === "profile" ? <ProfileTab /> : null}
    </CabinetShell>
  );
}

/**
 * Дашборд соискателя: где он находится и что требует внимания.
 *
 * Показатели считаются по уже загруженным данным, ничего не «довыводится»: если
 * чего-то нет, показывается «нет данных», а не ноль.
 */
function OverviewTab() {
  const [profile, setProfile] = useState<apiClient.CandidateProfile | null>(null);
  const [category, setCategory] = useState<CategoryStatus | null>(null);
  const [invitations, setInvitations] = useState<apiClient.CandidateInvitation[]>([]);
  const [applications, setApplications] = useState<apiClient.ApplicationCandidate[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [profileData, categoryData, invitationsData, applicationsData] = await Promise.all([
          apiClient.getCandidateProfile(),
          apiClient.myCategory(),
          apiClient.myInvitations(),
          apiClient.myApplications(),
        ]);
        setProfile(profileData);
        setCategory(categoryData);
        setInvitations(invitationsData);
        setApplications(applicationsData);
      } catch (err) {
        setError(errorMessage(err));
      }
    })();
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!profile || !category) return <p className="text-sm text-slate-500">Загрузка…</p>;

  // Заполненность профиля: знаменатель — длина списка, а не литерал,
  // иначе правка списка полей молча исказит метрику
  const profileFields = [
    Boolean(profile.full_name),
    Boolean(profile.specialization),
    Boolean(profile.grade),
    profile.stack.length > 0,
    profile.roles.length > 0,
    profile.soft_skills.length > 0,
    profile.experience_years !== null,
    Boolean(profile.summary),
  ];
  const filled = profileFields.filter(Boolean).length;
  const completeness = Math.round((filled / profileFields.length) * 100);

  const completed = category.sessions.filter((session) => session.status === "completed");
  const theta = completed.length ? completed[completed.length - 1].theta : null;
  const waiting = invitations.filter(
    (item) => item.status === "sent" || item.status === "viewed",
  ).length;
  const accepted = invitations.filter((item) => item.status === "accepted").length;
  const acceptedApplications = applications.filter((item) => item.status === "accepted").length;

  return (
    <Dashboard
      lead={
        <>
          Коротко о вашем положении: заполненность профиля, присвоенная категория, входящие
          приглашения и собственные отклики. Отсюда видно, чего не хватает, чтобы работодатель
          выходил на контакт.
        </>
      }
      kpis={
        <>
          <Kpi
            label="Профиль заполнен"
            tip="Доля заполненных полей, которые участвуют в подборе: имя, специализация, грейд, стек, роли, soft skills, опыт, о себе. Чем больше заполнено, тем точнее подборка."
            value={`${completeness}%`}
            hint={
              completeness === 100
                ? "все поля заполнены"
                : `заполнено ${filled} из ${profileFields.length} полей`
            }
            tone={completeness === 100 ? "ok" : "warn"}
          />
          <Kpi
            label="Категория"
            tip="Специализация × грейд, присвоенная по результату теста, а не по тексту резюме. Категория определяет, в какие подборки работодателей вы попадаете."
            value={
              category.specialization
                ? `${category.specialization} / ${gradesLabel(category.grade)}`
                : "не присвоена"
            }
            hint={
              category.specialization
                ? "видна работодателям в подборке"
                : "пройдите тестирование — без категории вас не видно"
            }
            tone={category.specialization ? "ok" : "warn"}
          />
          <Kpi
            label="Оценка теста θ"
            tip="Оценка способностей по модели Раша: 0 — средний уровень набора заданий, положительная — выше среднего. Грейд выводится из θ по порогам, а не по числу верных ответов."
            value={theta === null ? "нет данных" : score(theta, 2)}
            hint={theta === null ? "тест ещё не завершён" : "из неё выведен грейд"}
          />
          <Kpi
            label="Приглашения"
            tip="Приглашения работодателей. «Ждут решения» — где выбор за вами, «принято» — где вы согласились. Контакты раскрываются работодателю после вашего решения."
            value={invitations.length}
            hint={`ждут решения: ${waiting} · принято: ${accepted}`}
          />
        </>
      }
      ai={<VacancyHints />}
    >
      <Card title="Входящие приглашения по статусам">
        {invitations.length === 0 ? (
          <p className="text-sm text-slate-400">
            Пока приглашений нет. Они появляются, когда работодатель сам выходит на контакт — это
            основная механика платформы.
          </p>
        ) : (
          <InvitationBars invitations={invitations} />
        )}
      </Card>

      <Card title="Свои отклики">
        <p className="text-sm text-slate-300">
          Всего откликов: {applications.length}
          {applications.length ? ` · принято работодателем: ${acceptedApplications}` : ""}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Отклик — дополнительный сценарий: он раскрывает ваши контакты работодателю.
        </p>
      </Card>
    </Dashboard>
  );
}

function CategoryTab({
  onContinueTest,
}: {
  onContinueTest: (specialization: string, targetGrade: string) => void;
}) {
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
      <SectionNote>
        <b>Категория</b> — это пара «специализация × грейд». Её присваивает платформа по результату
        теста, а не резюме: именно по категории работодатель находит кандидата и приглашает его.
      </SectionNote>

      {status.active_session ? (
        <Alert kind="info">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              У вас <b>незавершённый тест</b> на грейд {gradesLabel(status.active_session.target_grade)}:
              отвечено {status.active_session.items_answered} заданий. Прогресс сохранён — можно
              продолжить с того же задания.
            </span>
            <Button
              onClick={() =>
                onContinueTest(status.specialization ?? "", status.active_session?.target_grade ?? "")
              }
            >
              Продолжить тест
            </Button>
          </div>
        </Alert>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <Card
          title={
            <>
              Специализация
              <InfoTip text="Направление, по которому вы проходите тест. Меняется через новый опрос при следующем тестировании." />
            </>
          }
        >
          <p className="text-lg font-semibold">{status.specialization ?? "не выбрана"}</p>
        </Card>
        <Card
          title={
            <>
              Грейд
              <InfoTip text="Уровень подтверждён тестом. Самооценка и текст резюме на него не влияют — поэтому работодатель доверяет этой категории больше, чем обычному резюме." />
            </>
          }
          accent
        >
          <p className="text-lg font-semibold text-sky-300">{gradesLabel(status.grade)}</p>
          <p className="mt-1 text-xs text-slate-500">определён тестом, не самооценкой</p>
        </Card>
        <Card
          title={
            <>
              Смена грейда
              <InfoTip
                text={`Сменить грейд можно не чаще, чем раз в ${status.grade_change_cooldown_days} дней. Понижение не применяется автоматически: неудача на сложном уровне не отнимает уже подтверждённый грейд — результат остаётся только в истории.`}
              />
            </>
          }
        >
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
        <SectionNote>
          Каждая строка — одна попытка. Статус «в процессе» означает, что тест не доведён до конца:
          его можно продолжить, ответы и прогресс сохраняются.
        </SectionNote>
        {status.sessions.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="py-1 pr-3">Статус</th>
                  <th className="py-1 pr-3">Цель теста</th>
                  <th className="py-1 pr-3">Результат</th>
                  <th className="py-1 pr-3">Заданий</th>
                  <th className="py-1 pr-3">
                    θ
                    <InfoTip text="Оценка уровня подготовки по модели Раша: 0 — средний уровень, больше 0 — выше среднего, меньше 0 — ниже. Грейд выводится именно из неё, а не из числа верных ответов напрямую." />
                  </th>
                  <th className="py-1">Действие</th>
                </tr>
              </thead>
              <tbody>
                {status.sessions.map((session) => (
                  <tr key={session.id} className="border-t border-slate-800">
                    <td className="py-1 pr-3">
                      <StatusBadge status={session.status} />
                    </td>
                    <td className="py-1 pr-3">{gradesLabel(session.target_grade)}</td>
                    <td className="py-1 pr-3">{gradesLabel(session.result_grade)}</td>
                    <td className="py-1 pr-3">{session.items_answered}</td>
                    <td className="py-1 pr-3">{score(session.theta, 2)}</td>
                    <td className="py-1">
                      {session.status === "in_progress" ? (
                        <Button
                          variant="ghost"
                          onClick={() => onContinueTest(status.specialization ?? "", session.target_grade)}
                        >
                          Продолжить
                        </Button>
                      ) : (
                        <span className="text-xs text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="Тестов пока не было"
            hint="Первый тест присваивает грейд: опрос по специализации → выбор уровня → адаптивные задания под ваши ответы."
          />
        )}
      </Card>
    </div>
  );
}

function TestTab({
  resume,
  onResumeConsumed,
}: {
  resume: { specialization: string; targetGrade: string } | null;
  onResumeConsumed: () => void;
}) {
  const specializations = useSpecializations();
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

  // Первую специализацию подставляем, когда справочник загрузился
  useEffect(() => {
    if (specializations.length && !specialization) setSpecialization(specializations[0].code);
  }, [specializations, specialization]);

  // Возврат в незавершённый тест: шаг опроса пропускаем и продолжаем с того же задания.
  useEffect(() => {
    if (!resume || busy || sessionId) return;
    let cancelled = false;
    (async () => {
      setBusy(true);
      setError(null);
      try {
        setSpecialization(resume.specialization);
        setTargetGrade(resume.targetGrade);
        const session = await apiClient.startSession(resume.specialization, resume.targetGrade);
        if (cancelled) return;
        setSessionId(session.session_id);
        setItem(session.item);
        setItemStartedAt(Date.now());
        setResult(null);
        setLastVerdict(null);
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      } finally {
        if (!cancelled) setBusy(false);
        onResumeConsumed();
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- запуск строго один раз на переданный resume
  }, [resume]);

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
      <SectionNote>
        Обязательный путь: <b>опрос</b> по специализации → <b>заявленный грейд</b> → короткий{" "}
        <b>адаптивный тест</b> (10–16 заданий, сложность подстраивается под ваши ответы). Категорию
        платформа считает сама по результату — угадывать уровень не нужно, грейд не понижается за
        неудачную попытку.
      </SectionNote>
      <Card title="Шаг 1. Опрос по отрасли и специализации">
        <div className="flex flex-wrap items-end gap-3">
          <SelectField
            label="Специализация"
            value={specialization}
            onChange={setSpecialization}
            options={specializations.map((item) => ({ value: item.code, label: item.title }))}
          />
          {specializations.length === 0 ? (
            <p className="text-xs text-amber-400">
              Справочник специализаций недоступен или ещё загружается — обновите страницу.
            </p>
          ) : null}
          <Button onClick={() => void startSurvey()} disabled={busy || !specialization}>
            Пройти опрос
          </Button>
        </div>
      </Card>

      {grades.length ? (
        <Card title="Шаг 2. Заявленный грейд и тест">
          <div className="flex flex-wrap items-end gap-3">
            <SelectField
              label="Грейд, на который тестируетесь"
              value={targetGrade}
              onChange={setTargetGrade}
              options={grades.map((code) => ({ value: code, label: gradesLabel(code) }))}
            />
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
              Оценка θ = {score(result.theta)} (ошибка ±{score(result.standard_error)})
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
  const {
    data: invitations,
    error,
    setError,
    reload: load,
  } = useResource(async () => {
    const list = await apiClient.myInvitations();
    // Открытие вкладки означает фактический просмотр: приглашения в статусе
    // «отправлено» переводятся в «просмотрено», чтобы работодатель видел,
    // что приглашение доставлено и открыто, а не проигнорировано.
    return Promise.all(
      list.map(async (invitation) =>
        invitation.status === "sent" ? await apiClient.viewInvitation(invitation.id) : invitation,
      ),
    );
  }, { initial: [] });
  const [busy, setBusy] = useState(false);
  // Подтверждение решения: принятие и отказ необратимы, поэтому спрашиваем явно
  const [confirm, setConfirm] = useState<{ id: string; action: "accepted" | "declined" } | null>(null);

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
      <SectionNote>
        Работодатель нашёл вас по подтверждённой категории. Название компании и зарплата видны{" "}
        <b>до начала общения</b>, а ваши контакты он получит только после принятия — отклик и
        приглашение работают именно так.
      </SectionNote>
      {invitations.length === 0 ? (
        <EmptyState
          title="Входящих приглашений нет"
          hint="Работодатель сам находит кандидатов по категории и подтверждённому профилю — откликаться вслепую не нужно."
        />
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
              {invitation.status === "revoked" ? (
                <p className="mt-1 text-xs text-slate-500">
                  Работодатель отозвал приглашение. Инициативу можно проявить самому — откликнуться на
                  вакансии в разделе «Вакансии».
                </p>
              ) : null}
            </div>
            <div className="flex flex-col items-end gap-2">
              <StatusBadge status={invitation.status} />
              {invitation.status === "sent" || invitation.status === "viewed" ? (
                <div className="flex gap-2">
                  <Button
                    disabled={busy}
                    onClick={() => setConfirm({ id: invitation.id, action: "accepted" })}
                  >
                    Принять
                  </Button>
                  <Button
                    variant="danger"
                    disabled={busy}
                    onClick={() => setConfirm({ id: invitation.id, action: "declined" })}
                  >
                    Отклонить
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        </Card>
      ))}

      <Modal
        open={confirm !== null}
        title={confirm?.action === "accepted" ? "Принять приглашение?" : "Отклонить приглашение?"}
        description={
          confirm?.action === "accepted"
            ? "Работодатель получит ваши контакты и сможет связаться напрямую. Решение окончательное — изменить его потом нельзя."
            : "Приглашение закроется, и работодатель не получит ваши контакты. Решение окончательное — вернуться к нему потом нельзя."
        }
        onClose={() => setConfirm(null)}
        footer={
          <>
            <Button
              variant={confirm?.action === "accepted" ? "primary" : "danger"}
              disabled={busy}
              onClick={() => {
                if (confirm) void decide(confirm.id, confirm.action);
              }}
            >
              {confirm?.action === "accepted" ? "Принять" : "Отклонить"}
            </Button>
            <Button variant="ghost" onClick={() => setConfirm(null)}>
              Отмена
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-400">
          Это действие нельзя отменить: решение по приглашению фиксируется один раз.
        </p>
      </Modal>
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
      setGrade(profile.declared_grade ?? "");
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
        declared_grade: grade || null,
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
