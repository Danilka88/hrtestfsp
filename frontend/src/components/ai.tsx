import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import * as apiClient from "../api/client";
import type { AIResult, AIStatus } from "../api/client";
import type { ToastKind } from "./toast";

/**
 * Элементы интерфейса для ИИ-функций.
 *
 * Главное правило: интерфейс всегда показывает, откуда взялся текст — от
 * локальной модели или из демо-данных. Пользователь не должен думать, что
 * видит результат работы модели, когда модель недоступна.
 */

export function useAIStatus(): AIStatus | null {
  const [status, setStatus] = useState<AIStatus | null>(null);
  useEffect(() => {
    apiClient
      .aiStatus()
      .then(setStatus)
      .catch(() => undefined);
  }, []);
  return status;
}

export function AIStatusBadge() {
  const status = useAIStatus();
  if (!status) return null;

  const working = status.available && !status.degraded;
  const styles = working
    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
    : "border-amber-500/40 bg-amber-500/10 text-amber-300";
  const label = working ? `ИИ: ${status.model ?? "локальная модель"}` : "ИИ: демо-режим";

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${styles}`}
      title={status.hint}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${working ? "bg-emerald-400" : "bg-amber-400"}`} />
      {label}
    </span>
  );
}

/** Готовая формулировка для уведомления о результате ИИ-вызова. */
export function aiToastPayload(
  result: AIResult,
  successText: string,
): { kind: ToastKind; text: string; detail: string } {
  if (result.degraded) {
    return {
      kind: "info",
      text: `${successText} — демо-данные`,
      detail: result.note ?? "Локальная модель недоступна: показаны подготовленные демо-данные",
    };
  }
  return {
    kind: "success",
    text: successText,
    detail: `${result.provider} · ${result.latency_ms} мс`,
  };
}

/**
 * Текст модели.
 *
 * Модель оформляет ответ разметкой (`**жирный**`), и в интерфейсе это выглядело как
 * звёздочки. Здесь разметка превращается в выделение, а служебные знаки не показываются.
 */
export function AIText({ children, className }: { children?: string | null; className?: string }) {
  const text = (children ?? "").trim();
  if (!text) return null;
  return (
    <span className={className}>
      {text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={index} className="font-semibold text-slate-100">
            {part.slice(2, -2)}
          </strong>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </span>
  );
}

/** Компактная пометка под сгенерированным текстом. */
export function AISourceNote({ result }: { result: AIResult | null }) {
  if (!result) return null;
  const degraded = result.degraded;
  return (
    <p className={`mt-1 text-xs ${degraded ? "text-amber-400/90" : "text-slate-500"}`}>
      {degraded
        ? `Демо-данные: ${result.note ?? "модель недоступна"}`
        : `Сформировано локальной моделью ${result.provider} за ${result.latency_ms} мс` +
          (result.note ? ` · ${result.note}` : "")}
    </p>
  );
}

/**
 * Метка ИИ-функции.
 *
 * Один знак для кнопок, блоков и результатов: пользователь сразу видит, что перед
 * ним результат модели, а не обычное действие платформы. Раньше часть кнопок ИИ
 * выглядела как обычные, и было непонятно, где подключается модель.
 */
export function AITag({ children = "ИИ" }: { children?: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium tracking-wide text-violet-200 uppercase">
      <span aria-hidden>✦</span>
      {children}
    </span>
  );
}

/**
 * Блок ИИ-функции: рамка и подложка того же цвета, что у кнопок ИИ.
 *
 * Внутри — форма запуска, результат и подпись об источнике текста. Любой блок,
 * который показывает или собирает вывод модели, оформляется этим компонентом.
 */
export function AIPanel({
  title,
  hint,
  children,
  result,
}: {
  title: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
  result?: AIResult | null;
}) {
  return (
    <section className="rounded-xl border border-violet-500/40 bg-violet-500/[0.06] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-violet-100">
          <span aria-hidden>✦</span>
          {title}
        </h2>
        <AITag />
      </div>
      {hint ? <div className="mb-3 text-xs leading-relaxed text-slate-400">{hint}</div> : null}
      {children}
      <AISourceNote result={result ?? null} />
    </section>
  );
}

/** Кнопка запуска ИИ-действия с индикатором ожидания. */
export function AIButton({
  children,
  onClick,
  busy,
  disabled,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  busy?: boolean;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy || disabled}
      title={title}
      className="inline-flex items-center gap-2 rounded-lg border border-violet-500/50 px-3 py-1.5 text-sm font-medium text-violet-200 transition hover:border-violet-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
    >
      {busy ? (
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-violet-300/40 border-t-violet-200" />
      ) : (
        <span aria-hidden>✦</span>
      )}
      {busy ? "Готовим…" : children}
    </button>
  );
}

/** Индикатор загрузки для длительных операций. */
export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-400">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" />
      {label ?? "Загрузка…"}
    </span>
  );
}
