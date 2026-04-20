import { writable } from 'svelte/store';
import { api } from '../api/client.js';
import { theme } from './theme.js';

export const settings = writable({
  username: '',
  auto_refresh_minutes: 5,
  max_home_tasks: 10,
  language: 'fr',
  enabled_modules: {},
});

export async function loadSettings() {
  // Retry — backend sidecar takes a few seconds to start
  for (let attempt = 0; attempt < 8; attempt++) {
    try {
      const data = await api.get('/api/settings/general');
      if (data && typeof data === 'object') {
        settings.set(data);
        break;
      }
    } catch (e) {
      if (attempt < 7) {
        await new Promise(r => setTimeout(r, 2000));
      } else {
        console.warn('Failed to load settings after retries:', e);
      }
    }
  }

  // Theme is managed client-side via theme.js store (localStorage)
  // No backend sync needed — toggleTheme in navbar handles persistence

  // Apply compact mode from localStorage
  if (localStorage.getItem('itm-compact') === '1') {
    document.documentElement.setAttribute('data-compact', 'true');
  }
}
