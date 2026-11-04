// VERIFIED backend contract: HANDOFF.md section 4 (/auth/register, /auth/login, /auth/me).
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

export type User = { id: number; role: string; full_name: string; email: string; phone: string };

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

// Same rules as the backend.
export const phoneOk = (v: string) => /^01[0125][0-9]{8}$/.test(v);
export const passwordOk = (v: string) => v.length >= 8 && v.length <= 128 && /[A-Za-z]/.test(v) && /\d/.test(v);
export const emailOk = (v: string) => /^\S+@\S+\.\S+$/.test(v);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, init);
  } catch {
    throw new ApiError("network", "network");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.code ?? "generic", body?.message ?? "error");
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export async function login(email: string, password: string): Promise<{ token: string; user: User }> {
  if (USE_MOCK) {
    // MOCK ONLY: any valid email + password passes.
    return {
      token: "mock-token",
      user: { id: 1, role: "customer", full_name: email.split("@")[0], email, phone: "" },
    };
  }
  const { access_token } = await request<{ access_token: string }>("/auth/login", json({ email, password }));
  const user = await me(access_token);
  return { token: access_token, user };
}

export async function register(data: { full_name: string; email: string; phone: string; password: string }) {
  if (USE_MOCK) return;
  await request("/auth/register", json({ ...data, role: "customer" }));
}

export function me(token: string): Promise<User> {
  return request<User>("/auth/me", { headers: { Authorization: `Bearer ${token}` } });
}