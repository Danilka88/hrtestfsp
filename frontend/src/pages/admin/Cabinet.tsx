import { useCallback, useEffect, useMemo, useState } from "react";

import * as apiClient from "../../api/client";
import type {
  AdminAnomaly,
  AdminCategory,
  AdminCompany,
  AdminInteraction,
  AdminOverview,
} from "../../api/client";
import { errorMessage } from "../../api/client";
import { AISourceNote } from "../../components/ai";
import { Alert, Button, Card, EmptyState, InfoTip, SectionNote, score } from "../../components/ui";
import { useToast } from "../../components/toast";

type Tab = "overview" | "graph" | "categories" | "companies" | "signals" | "ai";

const TABS: [Tab, string][] = [
  ["overview", "Обзор"],
  ["graph", "Схема взаимодействия"],
  ["categories", "Категории"],
  ["companies", "Компании"],
  ["signals", "Сигналы"],
  ["ai", "ИИ-сводка"],
];

const STATUS_COLORS: Record<string, string> = {
  sent: "#38bdf8",
  viewed: "#fbbf24",
  accepted: "#34d399",
  declined: "#fb7185",
  revoked: "#64748b",
};

const STATUS_LABELS: Record<string, string> = {
  sent: "отправлено",
  viewed: "просмотрено",
  accepted: "принято",
  declined: "отклонено",
  revoked: "отозвано",
};

export function AdminCabinet() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Кабинет администратора</h1>
          <p className="mt-1 text-sm text-slate-400">
            Наблюдение за платформой как за двусторонним рынком: обе стороны, их взаимодействие и
            узкие места.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map(([key, label]) => (
          <Button
            key={key}
            variant={tab === key ? "primary" : "ghost"}
            onClick={() => setTab(key)}
          >
            {label}
          </Button>
        ))}
      </div>

      {tab === "overview" ? <OverviewTab /> : null}
      {tab === "graph" ? <GraphTab /> : null}
      {tab === "categories" ? <CategoriesTab /> : null}
      {tab === "companies" ? <CompaniesTab /> : null}
      {tab === "signals" ? <SignalsTab /> : null}
      {tab === "ai" ? <AiTab /> : null}
    </div>
  );
}

/** Доля в процентах; отсутствие данных — «нет данных», а не «0%». */
function Percent({ value }: { value: number | null }) {
  if (value === null || value === undefined) {
    return <span className="text-slate-500">нет данных</span>;
  }
  return <span>{value}%</span>;
}

function OverviewTab() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await apiClient.adminOverview());
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p className="text-sm text-slate-400">Загружаю показатели…</p>;

  const maxStage = Math.max(...data.funnel.map((stage) => stage.value), 1);

  return (
    <div className="space-y-4">
      <SectionNote>
        Метрики двустороннего рынка: важно не число пользователей, а находят ли стороны друг друга.
        Поэтому основной набор — воронка пути кандидата, ликвидность (сколько потребностей доходит до
        приглашения) и время до первого ответа.
      </SectionNote>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs text-slate-400">Соискатели</p>
          <p className="mt-1 text-2xl font-semibold">{data.people.candidates}</p>
          <p className="text-xs text-slate-500">
            активны за 30 дней: {data.people.active_candidates}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">Компании</p>
          <p className="mt-1 text-2xl font-semibold">{data.people.employers}</p>
          <p className="text-xs text-slate-500">
            выходили на контакт: {data.people.active_employers}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">
            Соискателей на компанию{" "}
            <InfoTip text="Соотношение сторон. Сильный перекос означает, что одной стороне платформа полезна меньше: при избытке соискателей компании не успевают отвечать, при недостатке — кандидаты не находят вариантов." />
          </p>
          <p className="mt-1 text-2xl font-semibold">
            {data.people.candidate_employer_ratio ?? "нет данных"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">С достижениями ФСП</p>
          <p className="mt-1 text-2xl font-semibold">{data.coverage.with_fsp}</p>
          <p className="text-xs text-slate-500">
            <Percent value={data.coverage.fsp_share} /> от соискателей
          </p>
        </Card>
      </div>

      <Card title="Путь кандидата: где отваливаются">
        <SectionNote>
          Обязательный путь продукта: регистрация → профиль → тест → категория → приглашение →
          ответ. Ступень с самым большим провалом показывает, что мешает людям дойти до контакта.
        </SectionNote>
        <div className="mt-3 space-y-2">
          {data.funnel.map((stage, index) => (
            <div key={stage.key}>
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{stage.title}</span>
                <span className="text-slate-400">
                  {stage.value} чел. · <Percent value={stage.share} />
                  {index > 0 ? (
                    <span className="ml-2 text-xs text-slate-500">
                      шаг: <Percent value={stage.share === null ? null : Math.round(stage.share)} />
                    </span>
                  ) : null}
                </span>
              </div>
              <div className="mt-1 h-2 rounded bg-slate-800">
                <div
                  className="h-2 rounded bg-sky-500/70"
                  style={{ width: `${Math.max(2, (stage.value / maxStage) * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">{stage.hint}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Ликвидность рынка">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="text-xs text-slate-400">
              Потребности → подборка{" "}
              <InfoTip text="Доля запросов работодателей, по которым система смогла построить подборку. Низкая доля означает, что в описанных категориях нет кандидатов." />
            </p>
            <p className="text-lg">
              <Percent value={data.liquidity.selection_rate} />{" "}
              <span className="text-xs text-slate-500">
                ({data.liquidity.needs_with_selection} из {data.liquidity.needs_total})
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">
              Потребности → приглашение{" "}
              <InfoTip text="Доля запросов, которые дошли до реального контакта. Это главный показатель того, что механика работает, а не просто существует." />
            </p>
            <p className="text-lg">
              <Percent value={data.liquidity.contact_rate} />{" "}
              <span className="text-xs text-slate-500">
                ({data.liquidity.needs_with_invitation} из {data.liquidity.needs_total})
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Приглашений с решением кандидата</p>
            <p className="text-lg">
              <Percent value={data.liquidity.response_rate} />{" "}
              <span className="text-xs text-slate-500">
                ({data.liquidity.invitations_answered} из {data.liquidity.invitations_total})
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Приглашения приняты</p>
            <p className="text-lg">
              <Percent value={data.liquidity.accept_rate} />{" "}
              <span className="text-xs text-slate-500">({data.liquidity.invitations_accepted})</span>
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">
              Время до первого ответа{" "}
              <InfoTip text="Медиана часов от отправки приглашения до решения кандидата. Эту задержку чувствует кандидат, и она определяет, считает ли он платформу живой." />
            </p>
            <p className="text-lg">
              {data.liquidity.response_hours_median === null ? (
                <span className="text-slate-500">нет данных</span>
              ) : (
                `${data.liquidity.response_hours_median} ч`
              )}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Приглашения без ответа дольше недели</p>
            <p className="text-lg">{data.liquidity.invitations_stale}</p>
          </div>
        </div>
      </Card>

      <Card title="Дополнительный функционал">
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <p className="text-xs text-slate-400">Открытых вакансий</p>
            <p className="text-lg">{data.coverage.vacancies_open}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Откликов на вакансии</p>
            <p className="text-lg">{data.coverage.applications_total}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Регулярных заданий</p>
            <p className="text-lg">{data.coverage.tasks_total}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

function GraphTab() {
  const [data, setData] = useState<AdminInteraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [only, setOnly] = useState<string>("all");

  const load = useCallback(async () => {
    try {
      setData(await apiClient.adminInteractions(80));
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const edges = useMemo(() => {
    if (!data) return [];
    return only === "all" ? data.edges : data.edges.filter((edge) => edge.status === only);
  }, [data, only]);

  const activeEmployers = useMemo(() => {
    if (!data) return [];
    const ids = new Set(edges.map((edge) => edge.employer_id));
    return data.employers.filter((item) => ids.has(item.id));
  }, [edges, data]);

  const activeCandidates = useMemo(() => {
    if (!data) return [];
    const ids = new Set(edges.map((edge) => edge.candidate_id));
    return data.candidates.filter((item) => ids.has(item.id));
  }, [edges, data]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p className="text-sm text-slate-400">Строю схему…</p>;

  if (!data.edges.length) {
    return (
      <EmptyState
        title="Взаимодействий пока нет"
        hint="Схема заполняется приглашениями: как только работодатель выходит на контакт с кандидатом, между ними появляется связь."
      />
    );
  }

  const rowHeight = 52;
  const leftX = 8;
  const rightX = 660;
  const width = 900;
  const height = Math.max(activeEmployers.length, activeCandidates.length) * rowHeight + 40;

  const employerY = new Map(activeEmployers.map((item, index) => [item.id, 30 + index * rowHeight]));
  const candidateY = new Map(
    activeCandidates.map((item, index) => [item.id, 30 + index * rowHeight]),
  );

  return (
    <div className="space-y-4">
      <SectionNote>
        Кто с кем взаимодействует. Слева — компании, справа — соискатели; линия — приглашение, цвет
        линии — статус. Так видно и активные компании, и тех, кто получил ответ, и отозванные
        предложения.
      </SectionNote>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant={only === "all" ? "primary" : "ghost"} onClick={() => setOnly("all")}>
          Все связи
        </Button>
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <Button key={key} variant={only === key ? "primary" : "ghost"} onClick={() => setOnly(key)}>
            <span
              className="mr-1 inline-block h-2 w-2 rounded-full"
              style={{ background: STATUS_COLORS[key] }}
            />
            {label}
          </Button>
        ))}
      </div>

      <Card>
        <div className="overflow-x-auto">
          <svg width={width} height={height} role="img" aria-label="Схема взаимодействия">
            <text x={leftX} y={16} className="fill-slate-400" fontSize="11">
              КОМПАНИИ
            </text>
            <text x={rightX} y={16} className="fill-slate-400" fontSize="11">
              СОИСКАТЕЛИ
            </text>

            {edges.map((edge) => {
              const y1 = employerY.get(edge.employer_id);
              const y2 = candidateY.get(edge.candidate_id);
              if (y1 === undefined || y2 === undefined) return null;
              const x1 = leftX + 190;
              const x2 = rightX - 10;
              const mid = (x1 + x2) / 2;
              return (
                <path
                  key={edge.id}
                  d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                  stroke={STATUS_COLORS[edge.status] ?? "#64748b"}
                  strokeWidth={edge.status === "accepted" ? 2.5 : 1.5}
                  fill="none"
                  opacity={edge.status === "revoked" ? 0.5 : 0.9}
                />
              );
            })}

            {activeEmployers.map((item) => {
              const y = employerY.get(item.id) ?? 0;
              return (
                <g key={item.id}>
                  <rect
                    x={leftX}
                    y={y - 14}
                    width={190}
                    height={28}
                    rx={7}
                    fill="rgba(56,189,248,0.12)"
                    stroke="#2e4070"
                  />
                  <text x={leftX + 8} y={y + 4} fontSize="11.5" className="fill-slate-100">
                    {item.label.length > 26 ? `${item.label.slice(0, 25)}…` : item.label}
                  </text>
                </g>
              );
            })}

            {activeCandidates.map((item) => {
              const y = candidateY.get(item.id) ?? 0;
              return (
                <g key={item.id}>
                  <rect
                    x={rightX - 10}
                    y={y - 14}
                    width={230}
                    height={28}
                    rx={7}
                    fill="rgba(52,211,153,0.10)"
                    stroke="#2e4070"
                  />
                  <text x={rightX} y={y + 4} fontSize="11.5" className="fill-slate-100">
                    {(item.label.length > 22 ? `${item.label.slice(0, 21)}…` : item.label) +
                      (item.specialization ? ` · ${item.specialization}` : "")}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-400">
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <span key={key} className="inline-flex items-center gap-1">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: STATUS_COLORS[key] }}
              />
              {label}
            </span>
          ))}
        </div>
        {data.truncated ? (
          <p className="mt-2 text-xs text-slate-500">
            Показаны последние связи — схема ограничена, чтобы оставаться читаемой.
          </p>
        ) : null}
      </Card>
    </div>
  );
}

function CategoriesTab() {
  const [rows, setRows] = useState<AdminCategory[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setRows(await apiClient.adminCategories());
      } catch (err) {
        setError(errorMessage(err));
      }
    })();
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;

  if (!rows.length) {
    return (
      <EmptyState
        title="Категорий пока нет"
        hint="Категории появляются, когда кандидаты проходят тест, а работодатели описывают потребности."
      />
    );
  }

  const maxCandidates = Math.max(...rows.map((row) => row.candidates), 1);

  return (
    <div className="space-y-4">
      <SectionNote>
        Сбалансированность рынка по связке «специализация × грейд». Если спрос есть, а кандидатов нет —
        платформа не может помочь и туда нужно направлять привлечение соискателей.
      </SectionNote>
      <div className="tw overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400">
              <th className="py-2 pr-3">Категория</th>
              <th className="py-2 pr-3">Грейд</th>
              <th className="py-2 pr-3">Кандидаты</th>
              <th className="py-2 pr-3">Потребности</th>
              <th className="py-2 pr-3">Приглашения</th>
              <th className="py-2 pr-3">Состояние</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.specialization}-${row.grade ?? "any"}`} className="border-t border-slate-800">
                <td className="py-2 pr-3">{row.specialization_title}</td>
                <td className="py-2 pr-3">{row.grade ?? "не указан"}</td>
                <td className="py-2 pr-3">
                  <div className="flex items-center gap-2">
                    <span className="w-8">{row.candidates}</span>
                    <span className="h-1.5 w-24 rounded bg-slate-800">
                      <span
                        className="block h-1.5 rounded bg-emerald-500/70"
                        style={{ width: `${Math.max(2, (row.candidates / maxCandidates) * 100)}%` }}
                      />
                    </span>
                  </div>
                </td>
                <td className="py-2 pr-3">{row.needs}</td>
                <td className="py-2 pr-3">{row.invitations}</td>
                <td className="py-2 pr-3">
                  <span
                    className={
                      row.balance === "дефицит"
                        ? "text-amber-300"
                        : row.balance === "переизбыток"
                          ? "text-sky-300"
                          : row.balance === "нет спроса"
                            ? "text-slate-500"
                            : "text-emerald-300"
                    }
                  >
                    {row.balance}
                  </span>
                  {row.supply_per_need !== null ? (
                    <span className="ml-2 text-xs text-slate-500">
                      {score(row.supply_per_need, 2)} на запрос
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CompaniesTab() {
  const [rows, setRows] = useState<AdminCompany[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setRows(await apiClient.adminCompanies());
      } catch (err) {
        setError(errorMessage(err));
      }
    })();
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;

  if (!rows.length) {
    return <EmptyState title="Компаний пока нет" hint="Здесь появится активность работодателей." />;
  }

  return (
    <div className="space-y-4">
      <SectionNote>
        Активность компаний: сколько приглашений направлено, сколько дошло до ответа. Компания с
        нулём приглашений зарегистрирована, но основной механикой не пользуется.
      </SectionNote>
      <div className="tw overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400">
              <th className="py-2 pr-3">Компания</th>
              <th className="py-2 pr-3">Потребности</th>
              <th className="py-2 pr-3">Приглашения</th>
              <th className="py-2 pr-3">Ждут ответа</th>
              <th className="py-2 pr-3">Принято</th>
              <th className="py-2 pr-3">Отклонено</th>
              <th className="py-2 pr-3">Доля ответов</th>
              <th className="py-2 pr-3">Вакансии</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.employer_id} className="border-t border-slate-800">
                <td className="py-2 pr-3">{row.company_name ?? "без названия"}</td>
                <td className="py-2 pr-3">{row.needs}</td>
                <td className="py-2 pr-3">{row.invitations}</td>
                <td className="py-2 pr-3">{row.waiting}</td>
                <td className="py-2 pr-3">{row.accepted}</td>
                <td className="py-2 pr-3">{row.declined}</td>
                <td className="py-2 pr-3">
                  <Percent value={row.response_rate} />
                </td>
                <td className="py-2 pr-3">{row.vacancies}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SignalsTab() {
  const [rows, setRows] = useState<AdminAnomaly[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setRows(await apiClient.adminAnomalies());
      } catch (err) {
        setError(errorMessage(err));
      }
    })();
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;

  if (!rows.length) {
    return (
      <EmptyState
        title="Сигналов нет"
        hint="Проверки проходят по данным платформы: пустые категории, зависшие приглашения, дубли компаний."
      />
    );
  }

  return (
    <div className="space-y-4">
      <SectionNote>
        Сигналы — не «предсказания», а следствия конкретных данных: рядом указано, что именно
        проверено и сколько записей задето.
      </SectionNote>
      {rows.map((row) => (
        <Card key={row.key}>
          <div className="flex items-start gap-3">
            <span
              className={
                row.severity === "warning"
                  ? "mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-400"
                  : "mt-1 h-2 w-2 shrink-0 rounded-full bg-sky-400"
              }
            />
            <div>
              <p className="font-medium">{row.title}</p>
              <p className="mt-1 text-sm text-slate-300">{row.detail}</p>
              <p className="mt-1 text-xs text-slate-500">{row.hint}</p>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function AiTab() {
  const toast = useToast();
  const [summary, setSummary] = useState<apiClient.AIResult | null>(null);
  const [actions, setActions] = useState<apiClient.AIResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(kind: "summary" | "actions") {
    setBusy(true);
    try {
      if (kind === "summary") {
        setSummary(await apiClient.adminAiSummary());
      } else {
        setActions(await apiClient.adminAiRecommendations());
      }
    } catch (err) {
      toast.error("Не удалось получить ответ модели", errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <SectionNote>
        Модель не считает метрики — она получает уже посчитанные числа и объясняет их. Если модель
        недоступна, показываются подготовленные данные с пометкой, и сценарий не ломается.
      </SectionNote>

      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => void run("summary")}>
          Сводка состояния платформы
        </Button>
        <Button variant="ghost" disabled={busy} onClick={() => void run("actions")}>
          Что делать по показателям
        </Button>
      </div>

      {summary ? (
        <Card title={(summary.data as { headline?: string }).headline ?? "Сводка"}>
          <p className="text-sm text-slate-200">
            {(summary.data as { summary?: string }).summary}
          </p>
          <ul className="mt-2 space-y-1 text-sm text-slate-400">
            {((summary.data as { points?: string[] }).points ?? []).map((item) => (
              <li key={item}>· {item}</li>
            ))}
          </ul>
          {((summary.data as { watch?: string[] }).watch ?? []).length ? (
            <div className="mt-3">
              <p className="text-xs text-slate-400">На что смотреть:</p>
              <ul className="mt-1 space-y-1 text-sm text-amber-300/90">
                {((summary.data as { watch?: string[] }).watch ?? []).map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <AISourceNote result={summary} />
        </Card>
      ) : null}

      {actions ? (
        <Card title="Предлагаемые действия">
          <div className="space-y-3">
            {((actions.data as { actions?: { title: string; why: string; how?: string }[] }).actions ?? []).map(
              (item) => (
                <div key={item.title} className="rounded-lg border border-slate-800 p-3">
                  <p className="font-medium">{item.title}</p>
                  <p className="mt-1 text-sm text-slate-300">{item.why}</p>
                  {item.how ? <p className="mt-1 text-xs text-slate-500">{item.how}</p> : null}
                </div>
              ),
            )}
          </div>
          <AISourceNote result={actions} />
        </Card>
      ) : null}
    </div>
  );
}
