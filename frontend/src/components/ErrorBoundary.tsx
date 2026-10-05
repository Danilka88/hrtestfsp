import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

/**
 * Граница ошибок интерфейса.
 *
 * Без неё любая ошибка отрисовки оставляет пустой экран — на демонстрации это
 * выглядит как «приложение не работает». Здесь пользователь видит понятное
 * сообщение и кнопку возврата, а сама ошибка попадает в консоль для разбора.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Сбой интерфейса:", error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="mx-auto max-w-lg p-6">
        <div className="rounded-lg border border-rose-600/50 bg-rose-600/10 p-4 text-sm text-rose-200">
          <p className="font-medium">Раздел не открылся из-за ошибки интерфейса</p>
          <p className="mt-1">
            Данные на сервере в порядке — сбой только в отображении. Обновите страницу или вернитесь
            на главную.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              className="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-900"
              onClick={() => window.location.reload()}
            >
              Обновить страницу
            </button>
            <a
              className="rounded-lg px-3 py-1.5 text-sm text-rose-200 underline"
              href="/"
            >
              На главную
            </a>
          </div>
        </div>
      </div>
    );
  }
}
