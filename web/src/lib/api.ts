"use client";

import useSWR, { type SWRConfiguration } from "swr";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** JSON request to the backend (same origin: Next forwards /api/* to FastAPI). */
export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(path, {
    ...rest,
    headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...rest.headers },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

/** Not signed in (or the session ended): go to the sign-in page, then come back here. */
export function toSignIn() {
  const { pathname, search } = window.location;
  if (pathname === "/login") return;
  // A full load on purpose: called from outside React (fetchers, sockets), and it drops everything cached.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(pathname + search)}`);
}

/** Read a screen's data. `path` null = don't fetch yet. Revalidates on focus and every `refreshMs`. */
export function useApi<T>(path: string | null, refreshMs = 30_000, config?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(path, (p: string) => api<T>(p), {
    refreshInterval: refreshMs,
    revalidateOnFocus: true,
    shouldRetryOnError: (err) => !(err instanceof ApiError && err.status < 500),
    // A screen's data answering 401 means the session is gone. (Asking who is signed in is allowed to
    // answer 401: the sign-in page asks it too.)
    onError: (err) => {
      if (err instanceof ApiError && err.status === 401 && path !== "/api/auth/me") toSignIn();
    },
    ...config,
  });
}
