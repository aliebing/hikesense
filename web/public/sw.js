// Minimal service worker: caches only the app shell (own static files) so the app is installable and starts offline.
// Never cached: map tiles, API responses, Supabase calls, pages with data, anything cross-origin or non-GET.
const CACHE = "hikeall-shell-v1";
const SHELL = ["/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png", "/favicon.ico"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  // Only same-origin GETs for the shell files and Next's hashed static assets; everything else goes to the network untouched.
  const isShell = SHELL.includes(url.pathname) || url.pathname.startsWith("/_next/static/");
  if (req.method !== "GET" || url.origin !== self.location.origin || !isShell) return;
  event.respondWith(
    caches.match(req).then(
      (hit) =>
        hit ||
        fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        }),
    ),
  );
});
