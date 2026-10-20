"use client";

import { useEffect } from "react";

/**
 * Registers the service worker so the app can be installed. Production only: in `next dev` a service
 * worker would serve stale code and make hot reload confusing.
 */
export function PwaRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
      /* installability is a nicety; the app works without it */
    });
  }, []);
  return null;
}
