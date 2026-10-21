"use client";

import { useEffect } from "react";

/**
 * Registers the service worker so the app can be installed, in production only.
 *
 * Everywhere else it does the opposite and removes any worker (and its caches) left on this origin by an
 * earlier production run. The worker serves `/_next/static/*` from its cache first; after switching from the
 * built app to `next dev` on the same address that would hand the dev server stale chunks.
 */
export function PwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    if (process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
        /* installability is a nicety; the app works without it */
      });
      return;
    }

    void (async () => {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((r) => r.unregister()));
      if ("caches" in window) {
        const stale = (await caches.keys()).filter((k) => k.startsWith("voicemitra-"));
        await Promise.all(stale.map((k) => caches.delete(k)));
      }
      // A worker that was just unregistered keeps controlling this page until it reloads, and it would
      // re-create its cache from the requests that follow. One reload gets a page with no worker in the
      // way (the guard stops it reloading again).
      if (navigator.serviceWorker.controller && !sessionStorage.getItem("vm-sw-cleaned")) {
        sessionStorage.setItem("vm-sw-cleaned", "1");
        location.reload();
      }
    })().catch(() => {
      /* cleanup is best effort */
    });
  }, []);
  return null;
}
