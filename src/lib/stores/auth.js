import { writable, derived } from 'svelte/store';
import { currentPage } from './navigation.js';

function getStored(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}

export const token = writable(localStorage.getItem('auth_token') || '');
export const refreshToken = writable(localStorage.getItem('auth_refresh') || '');
export const currentUser = writable(getStored('auth_user'));
export const isAuthenticated = derived(token, $t => !!$t);

token.subscribe(v => { if (v) localStorage.setItem('auth_token', v); else localStorage.removeItem('auth_token'); });
refreshToken.subscribe(v => { if (v) localStorage.setItem('auth_refresh', v); else localStorage.removeItem('auth_refresh'); });
currentUser.subscribe(v => { if (v) localStorage.setItem('auth_user', JSON.stringify(v)); else localStorage.removeItem('auth_user'); });

import { API_BASE } from '../api/client.js';

export async function login(username, password) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(err.detail || 'Login failed');
  }
  const data = await res.json();
  token.set(data.access_token);
  refreshToken.set(data.refresh_token);
  currentUser.set(data.user);
  if (data.must_change_password) {
    currentPage.set('/change-password');
  } else {
    currentPage.set('/');
  }
  return data;
}

export async function register(username, email, password, display_name) {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password, display_name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
    throw new Error(err.detail || 'Registration failed');
  }
  const data = await res.json();
  token.set(data.access_token);
  refreshToken.set(data.refresh_token);
  currentUser.set(data.user);
  currentPage.set('/');
  return data;
}

export function logout() {
  token.set('');
  refreshToken.set('');
  currentUser.set(null);
  currentPage.set('/login');
}

export async function checkAuth() {
  const t = localStorage.getItem('auth_token');
  if (!t) {
    currentPage.set('/login');
    return false;
  }
  // Decode JWT to check expiry (without server call)
  try {
    const payload = JSON.parse(atob(t.split('.')[1]));
    if (payload.exp * 1000 < Date.now()) {
      // Try refresh
      const rt = localStorage.getItem('auth_refresh');
      if (rt) {
        const res = await fetch(`${API_BASE}/api/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (res.ok) {
          const data = await res.json();
          token.set(data.access_token);
          refreshToken.set(data.refresh_token);
          currentUser.set(data.user);
          return true;
        }
      }
      logout();
      return false;
    }
    return true;
  } catch {
    logout();
    return false;
  }
}
