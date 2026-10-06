import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export function Card({ title, children, accent }: { title?: ReactNode; children: ReactNode; accent?: boolean }) {
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
  autoComplete,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  autoComplete?: string;
  hint?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-400">{label}</span>
      <input
        className={inputClass}
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
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
        className={inputClass}
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

/**
 * Единый вид поля ввода. Раньше класс копировался в каждую форму, причём в части
 * мест без стиля фокуса — теперь он один и с видимым фокусом.
 */
export const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-sky-500";

/**
 * Статус приглашения в одном месте: подпись, вид значка и цвет линии на схеме
 * взаимодействия. Раньше эти три представления жили в разных файлах и расходились.
 */
export const INVITATION_STATUS: Record<string, { label: string; badge: string; color: string }> = {
  sent: { label: "отправлено", badge: "bg-sky-500/15 text-sky-300", color: "#38bdf8" },
  viewed: { label: "просмотрено", badge: "bg-amber-500/15 text-amber-300", color: "#fbbf24" },
  accepted: { label: "принято", badge: "bg-emerald-500/15 text-emerald-300", color: "#34d399" },
  declined: { label: "отклонено", badge: "bg-rose-500/15 text-rose-300", color: "#fb7185" },
  revoked: { label: "отозвано работодателем", badge: "bg-slate-600/30 text-slate-400", color: "#64748b" },
};

/** Остальные статусы платформы: вакансии, отклики, задания. */
const OTHER_STATUS: Record<string, { label: string; badge: string }> = {
  published: { label: "опубликована", badge: "bg-emerald-500/15 text-emerald-300" },
  closed: { label: "закрыта", badge: "bg-slate-600/30 text-slate-400" },
  open: { label: "открыто", badge: "bg-emerald-500/15 text-emerald-300" },
  submitted: { label: "отправлено", badge: "bg-sky-500/15 text-sky-300" },
  completed: { label: "завершён", badge: "bg-emerald-500/15 text-emerald-300" },
  in_progress: { label: "в процессе", badge: "bg-amber-500/15 text-amber-300" },
};

export function StatusBadge({ status }: { status: string }) {
  const known = INVITATION_STATUS[status] ?? OTHER_STATUS[status];
  const badge = known?.badge ?? "bg-slate-700/40 text-slate-300";
  return <span className={`rounded-full px-2.5 py-0.5 text-xs ${badge}`}>{known?.label ?? status}</span>;
}

/** Процент с честным «нет данных»: отсутствие данных — не ноль. */
export function Percent({ value }: { value: number | null | undefined }) {
  if (value === null || value === undefined) return <span className="text-slate-500">нет данных</span>;
  return <span>{value}%</span>;
}

/** Поле выбора: та же форма, что у поля ввода, но со списком. */
export function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  hint?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-400">{label}</span>
      <select className={inputClass} value={value} onChange={(event) => onChange(event.target.value)}>
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
    </label>
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

/**
 * Отсутствующие данные: у каждого критерия — короткое человеческое название, а не
 * готовая фраза сервера. Иначе получалось «нет данных: нет данных о достижениях».
 */
const MISSING_LABELS: Record<string, string> = {
  "нет результата теста": "результат теста",
  "нет данных о достижениях (в том числе при отсутствии истории)": "достижения ФСП",
  "нет отметок активности в регулярных заданиях": "активность в заданиях",
  "нет оценки соответствия потребности": "соответствие описанной потребности",
};

export function ReasonList({
  reasons,
  missing,
}: {
  reasons: { code: string; text: string; contribution: number }[];
  missing: string[];
}) {
  return (
    <>
      <ul className="mt-2 space-y-0.5 text-xs text-slate-400">
        {reasons.map((reason) => (
          <li key={reason.code}>
            · {reason.text}
            {reason.contribution > 0 ? ` (вклад ${score(reason.contribution)})` : ""}
          </li>
        ))}
        {missing.map((item) => (
          <li key={item} className="text-slate-500">
            · не оценено: {MISSING_LABELS[item] ?? item} — вклад 0
          </li>
        ))}
      </ul>
      {missing.length ? (
        <p className="mt-1 text-xs text-slate-500">
          Данных для этих критериев нет — они не додумываются: вклад 0, позицию это не понижает.
        </p>
      ) : null}
    </>
  );
}

/** Порядок грейдов, если справочник ещё не загружен: тот же, что в GRADE_ORDER на сервере. */
export const GRADE_CODES = ["intern", "junior", "junior_plus", "middle", "senior", "lead"];

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

/**
 * Числовой показатель (балл рубрики, θ) в едином виде: фиксированное число знаков
 * и запятая как разделитель. Иначе в интерфейсе соседствуют «0.25» и «0.4187».
 */
export function score(value: number, digits = 3): string {
  return value.toLocaleString("ru-RU", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/**
 * Модальное окно для действий.
 *
 * Все формы и подтверждения показываются здесь, а не под списком: при длинном
 * списке форма «внизу» остаётся незамеченной, и нажатие кнопки выглядит как
 * отсутствие реакции. Закрывается по Esc, клику по фону и крестику.
 */
export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  wide,
}: {
  open: boolean;
  title: string;
  description?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/75 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
        className={`my-6 w-full ${wide ? "max-w-3xl" : "max-w-xl"} rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-2xl outline-none`}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-sky-300">{title}</h2>
            {description ? (
              <div className="mt-1 text-xs leading-relaxed text-slate-400">{description}</div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="shrink-0 rounded-lg border border-slate-700 px-2 py-1 text-xs text-slate-400 transition hover:border-sky-500 hover:text-white"
          >
            ✕
          </button>
        </div>
        <div className="space-y-3">{children}</div>
        {footer ? (
          <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-800 pt-4">{footer}</div>
        ) : null}
      </div>
    </div>
  );
}

/**
 * Пояснение по кнопке «?».
 *
 * Открывается по клику (а не только по наведению) — иначе на планшете и в
 * демонстрации с тачскрином подсказку невозможно прочитать. Закрывается по
 * Esc, клику вне подсказки и повторному нажатию.
 */
export function InfoTip({ text, label = "Пояснение" }: { text: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const holder = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (event: MouseEvent) => {
      if (holder.current && !holder.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={holder} className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-600 text-[10px] leading-none text-slate-400 transition hover:border-sky-500 hover:text-sky-300"
      >
        ?
      </button>
      {open ? (
        <span
          role="tooltip"
          className="absolute left-1/2 top-6 z-40 w-72 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-900 p-3 text-left text-xs leading-relaxed font-normal text-slate-300 shadow-xl"
        >
          {text}
        </span>
      ) : null}
    </span>
  );
}

/** Пояснение к разделу: что здесь происходит и зачем. */
export function SectionNote({ children }: { children: ReactNode }) {
  return (
    <p className="mb-3 rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-xs leading-relaxed text-slate-400">
      {children}
    </p>
  );
}

/** Пустое состояние: объясняет, почему пусто и что сделать. */
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-700 p-6 text-center">
      <p className="text-sm text-slate-300">{title}</p>
      {hint ? <p className="mx-auto mt-1 max-w-md text-xs text-slate-500">{hint}</p> : null}
      {action ? <div className="mt-3 flex justify-center">{action}</div> : null}
    </div>
  );
}
