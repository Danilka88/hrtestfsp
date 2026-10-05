import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import * as apiClient from "../api/client";
import type { Role, UserPublic } from "../api/client";
import { tokenStore } from "../api/client";
import { useToast } from "../components/toast";

interface AuthState {
  user: UserPublic | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<UserPublic>;
  register: (input: {
    email: string;
    password: string;
    role: Role;
    consent_pdn: boolean;
    consent_publish: boolean;
  }) => Promise<apiClient.RegisterResponse>;
  confirmEmail: (token: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [user, setUser] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const currentUser = useRef<UserPublic | null>(null);
  currentUser.current = user;

  // Сессия закончилась во время работы: без явного сообщения пользователь видит
  // ошибки конкретных действий и не понимает, что нужно войти заново.
  useEffect(() => {
    const onUnauthorized = (event: Event) => {
      const hadToken = (event as CustomEvent<{ hadToken?: boolean }>).detail?.hadToken ?? false;
      if (currentUser.current || hadToken) {
        toast.error("Сессия истекла", "Войдите заново — данные сохранены на сервере");
      }
      setUser(null);
    };
    window.addEventListener("it-talent:unauthorized", onUnauthorized);
    return () => window.removeEventListener("it-talent:unauthorized", onUnauthorized);
  }, [toast]);

  const refresh = useCallback(async () => {
    if (!tokenStore.access()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await apiClient.me());
    } catch {
      tokenStore.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    await apiClient.login(email, password);
    const profile = await apiClient.me();
    setUser(profile);
    return profile;
  }, []);

  const register = useCallback<AuthState["register"]>(async (input) => {
    return apiClient.register(input);
  }, []);

  const confirmEmail = useCallback(
    async (token: string) => {
      await apiClient.verifyEmail(token);
    },
    [],
  );

  const logout = useCallback(async () => {
    await apiClient.logout();
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, register, confirmEmail, logout, refresh }),
    [user, loading, login, register, confirmEmail, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth должен использоваться внутри AuthProvider");
  return context;
}
