import type { ReactNode } from "react";

export function Card({ title, children, accent }: { title?: string; children: ReactNode; accent?: boolean }) {
  return (
    <section
      className={`rounded-xl border bg-slate-900/60 p-4 ${
        accent ? "border-sky-500/60" : "border-slate-800"
      }`}
    >
      {title ? <h2 className="mb-3 text-sm font-semibold text-sky-300">{title}</h2> : null}
      {children}
    </section>
  );
}

export function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-400">{label}</span>
      <input
        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-sky-500"
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function TextArea({
  label,
  value,
  onChange,
  rows = 4,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-400">{label}</span>
      <textarea
        className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-sky-500"
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-sky-500 text-slate-950 hover:bg-sky-400",
    ghost: "border border-slate-700 text-slate-300 hover:border-sky-500 hover:text-white",
    danger: "border border-rose-600/60 text-rose-300 hover:bg-rose-600/10",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${styles}`}
    >
      {children}
    </button>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    sent: "bg-sky-500/15 text-sky-300",
    viewed: "bg-amber-500/15 text-amber-300",
    accepted: "bg-emerald-500/15 text-emerald-300",
    declined: "bg-rose-500/15 text-rose-300",
    published: "bg-emerald-500/15 text-emerald-300",
    closed: "bg-slate-600/30 text-slate-400",
    open: "bg-emerald-500/15 text-emerald-300",
    submitted: "bg-sky-500/15 text-sky-300",
    completed: "bg-emerald-500/15 text-emerald-300",
    in_progress: "bg-amber-500/15 text-amber-300",
  };
  const labels: Record<string, string> = {
    sent: "отправлено",
    viewed: "просмотрено",
    accepted: "принято",
    declined: "отклонено",
    published: "опубликована",
    closed: "закрыта",
    open: "открыто",
    submitted: "отправлено",
    completed: "завершён",
    in_progress: "в процессе",
  };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs ${map[status] ?? "bg-slate-700/40 text-slate-300"}`}>
      {labels[status] ?? status}
    </span>
  );
}

export function Alert({ kind = "info", children }: { kind?: "info" | "error" | "ok"; children: ReactNode }) {
  const styles = {
    info: "border-slate-700 text-slate-300",
    error: "border-rose-600/50 bg-rose-600/10 text-rose-200",
    ok: "border-emerald-600/50 bg-emerald-600/10 text-emerald-200",
  }[kind];
  return <div className={`rounded-lg border p-3 text-sm ${styles}`}>{children}</div>;
}

export function ReasonList({ reasons, missing }: { reasons: { code: string; text: string; contribution: number }[]; missing: string[] }) {
  return (
    <ul className="mt-2 space-y-0.5 text-xs text-slate-400">
      {reasons.map((reason) => (
        <li key={reason.code}>
          · {reason.text}
          {reason.contribution > 0 ? ` (вклад ${reason.contribution})` : ""}
        </li>
      ))}
      {missing.map((item) => (
        <li key={item} className="text-amber-400/80">
          ! нет данных: {item}
        </li>
      ))}
    </ul>
  );
}

export function gradesLabel(grade: string | null | undefined): string {
  if (!grade) return "не определён";
  const labels: Record<string, string> = {
    intern: "стажёр",
    junior: "младший",
    junior_plus: "младший+",
    middle: "средний",
    senior: "старший",
    lead: "ведущий",
  };
  return labels[grade] ?? grade;
}

export function money(value: number): string {
  return `${value.toLocaleString("ru-RU")} ₽`;
}
