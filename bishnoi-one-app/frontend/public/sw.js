// Bishnoi One's service worker (Step 4H, 2026-11-18): the app opens without a signal, so a field agent can
// still log visits (kept on the phone by src/modules/crm/components/field/offline-queue.ts).
//
// Kept deliberately small:
// - Built files (/_next/static, hashed, never change) and the brand images: from the cache once fetched.
// - Pages: always from the network first. Only the few a field agent needs offline (FIELD_PAGES) are kept,
//   the last copy of each, so they open offline; any other page offline shows /offline.html.
// - Never kept: API calls, server actions, the screens' data requests (RSC), anything not a GET, anything
//   from another site. A signed-out visit (sent to /login) drops the kept pages.
// - Background Sync: when the phone is back online it tells the open app to send what's waiting.
//
// Change VERSION when this file's caching changes: the old caches are dropped on activation.

const VERSION = "v1";
const STATIC = `bishnoi-static-${VERSION}`;
const PAGES = `bishnoi-pages-${VERSION}`;
const OFFLINE = "/offline.html";
const MOST_STATIC = 400;
const FIELD_PAGES = ["/", "/crm", "/crm/field", "/crm/field/doctors", "/crm/visits", "/crm/visits/new"];
const SYNC_TAG = "bishnoi-field-send";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC)
      .then((cache) => cache.addAll([OFFLINE, "/brand/app-192.png"]))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n.startsWith("bishnoi-") && n !== STATIC && n !== PAGES).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "forget-pages") event.waitUntil(caches.delete(PAGES));
});

function isStatic(url) {
  return url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/brand/");
}

async function trim(cache) {
  const keys = await cache.keys();
  for (const key of keys.slice(0, Math.max(0, keys.length - MOST_STATIC))) await cache.delete(key);
}

async function fromCacheFirst(request) {
  const cache = await caches.open(STATIC);
  const kept = await cache.match(request);
  if (kept) return kept;
  const response = await fetch(request);
  if (response.ok && response.type === "basic") {
    await cache.put(request, response.clone());
    trim(cache);
  }
  return response;
}

async function page(request, url) {
  if (url.pathname === "/login" || url.pathname.startsWith("/login/")) {
    await caches.delete(PAGES);
    return fetch(request);
  }
  const keep = FIELD_PAGES.includes(url.pathname.replace(/\/$/, "") || "/");
  try {
    const response = await fetch(request);
    const landed = new URL(response.url || url.href);
    if (landed.pathname.startsWith("/login")) {
      await caches.delete(PAGES);
    } else if (keep && response.ok && response.type === "basic" && (response.headers.get("content-type") || "").includes("text/html")) {
      const cache = await caches.open(PAGES);
      // One copy per page, whatever its query: the newest.
      await cache.put(new Request(url.origin + url.pathname), response.clone());
    }
    return response;
  } catch {
    if (keep) {
      const kept = await caches.open(PAGES).then((cache) => cache.match(url.origin + url.pathname));
      if (kept) return kept;
    }
    return (await caches.match(OFFLINE)) || new Response("You're offline.", { status: 503, headers: { "Content-Type": "text/plain" } });
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (request.mode === "navigate") {
    event.respondWith(page(request, url));
    return;
  }
  // The screens' data (RSC requests carry the RSC header or _rsc) and every API call go straight to the network.
  if (request.headers.get("RSC") || url.searchParams.has("_rsc")) return;
  if (isStatic(url)) event.respondWith(fromCacheFirst(request));
});

self.addEventListener("sync", (event) => {
  if (event.tag !== SYNC_TAG) return;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) client.postMessage({ type: "send" });
    }),
  );
});
