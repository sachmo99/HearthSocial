const CACHE = "hearthsocial-shell-v7";
const SHELL = ["/", "/index.html"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Never touch API or portrait traffic - this app needs live data from the backend for
// everything (chat, feed, characters, avatars), and any cache involvement here risks
// silently serving stale state. Only the static app shell goes through this cache.
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/portraits/")
  ) {
    return;
  }
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
