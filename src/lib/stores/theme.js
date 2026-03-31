import { writable } from 'svelte/store';

// Theme: 'dark' or 'light'
const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('itm-theme') : null;
// Migrate old theme names
const initial = stored === 'glass' ? 'dark' : stored === 'glass-light' ? 'light' : (stored || 'dark');
export const theme = writable(initial);

// Apply theme to DOM
theme.subscribe(value => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', value);
    localStorage.setItem('itm-theme', value);
  }
});

export function toggleTheme() {
  theme.update(t => t === 'dark' ? 'light' : 'dark');
}
