import type { ReactNode } from "react";

import { Card, InfoTip, INVITATION_STATUS, SectionNote } from "./ui";

/** Тон полосы для каждого статуса приглашения — в одном месте. */
const INVITATION_TONES: Record<string, "sky" | "amber" | "emerald" | "rose" | "slate"> = {
  sent: "sky",
  viewed: "amber",
  accepted: "emerald",
  declined: "rose",
  revoked: "slate",
};

/** Порядок статусов приглашения: от отправки к решению. */
const INVITATION_ORDER = ["sent", "viewed", "accepted", "declined", "revoked"] as const;

/**
 * Распределение приглашений по статусам.
 *
 * Одинаково в обоих кабинетах: раньше этот блок из пяти полос был скопирован в каждый
 * дашборд, и подписи со статусами могли разойтись.
 */
export function InvitationBars({ invitations }: { invitations: { status: string }[] }) {
  const total = invitations.length;
  return (
    <div className="space-y-2">
      {INVITATION_ORDER.map((status) => (
        <Bar
          key={status}
          label={INVITATION_STATUS[status].label}
          value={invitations.filter((item) => item.status === status).length}
          total={total}
          tone={INVITATION_TONES[status]}
        />
      ))}
    </div>
  );
}

/**
 * Кирпичики дашбордов кабинетов: показатели и ИИ-блок.
 *
 * Значения приходят уже посчитанными — карточка ничего не «выводит», поэтому
 * «нет данных» здесь честно отличается от нуля.
 */
export function Kpi({
  label,
  value,
  hint,
  tone = "default",
  tip,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "default" | "ok" | "warn";
  tip?: string;
}) {
  const valueClass =
    tone === "ok" ? "text-emerald-300" : tone === "warn" ? "text-amber-300" : "text-slate-100";
  return (
    <Card>
      <p className="text-xs text-slate-400">
        {label}
        {tip ? <InfoTip text={tip} /> : null}
      </p>
      <p className={`mt-1 text-2xl font-semibold ${valueClass}`}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </Card>
  );
}

/** Шапка дашборда: короткое объяснение + сетка показателей + ИИ-блок. */
export function Dashboard({
  lead,
  kpis,
  ai,
  children,
}: {
  lead: ReactNode;
  kpis: ReactNode;
  ai?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="space-y-4">
      <SectionNote>{lead}</SectionNote>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{kpis}</div>
      {children}
      {ai}
    </div>
  );
}

/** Строка-показатель с полосой: удобно для распределения по статусам. */
export function Bar({
  label,
  value,
  total,
  tone = "sky",
}: {
  label: string;
  value: number;
  total: number;
  tone?: "sky" | "emerald" | "amber" | "rose" | "slate";
}) {
  const colors: Record<string, string> = {
    sky: "bg-sky-500/70",
    emerald: "bg-emerald-500/70",
    amber: "bg-amber-500/70",
    rose: "bg-rose-500/70",
    slate: "bg-slate-500/70",
  };
  const share = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className="text-slate-400">
          {value}
          {total > 0 ? <span className="ml-2 text-xs text-slate-500">{share}%</span> : null}
        </span>
      </div>
      <div className="mt-1 h-2 rounded bg-slate-800">
        <div
          className={`h-2 rounded ${colors[tone]}`}
          style={{ width: `${Math.max(2, share)}%` }}
        />
      </div>
    </div>
  );
}
