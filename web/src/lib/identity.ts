"use client";

// Who is signed in. The API decides (a session cookie set by POST /api/auth/session); this only asks it
// (GET /api/auth/me) so screens can greet the person and send them to their own home. Every API call is
// checked again on the server, so nothing here is security.

import { mutate } from "swr";
import { api, useApi } from "@/lib/api";
import type { components } from "@/lib/api-schema";

export type Me = components["schemas"]["Me"];

export const ME_PATH = "/api/auth/me";

/** undefined while loading, null when nobody is signed in, otherwise who it is. */
export function useIdentity(): Me | null | undefined {
  const { data, error } = useApi<Me>(ME_PATH, 0, { shouldRetryOnError: false, revalidateOnFocus: true });
  if (data) return data;
  if (error) return error.status === 401 ? null : undefined; // a network error: keep waiting, don't bounce
  return undefined;
}

export function homePath(me: Me): string {
  switch (me.role) {
    case "patient":
      return `/patients/${me.id}`;
    case "caregiver":
      return `/caregivers/${me.id}`;
    case "staff":
      return "/operator";
  }
}

/** Sign in on this browser; returns who it is. Throws ApiError (401 wrong, 429 paused). */
export async function signIn(username: string, password: string): Promise<Me> {
  const me = await api<Me>("/api/auth/session", { method: "POST", json: { username, password } });
  await mutate(ME_PATH, me, { revalidate: false });
  return me;
}

/** Sign out and start fresh at the sign-in page (a full load, so no one's data stays in memory). */
export async function signOut(): Promise<void> {
  try {
    await api("/api/auth/session", { method: "DELETE" });
  } finally {
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- a full load on purpose
    window.location.assign("/login");
  }
}

/** Where to go after signing in: `?next=` if it is a path on this site, else the person's home. */
export function afterSignIn(me: Me, next: string | null): string {
  if (next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login")) return next;
  return homePath(me);
}
