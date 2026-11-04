import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as api from "@/api/auth";

type Ctx = {
  user: api.User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (d: { full_name: string; email: string; phone: string; password: string }) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<Ctx | null>(null);
const TOKEN_KEY = "dalil.token";
const USER_KEY = "dalil.user"; // used in mock mode only

const read = (k: string) => {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
};
const write = (k: string, v: string | null) => {
  try {
    if (v === null) localStorage.removeItem(k);
    else localStorage.setItem(k, v);
  } catch {
    /* ignore */
  }
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<api.User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = read(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    if (api.USE_MOCK) {
      const saved = read(USER_KEY);
      setUser(saved ? JSON.parse(saved) : null);
      setLoading(false);
      return;
    }
    api
      .me(token)
      .then(setUser)
      .catch(() => write(TOKEN_KEY, null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { token, user } = await api.login(email, password);
    write(TOKEN_KEY, token);
    if (api.USE_MOCK) write(USER_KEY, JSON.stringify(user));
    setUser(user);
  }, []);

  const register = useCallback(
    async (d: { full_name: string; email: string; phone: string; password: string }) => {
      await api.register(d);
      await login(d.email, d.password);
    },
    [login],
  );

  const logout = useCallback(() => {
    write(TOKEN_KEY, null);
    write(USER_KEY, null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}