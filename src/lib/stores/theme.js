import { writable } from 'svelte/store';

// Theme: 'glass' (dark) or 'glass-light' (light)
// Read from localStorage if user toggled theme, otherwise default to glass-light
const _saved = typeof localStorage !== 'undefined' ? localStorage.getItem('itm-theme') : null;
export const theme = writable(_saved || 'glass-light');
export const accent = writable('#452B90');

// Apply theme to DOM — single source of truth
theme.subscribe(value => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', value);
    localStorage.setItem('itm-theme', value);
    if (value === 'glass-light') {
      document.documentElement.style.colorScheme = 'light';
      document.body.style.background = '#E8ECF2';
    } else {
      document.documentElement.style.colorScheme = 'dark';
      document.body.style.background = '';
    }
  }
});

export function toggleTheme() {
  theme.update(t => t === 'glass' ? 'glass-light' : 'glass');
}
