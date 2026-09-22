// Service worker: shows push notifications and opens the app when one is tapped.
//
// Deliberately has NO fetch handler and caches nothing. A caching worker can pin
// phones to an old build after a deploy; push doesn't need one.

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: 'Splitwise', body: event.data ? event.data.text() : '' };
  }

  const title = data.title || 'Splitwise';
  const options = {
    body: data.body || '',
    icon: '/icons/icon-192.png',
    badge: '/icons/badge-96.png',
    tag: data.tag || undefined,
    renotify: Boolean(data.tag),
    data: { url: data.url || '/' },
    timestamp: Date.now(),
  };

  event.waitUntil((async () => {
    await self.registration.showNotification(title, options);
    // An open copy of the app refreshes its data
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    windows.forEach((client) => client.postMessage({ type: 'splitwise:changed', groupId: data.group_id }));
  })());
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin).href;

  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (existing) {
      await existing.focus();
      existing.postMessage({ type: 'splitwise:open', url });
      return;
    }
    await self.clients.openWindow(url);
  })());
});
