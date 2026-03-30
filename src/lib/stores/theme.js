import { writable } from 'svelte/store';

// Theme: 'glass' (dark) or 'glass-light'
const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('itm-theme') : null;
export const theme = writable(stored || 'glass');
export const accent = writable('#06A6C9');

// Apply theme to DOM
theme.subscribe(value => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', value);
    localStorage.setItem('itm-theme', value);
  }
});

export function toggleTheme() {
  theme.update(t => t === 'glass' ? 'glass-light' : 'glass');
}
