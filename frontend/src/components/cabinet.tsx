import type { ReactNode } from "react";

import { useAuth } from "../auth/AuthContext";
import { AIStatusBadge } from "./ai";
import { Button } from "./ui";

/**
 * Общая шапка кабинета: кто вошёл, состояние модели и выход.
 *
 * Раньше каждая роль собирала шапку сама: у соискателя и работодателя были состояние
 * модели и кнопка выхода, у администратора — нет, а заголовок отличался размером.
 * Теперь шапка и вкладки одни на все кабинеты, поэтому расхождения невозможны.
 */
export function CabinetShell<T extends string>({
  title,
  subtitle,
  tabs,
  active,
  onSelect,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  tabs: [T, string][];
  active: T;
  onSelect: (tab: T) => void;
  children: ReactNode;
}) {
  const { user, logout } = useAuth();

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-slate-400">{subtitle ?? user?.email}</p>
        </div>
        <div className="flex items-center gap-3">
          <AIStatusBadge />
          <Button variant="ghost" onClick={() => void logout()}>
            Выйти
          </Button>
        </div>
      </header>

      <nav className="flex flex-wrap gap-2" aria-label="Разделы кабинета">
        {tabs.map(([key, label]) => (
          <Button key={key} variant={active === key ? "primary" : "ghost"} onClick={() => onSelect(key)}>
            {label}
          </Button>
        ))}
      </nav>

      {children}
    </div>
  );
}
