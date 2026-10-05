import type { ReactNode } from "react";
import { Link, Navigate, NavLink, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthContext";
import { Button } from "./components/ui";
import { HealthPage } from "./pages/Health";
import { HomePage } from "./pages/Home";
import { LoginPage } from "./pages/Login";
import { CandidateCabinet } from "./pages/candidate/Cabinet";
import { EmployerCabinet } from "./pages/employer/Cabinet";

function Shell({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 text-sm ${
      isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
    }`;

  const cabinetPath = user?.role === "employer" ? "/employer" : "/candidate";

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-800 bg-slate-950/70 backdrop-blur">
        <nav className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-2 px-5 py-3">
          <Link to="/" className="mr-3 font-bold tracking-tight text-sky-400">
            IT-Talent Match
          </Link>
          <NavLink to="/" className={linkClass} end>
            Обзор
          </NavLink>
          {!loading && user ? (
            <NavLink to={cabinetPath} className={linkClass}>
              Кабинет
            </NavLink>
          ) : null}
          <NavLink to="/health" className={linkClass}>
            Состояние
          </NavLink>

          <div className="ml-auto flex items-center gap-3">
            {loading ? null : user ? (
              <>
                <span className="hidden text-xs text-slate-500 sm:inline">
                  {user.email} · {user.role === "employer" ? "работодатель" : "соискатель"}
                </span>
                <Link to={cabinetPath}>
                  <Button variant="ghost">Мой кабинет</Button>
                </Link>
              </>
            ) : (
              <Link to="/login">
                <Button>Войти</Button>
              </Link>
            )}
            <a className="text-sm text-slate-400 hover:text-white" href="/docs" target="_blank" rel="noreferrer">
              API
            </a>
          </div>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-8">{children}</main>

      <footer className="border-t border-slate-800 py-6 text-center text-xs text-slate-500">
        IT-Talent Match · платформа обратного подбора ИТ-специалистов · MVP для хакатона
      </footer>
    </div>
  );
}

/** Маршрут, доступный только авторизованному пользователю нужной роли. */
function Protected({ role, children }: { role: "candidate" | "employer"; children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="text-sm text-slate-500">Проверка сессии…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) {
    return <Navigate to={user.role === "employer" ? "/employer" : "/candidate"} replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/candidate"
          element={
            <Protected role="candidate">
              <CandidateCabinet />
            </Protected>
          }
        />
        <Route
          path="/employer"
          element={
            <Protected role="employer">
              <EmployerCabinet />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
