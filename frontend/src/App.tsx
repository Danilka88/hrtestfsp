import type { ReactNode } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";

import { HealthPage } from "./pages/Health";
import { HomePage } from "./pages/Home";

function Shell({ children }: { children: ReactNode }) {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-950/70 backdrop-blur">
        <nav className="mx-auto flex max-w-5xl items-center gap-2 px-5 py-3">
          <Link to="/" className="mr-3 font-bold tracking-tight text-sky-400">
            IT-Talent Match
          </Link>
          <NavLink to="/" className={linkClass} end>
            Обзор
          </NavLink>
          <NavLink to="/health" className={linkClass}>
            Состояние
          </NavLink>
          <a
            className="ml-auto text-sm text-slate-400 hover:text-white"
            href={`${import.meta.env.VITE_API_BASE ?? "/api/v1"}/../docs`}
            target="_blank"
            rel="noreferrer"
          >
            API docs
          </a>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-10">{children}</main>
      <footer className="border-t border-slate-800 py-6 text-center text-xs text-slate-500">
        Каркас MVP · Этап 0 · демо-режим работает оффлайн
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </Shell>
  );
}
