/* Norbert Desk — offline service worker.
   Precaches the whole app shell so the home-screen app works with no internet
   after the first visit. Bump CACHE to ship an update. */
const CACHE = 'norbert-desk-v1';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then(hit => {
      if (hit) return hit;
      return fetch(e.request).then(resp => {
        try { const cp = resp.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); } catch (_) {}
        return resp;
      }).catch(() => caches.match('./index.html'));
    })
  );
});
