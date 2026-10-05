import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { errorMessage } from "../api/client";
import type { Role } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, Button, Card, Field } from "../components/ui";

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
      navigate(profile.role === "employer" ? "/employer" : "/candidate");
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
      navigate(profile.role === "employer" ? "/employer" : "/candidate");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

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
            <Field label="Электронная почта" value={email} onChange={setEmail} type="email" required />
            <Field
              label="Пароль (минимум 8 символов)"
              value={password}
              onChange={setPassword}
              type="password"
              required
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

            <div className="flex gap-2 pt-1">
              <Button type="submit" disabled={busy}>
                {mode === "login" ? "Войти" : "Зарегистрироваться"}
              </Button>
              {busy ? <span className="self-center text-xs text-slate-500">выполняется…</span> : null}
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

        <p className="text-center text-xs text-slate-500">
          Демо-доступ после загрузки демо-данных: <code>anna.kovaleva@demo.ru</code> /{" "}
          <code>demo12345</code>, работодатель <code>hr@fintech-demo.ru</code> /{" "}
          <code>demo12345</code>. <Link to="/health">Состояние сервиса</Link>
        </p>
      </div>
    </div>
  );
}
