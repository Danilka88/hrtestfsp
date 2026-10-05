import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { errorMessage } from "../api/client";
import type { Role } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, Button, Card, Field } from "../components/ui";

/** Кабинет по роли — то же правило, что в маршрутизации приложения. */
function cabinetPath(role: string): string {
  if (role === "employer") return "/employer";
  if (role === "admin") return "/admin";
  return "/candidate";
}

export function LoginPage() {
  const { login, register, confirmEmail } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("candidate");
  const [consentPdn, setConsentPdn] = useState(false);
  const [consentPublish, setConsentPublish] = useState(false);
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submitLogin() {
    setBusy(true);
    setError(null);
    try {
      const profile = await login(email, password);
      navigate(cabinetPath(profile.role));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitRegister() {
    setBusy(true);
    setError(null);
    try {
      const result = await register({
        email,
        password,
        role,
        consent_pdn: consentPdn,
        consent_publish: consentPublish,
      });
      setPendingToken(result.verification_token);
      setInfo(
        result.verification_token
          ? "Регистрация принята. В демо-режиме код подтверждения показан ниже — нажмите «Подтвердить»."
          : "Регистрация принята. Проверьте почту и подтвердите адрес.",
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitConfirm() {
    if (!pendingToken) return;
    setBusy(true);
    setError(null);
    try {
      await confirmEmail(pendingToken);
      const profile = await login(email, password);
      navigate(cabinetPath(profile.role));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  /** Вход в демонстрационный профиль одним нажатием — чтобы показ не начинался с ручного ввода. */
  async function demoLogin(kind: Role | "admin") {
    const accounts: Record<string, { email: string; password: string }> = {
      candidate: { email: "anna.kovaleva@demo.ru", password: "demo12345" },
      employer: { email: "hr@fintech-demo.ru", password: "demo12345" },
      admin: { email: "admin@demo.ru", password: "demo12345" },
    };
    const account = accounts[kind];
    setMode("login");
    setEmail(account.email);
    setPassword(account.password);
    setBusy(true);
    setError(null);
    try {
      const profile = await login(account.email, account.password);
      navigate(cabinetPath(profile.role));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  // Согласие на обработку персональных данных требует сервер: без него регистрация
  // вернула бы ошибку. Понятнее не отправлять форму, чем получить отказ после отправки.
  const consentMissing = mode === "register" && !consentPdn;

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-2xl font-bold tracking-tight">
        {mode === "login" ? "Вход" : "Регистрация"}
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        {mode === "login"
          ? "Войдите, чтобы открыть личный кабинет."
          : "Регистрация выполняется по электронной почте с подтверждением адреса."}
      </p>

      <div className="mt-5 flex gap-2">
        <Button variant={mode === "login" ? "primary" : "ghost"} onClick={() => setMode("login")}>
          Вход
        </Button>
        <Button variant={mode === "register" ? "primary" : "ghost"} onClick={() => setMode("register")}>
          Регистрация
        </Button>
      </div>

      <div className="mt-5 space-y-4">
        <Card>
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void (mode === "login" ? submitLogin() : submitRegister());
            }}
          >
            <Field
              label="Электронная почта"
              value={email}
              onChange={setEmail}
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
            />
            <Field
              label="Пароль (минимум 8 символов)"
              value={password}
              onChange={setPassword}
              type="password"
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              hint={mode === "register" ? "Пароль хешируется на сервере и не хранится в открытом виде." : undefined}
            />

            {mode === "register" ? (
              <>
                <label className="block text-sm">
                  <span className="mb-1 block text-slate-400">Роль</span>
                  <select
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                    value={role}
                    onChange={(event) => setRole(event.target.value as Role)}
                  >
                    <option value="candidate">Соискатель</option>
                    <option value="employer">Работодатель</option>
                  </select>
                </label>

                <label className="flex items-start gap-2 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={consentPdn}
                    onChange={(event) => setConsentPdn(event.target.checked)}
                  />
                  <span>
                    Согласен на обработку персональных данных <span className="text-slate-500">(обязательно)</span>
                  </span>
                </label>
                <label className="flex items-start gap-2 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={consentPublish}
                    onChange={(event) => setConsentPublish(event.target.checked)}
                  />
                  <span>Согласен на публикацию данных профиля работодателям (необязательно)</span>
                </label>
              </>
            ) : null}

            <div className="flex items-center gap-2 pt-1">
              <Button type="submit" disabled={busy || consentMissing}>
                {mode === "login" ? "Войти" : "Зарегистрироваться"}
              </Button>
              {busy ? <span className="text-xs text-slate-500">выполняется…</span> : null}
              {consentMissing ? (
                <span className="text-xs text-amber-400">Отметьте согласие на обработку данных</span>
              ) : null}
            </div>
          </form>
        </Card>

        {error ? <Alert kind="error">{error}</Alert> : null}
        {info ? <Alert kind="ok">{info}</Alert> : null}

        {pendingToken ? (
          <Card>
            <p className="text-xs text-slate-400">
              Код подтверждения (демо-режим, почта не отправляется):
            </p>
            <code className="mt-1 block break-all rounded bg-slate-950 p-2 text-xs text-sky-300">
              {pendingToken}
            </code>
            <div className="mt-3">
              <Button onClick={() => void submitConfirm()} disabled={busy}>
                Подтвердить и войти
              </Button>
            </div>
          </Card>
        ) : null}

        <Card title="Демонстрационный доступ">
          <p className="mb-3 text-xs text-slate-400">
            Логин и пароль подставятся автоматически. Работает после загрузки демо-данных
            (<code>bash scripts/reset-demo.sh</code>).
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" disabled={busy} onClick={() => void demoLogin("candidate")}>
              Войти как соискатель
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => void demoLogin("employer")}>
              Войти как работодатель
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => void demoLogin("admin")}>
              Войти как администратор
            </Button>
          </div>
        </Card>

        <p className="text-center text-xs text-slate-500">
          <code>anna.kovaleva@demo.ru</code>, <code>hr@fintech-demo.ru</code>,{" "}
          <code>admin@demo.ru</code>, пароль <code>demo12345</code> ·{" "}
          <Link to="/health">Состояние сервиса</Link>
        </p>
      </div>
    </div>
  );
}
