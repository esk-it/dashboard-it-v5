import { writable } from 'svelte/store';

export const toasts = writable([]);
let nextId = 0;

export function addToast(type, message, duration = 4000) {
  const id = nextId++;
  toasts.update(t => [...t, { id, type, message }]);
  setTimeout(() => {
    toasts.update(t => t.filter(toast => toast.id !== id));
  }, duration);
}

export function success(msg) { addToast('success', msg); }
export function error(msg) { addToast('error', msg); }
export function warning(msg) { addToast('warning', msg); }
export function info(msg) { addToast('info', msg); }
export function mail(msg) { addToast('mail', msg, 6000); }
export function alert_critical(msg) { addToast('alert_critical', msg, 8000); }
