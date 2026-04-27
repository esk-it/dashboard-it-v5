// Backend health monitor.
// Pings /api/health every 30 s and exposes a reactive `isOnline` store + a
// `failureStreak` count. After 2 consecutive failures the UI shows a red
// banner so the user knows the sidecar is dead instead of staring at a
// silently broken page.

import { writable, get } from 'svelte/store';
import { API_BASE } from '../api/client.js';

export const isOnline = writable(true);
export const failureStreak = writable(0);
export const lastCheckAt = writable(0);

const POLL_MS = 30_000;
const TIMEOUT_MS = 4_000;
const FAILURE_THRESHOLD = 2; // mark offline after this many consecutive failures

let pollTimer = null;

async function ping() {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_BASE}/api/health`, { signal: ctrl.signal, cache: 'no-store' });
    clearTimeout(t);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    failureStreak.set(0);
    isOnline.set(true);
  } catch {
    const next = get(failureStreak) + 1;
    failureStreak.set(next);
    if (next >= FAILURE_THRESHOLD) isOnline.set(false);
  } finally {
    lastCheckAt.set(Date.now());
  }
}

export function startHealthPolling() {
  if (pollTimer) return;
  // Immediate first ping so the banner appears fast on startup if backend missing.
  ping();
  pollTimer = setInterval(ping, POLL_MS);
}

export function stopHealthPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

// Triggered manually when the user clicks "Réessayer" in the banner.
export async function recheckNow() {
  await ping();
  return get(isOnline);
}
