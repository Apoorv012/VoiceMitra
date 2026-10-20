"use client";

// "Who is using this device". There are no accounts: a person picks who they are once and the choice is
// remembered, so the installed app opens straight to their own home. A convenience, not security --
// anyone can pick anyone, which is what a real sign-in would replace.

import { useSyncExternalStore } from "react";

export type Identity =
  | { role: "patient"; id: string }
  | { role: "doctor"; id: string }
  | { role: "operator" };

const KEY = "vm_who";
const listeners = new Set<() => void>();

let cachedRaw: string | null | undefined;
let cachedValue: Identity | null = null;

function snapshot(): Identity | null {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    /* storage blocked: behave as signed out */
  }
  if (raw === cachedRaw) return cachedValue; // useSyncExternalStore needs a stable reference
  cachedRaw = raw;
  try {
    cachedValue = raw ? (JSON.parse(raw) as Identity) : null;
  } catch {
    cachedValue = null;
  }
  return cachedValue;
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  window.addEventListener("storage", fn);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("storage", fn);
  };
}

function notify() {
  listeners.forEach((fn) => fn());
}

export function setIdentity(identity: Identity) {
  try {
    localStorage.setItem(KEY, JSON.stringify(identity));
  } catch {
    /* ignore */
  }
  notify();
}

export function clearIdentity() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  notify();
}

/** undefined while the first client render is pending (server markup), then the identity or null. */
export function useIdentity(): Identity | null | undefined {
  return useSyncExternalStore(subscribe, snapshot, () => undefined);
}

export function homePath(identity: Identity): string {
  switch (identity.role) {
    case "patient":
      return `/patients/${identity.id}`;
    case "doctor":
      return `/doctors/${identity.id}`;
    case "operator":
      return "/operator";
  }
}
