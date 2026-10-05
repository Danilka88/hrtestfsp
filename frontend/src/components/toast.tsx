import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

/**
 * Всплывающие уведомления о событиях.
 *
 * Зачем: раньше результат действия был виден только рядом с кнопкой, и при
 * прокрутке или смене вкладки сообщение терялось. Теперь любое значимое событие
 * (отклик отправлен, приглашение принято, подборка уточнена, ИИ недоступен)
 * показывается поверх интерфейса и не зависит от текущего экрана.
 *
 * Уведомления делятся по смыслу: success — действие выполнено, error — не
 * выполнено, info — пояснение (например, что ответ сформирован демо-данными).
 */

export type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  text: string;
  detail?: string;
}

interface ToastApi {
  push: (kind: ToastKind, text: string, detail?: string) => void;
  success: (text: string, detail?: string) => void;
  error: (text: string, detail?: string) => void;
  info: (text: string, detail?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

// Длительность показа: ошибки держим дольше — их нужно успеть прочитать.
const LIFETIME_MS: Record<ToastKind, number> = {
  success: 5000,
  info: 6000,
  error: 9000,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const push = useCallback(
    (kind: ToastKind, text: string, detail?: string) => {
      const id = Date.now() + Math.random();
      setItems((prev) => [...prev.slice(-4), { id, kind, text, detail }]);
      window.setTimeout(() => remove(id), LIFETIME_MS[kind]);
    },
    [remove],
  );

  const api: ToastApi = {
    push,
    success: (text, detail) => push("success", text, detail),
    error: (text, detail) => push("error", text, detail),
    info: (text, detail) => push("info", text, detail),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(92vw,380px)] flex-col gap-2"
        role="status"
        aria-live="polite"
      >
        {items.map((item) => (
          <ToastCard key={item.id} item={item} onClose={() => remove(item.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ item, onClose }: { item: ToastItem; onClose: () => void }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setShown(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const styles: Record<ToastKind, string> = {
    success: "border-emerald-500/50 bg-emerald-950/90 text-emerald-100",
    error: "border-rose-500/50 bg-rose-950/90 text-rose-100",
    info: "border-sky-500/50 bg-slate-900/95 text-slate-100",
  };
  const icons: Record<ToastKind, string> = { success: "✓", error: "!", info: "i" };

  return (
    <div
      className={`pointer-events-auto rounded-xl border p-3 shadow-lg backdrop-blur transition-all duration-200 ${
        styles[item.kind]
      } ${shown ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"}`}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full border border-current text-xs font-bold">
          {icons[item.kind]}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{item.text}</p>
          {item.detail ? <p className="mt-0.5 text-xs opacity-80">{item.detail}</p> : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex-none rounded px-1 text-xs opacity-60 transition hover:opacity-100"
          aria-label="Закрыть уведомление"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast должен использоваться внутри ToastProvider");
  return context;
}
