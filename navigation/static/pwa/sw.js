/* Offline support: the app shell + last saved map keep working without internet. */
const C = 'svsu-nav-v2';
const SHELL = ['/', '/manifest.webmanifest', '/static/pwa/icon-192.png', '/static/pwa/icon-512.png',
  '/static/vendor/qrcode.js', '/static/vendor/html5-qrcode.min.js', '/static/fonts/inter-400.woff2', '/static/fonts/inter-600.woff2', '/static/fonts/inter-700.woff2'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(C).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  if (u.pathname.startsWith('/admin') || u.pathname.startsWith('/editor') || u.pathname === '/api/me/') return;
  // network first (always fresh when online), cached copy when offline
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) { const cp = r.clone(); caches.open(C).then(c => c.put(e.request, cp)); }
    return r;
  }).catch(() => caches.match(e.request, {ignoreSearch: true}).then(m => m || (e.request.mode === 'navigate' ? caches.match('/') : Response.error()))));
});
