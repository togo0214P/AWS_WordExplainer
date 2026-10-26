import type { Candidate, Category, Entry } from "./types";

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new Error(
      "APIに接続できません。APIサーバーと接続先の設定を確認してください。",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.error?.message ?? `処理に失敗しました（HTTP ${response.status}）。`,
      response.status,
      body?.error?.code,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  generate: (word: string) =>
    request<Candidate>("/api/explanations/generate", {
      method: "POST",
      body: JSON.stringify({ word }),
    }),
  save: ({ word, category_id, explanation }: Candidate) =>
    request<Entry>("/api/entries", {
      method: "POST",
      body: JSON.stringify({ word, category_id, explanation }),
    }),
  categories: (signal?: AbortSignal) =>
    request<{ categories: Category[] }>("/api/categories", { signal }),
  entries: (signal?: AbortSignal) =>
    request<{ entries: Entry[] }>("/api/entries", { signal }),
  delete: (id: number) =>
    request<void>(`/api/entries/${id}`, { method: "DELETE" }),
};

export function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "処理に失敗しました。もう一度お試しください。";
}
