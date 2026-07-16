{% load static %}// Халтарынхан · service worker
const CACHE = 'haltarynkhan-v1';

// Апп нээгдэхэд шаардлагатай суурь файлууд
const SHELL = [
  '{% static "tree/icon-192.png" %}',
  '{% static "tree/icon-512.png" %}',
  '{% static "tree/apple-touch-icon.png" %}',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Зөвхөн GET хүсэлтийг барина. POST (нэвтрэх, засах г.м) шууд сүлжээгээр явна.
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;

  // Сүлжээг эхэлж оролдоод, амжилттай бол хуулбарыг кэшлэнэ.
  // Сүлжээ тасарсан үед кэшнээс өгнө.
  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((cache) => cache.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match('/')))
  );
});
