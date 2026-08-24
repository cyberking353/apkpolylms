/*
 * Al-Hikma LMS service worker.
 * Strategy:
 *   - Static assets (css/js/images/fonts): cache-first (fast, versioned by ?v=)
 *   - Page navigations: network-first, fall back to last cached copy, then /offline/
 * Never caches POST requests or /api/ /portal-admin/ traffic.
 */
const STATIC_CACHE = 'alhikma-static-v1';
const PAGE_CACHE = 'alhikma-pages-v1';

const PRECACHE = [
    '/static/css/main.css',
    '/static/js/main.js',
    '/static/images/logo.png',
    '/static/images/icon-192.png',
    '/static/manifest.json',
    '/offline/',
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then(cache => cache.addAll(PRECACHE))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== STATIC_CACHE && k !== PAGE_CACHE)
                    .map(k => caches.delete(k))
            ).then(() => self.clients.claim())
        )
    );
});

// allow the page to trigger immediate activation of a new worker
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // only handle same-origin GET
    if (event.request.method !== 'GET' || url.origin !== location.origin) return;
    // never interfere with admin or api
    if (url.pathname.startsWith('/portal-admin/') || url.pathname.startsWith('/api/')) return;

    // static assets: cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then(cached => cached ||
                fetch(event.request).then(resp => {
                    const copy = resp.clone();
                    caches.open(STATIC_CACHE).then(c => c.put(event.request, copy));
                    return resp;
                })
            )
        );
        return;
    }

    // page navigations: network-first with offline fallbacks
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).then(resp => {
                const copy = resp.clone();
                caches.open(PAGE_CACHE).then(c => c.put(event.request, copy));
                return resp;
            }).catch(() =>
                caches.match(event.request)
                    .then(cached => cached ||
                        caches.match('/offline/')
                        .then(off => off || caches.match('/')))
            )
        );
    }
});
