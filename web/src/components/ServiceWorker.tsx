"use client";

import { useEffect } from "react";

/**
 * Registers the app-shell service worker in production builds only. In `next dev` it removes any worker
 * (and its cache) left by an earlier production run, so stale caches never hide code changes.
 */
export default function ServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return; // not available over plain HTTP either (not a secure context)
    if (process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch((e) => console.warn("service worker not registered:", e));
    } else {
      navigator.serviceWorker.getRegistrations().then((rs) => rs.forEach((r) => void r.unregister())).catch(() => {});
      if ("caches" in window) caches.keys().then((ks) => ks.filter((k) => k.startsWith("hikesense-")).forEach((k) => void caches.delete(k))).catch(() => {});
    }
  }, []);
  return null;
}
