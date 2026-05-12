// Cache + accessors for the 3 establishments (NDK / SU / NDE). Loaded once
// at app startup and after edits in the Settings panel. Components import
// `<EstablishmentBadge code="NDK" />` rather than fetching directly — the
// store keeps a single in-memory copy so every render reads from the same
// reactive source instead of refetching the list per component mount.
//
// Shape of each establishment:
//   { id, code, name, color, has_logo, aliases: [...], sort_order }

import { writable, derived, get } from 'svelte/store';
import { API_BASE, api } from '../api/client.js';

export const establishments = writable([]);
export const establishmentsLoaded = writable(false);

// O(1) lookup by code — derived from the list. Components use it to render
// a badge given just a code string.
export const establishmentsByCode = derived(establishments, ($list) => {
  const out = {};
  for (const e of $list) out[e.code] = e;
  return out;
});

export async function loadEstablishments() {
  try {
    const list = await api.get('/api/establishments');
    establishments.set(Array.isArray(list) ? list : []);
  } catch {
    // Backend down or endpoint not yet deployed — leave the cache empty so
    // the UI just falls back to text without crashing.
    establishments.set([]);
  } finally {
    establishmentsLoaded.set(true);
  }
}

// URL of the logo file. We add a bust param tied to has_logo (and the
// establishment id) so updates show up immediately after upload without
// fighting the browser cache for stale image bytes.
export function logoUrl(establishment) {
  if (!establishment || !establishment.has_logo) return null;
  // Tiny cache-buster: re-use logo_path's hash component if present.
  const v = establishment.logo_path ? establishment.logo_path.split('_').pop() : 'v';
  return `${API_BASE}/api/establishments/${establishment.id}/logo?v=${encodeURIComponent(v)}`;
}

// Convenience helpers (sync — read the current store value once).
export function getByCode(code) {
  if (!code) return null;
  const list = get(establishments);
  return list.find(e => e.code === code) || null;
}

export function siteOptions() {
  // For dropdowns — returns [{ value: '', label: '— Aucun —' }, { value: 'NDK', label: 'NDK · Lycée…' }, …]
  const list = get(establishments);
  return [
    { value: '', label: '— Aucun —' },
    ...list.map(e => ({ value: e.code, label: `${e.code} · ${e.name}` })),
  ];
}
