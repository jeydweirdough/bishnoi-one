"use client";

import { useEffect } from "react";

/**
 * Starts Bishnoi One's service worker (public/sw.js, Step 4H) on signed-in pages, so the app can be put on a
 * phone's home screen and opens without a signal. Only in a production build: in development it would keep
 * old screens around while they're being changed.
 */
export function RegisterServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
      // No service worker (private browsing, an old browser): the app works as before, online only.
    });
  }, []);
  return null;
}
