var CACHE_NAME = 'lds-reader-v1';
var SHELL_ASSETS = [
    './index.html',
    './style/main.css',
    './toc.json'
];

// Install: pre-cache shell assets only
self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(SHELL_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate: delete old caches
self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(key) { return key !== CACHE_NAME; })
                    .map(function(key) { return caches.delete(key); })
            );
        })
    );
    self.clients.claim();
});

// Fetch: routing strategy
self.addEventListener('fetch', function(event) {
    var url = event.request.url;
    var path = new URL(url).pathname;

    // Cache-first for chapter HTML files
    if (path.includes('/chapters/') && path.endsWith('.html')) {
        event.respondWith(cacheFirst(event.request));
        return;
    }

    // Network-first for toc.json and search.json
    if (path.endsWith('/toc.json') || path.endsWith('/search.json')) {
        event.respondWith(networkFirst(event.request));
        return;
    }

    // Network-first for everything else
    event.respondWith(networkFirst(event.request));
});

function cacheFirst(request) {
    return caches.open(CACHE_NAME).then(function(cache) {
        return cache.match(request).then(function(cached) {
            if (cached) return cached;
            return fetch(request).then(function(response) {
                if (response && response.status === 200) {
                    cache.put(request, response.clone());
                }
                return response;
            });
        });
    });
}

function networkFirst(request) {
    return fetch(request).then(function(response) {
        if (response && response.status === 200) {
            caches.open(CACHE_NAME).then(function(cache) {
                cache.put(request, response.clone());
            });
        }
        return response;
    }).catch(function() {
        return caches.match(request);
    });
}
