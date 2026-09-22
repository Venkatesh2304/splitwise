import { api } from './api';

// Push notifications for this device.
// States: 'unsupported' (browser can't), 'insecure' (page is on http://), 'denied'
// (user blocked it), 'off' (allowed or not asked, but not subscribed), 'on'.

export function isPushSupported() {
  return typeof window !== 'undefined'
    && 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window;
}

export function registerServiceWorker() {
  if (!isPushSupported() || !window.isSecureContext) return;
  navigator.serviceWorker.register('/sw.js').catch((err) => {
    console.error('Service worker registration failed:', err);
  });
}

async function getRegistration() {
  if (!isPushSupported() || !window.isSecureContext) return null;
  // .ready never settles if registration failed, so don't wait forever
  const timeout = new Promise((resolve) => setTimeout(() => resolve(null), 5000));
  return Promise.race([navigator.serviceWorker.ready, timeout]);
}

async function currentSubscription() {
  const reg = await getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

export async function getPushState() {
  if (typeof window !== 'undefined' && !window.isSecureContext) return 'insecure';
  if (!isPushSupported()) return 'unsupported';
  if (Notification.permission === 'denied') return 'denied';
  const sub = await currentSubscription();
  return sub && Notification.permission === 'granted' ? 'on' : 'off';
}

function urlBase64ToUint8Array(base64) {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(padded);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function sameKey(subscription, publicKey) {
  const current = subscription.options && subscription.options.applicationServerKey;
  if (!current) return true; // browser doesn't expose it; assume fine
  const a = new Uint8Array(current);
  const b = urlBase64ToUint8Array(publicKey);
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

async function subscribeWithServerKey(reg) {
  const { public_key: publicKey } = await api.getPushPublicKey();
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub, publicKey)) {
    // Server key changed since this device subscribed: the old subscription is dead
    await sub.unsubscribe();
    sub = null;
  }
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }
  return sub;
}

// Must be called from a tap/click: browsers only show the permission prompt then.
export async function enablePush(user) {
  if (!user) throw new Error('Log in first.');
  const state = await getPushState();
  if (state === 'insecure') throw new Error('Notifications need the secure (https) address of the app.');
  if (state === 'unsupported') throw new Error('This browser does not support notifications. On iPhone, add the app to your Home Screen first.');

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error(permission === 'denied'
      ? 'Notifications are blocked. Allow them in the browser’s site settings, then try again.'
      : 'Notifications were not allowed.');
  }

  const reg = await getRegistration();
  if (!reg) throw new Error('The app\u2019s background worker did not start. Reload the page and try again.');
  const sub = await subscribeWithServerKey(reg);
  await api.pushSubscribe(user.id, sub.toJSON());
  return 'on';
}

// On app start / login: make sure this device's subscription is filed under this user.
export async function resyncPush(user) {
  try {
    if (!user || (await getPushState()) !== 'on') return;
    const reg = await getRegistration();
    if (!reg) return;
    const sub = await subscribeWithServerKey(reg);
    await api.pushSubscribe(user.id, sub.toJSON());
  } catch (err) {
    console.error('Could not refresh the push subscription:', err);
  }
}

// On logout / turning it off: this device stops receiving this user's notifications.
export async function disablePush() {
  try {
    const sub = await currentSubscription();
    if (!sub) return;
    await api.pushUnsubscribe(sub.endpoint).catch(() => {});
    await sub.unsubscribe();
  } catch (err) {
    console.error('Could not turn notifications off:', err);
  }
}
