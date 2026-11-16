// Single switch between mock data and the real FastAPI backend.
export const USE_MOCK: boolean = (import.meta.env.VITE_USE_MOCK ?? "true") !== "false";
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const delay = (ms = 300) => new Promise<void>((resolve) => setTimeout(resolve, ms));

// Backend errors use { code, message, details }.
export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let body: { code?: string; message?: string; details?: unknown } = {};
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, body.code ?? "unknown_error", body.message ?? res.statusText, body.details);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
