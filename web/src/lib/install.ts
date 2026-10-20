"use client";

import { useSyncExternalStore } from "react";

// "Add to home screen". Chrome/Android fires `beforeinstallprompt` (we keep it and show our own button);
// iPhone Safari has no such event, so there we can only show the manual Share -> Add to Home Screen steps.

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
type InstallState = { installed: boolean; canPrompt: boolean; showIosSteps: boolean };

let deferred: InstallEvent | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((fn) => fn());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e as InstallEvent;
    notify();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    notify();
  });
}

const SERVER: InstallState = { installed: false, canPrompt: false, showIosSteps: false };
let current: InstallState = SERVER;

/** A new object only when something changed, so React doesn't re-render for nothing. */
function snapshot(): InstallState {
  const installed =
    window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;
  const next: InstallState = {
    installed,
    canPrompt: deferred !== null,
    showIosSteps: /iphone|ipad|ipod/i.test(navigator.userAgent) && !installed,
  };
  if (
    next.installed !== current.installed || next.canPrompt !== current.canPrompt || next.showIosSteps !== current.showIosSteps
  ) {
    current = next;
  }
  return current;
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function useInstall() {
  const state = useSyncExternalStore(subscribe, snapshot, () => SERVER);
  return {
    ...state,
    prompt: async () => {
      if (!deferred) return;
      await deferred.prompt();
      await deferred.userChoice;
      deferred = null;
      notify();
    },
  };
}
