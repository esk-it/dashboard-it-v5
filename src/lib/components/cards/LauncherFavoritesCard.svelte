<script>
  // Compact row of favorite launchers on the Home page. Reads from /api/launcher
  // and renders only items with favorite=true. Click → opens the URL in the
  // default browser (via Tauri shell when available, falls back to window.open
  // in dev/web mode).

  import { onMount } from 'svelte';
  import { api, API_BASE } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';

  let favorites = [];
  let loaded = false;

  export function refresh() { fetchData(); }

  onMount(() => fetchData());

  async function fetchData() {
    try {
      const all = await api.get('/api/launcher');
      favorites = (all || []).filter(l => l.favorite);
    } catch {
      favorites = [];
    }
    loaded = true;
  }

  // Resolve the right image src or emoji to render. Same shape as the launcher
  // page so the visual matches.
  function iconDisplay(link) {
    if (link.icon_type === 'local') {
      // Bust cache when icon_value changes (filename includes content hash-ish suffix).
      return { type: 'img', value: `${API_BASE}/api/launcher/${link.id}/icon?v=${encodeURIComponent(link.icon_value || '')}` };
    }
    if (link.icon_type === 'url' && link.icon_value) {
      return { type: 'img', value: link.icon_value };
    }
    return { type: 'emoji', value: link.icon_value || '🔗' };
  }

  async function openLink(link) {
    if (!link.url) return;
    // Prefer Tauri's plugin-shell so the URL opens in the default browser
    // rather than the embedded WebView. The dynamic import lets this work in
    // both Tauri builds and the dev/web server (browser fallback below).
    try {
      const { open } = await import('@tauri-apps/plugin-shell');
      await open(link.url);
      return;
    } catch {}
    window.open(link.url, '_blank', 'noopener,noreferrer');
  }

  function goLauncher() {
    currentPage.set('/launcher');
  }
</script>

<div class="lf-wrap">
  {#if !loaded}
    <div class="lf-empty">Chargement…</div>
  {:else if favorites.length === 0}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="lf-empty lf-empty--clickable" on:click={goLauncher}>
      Aucun favori. <span class="lf-empty-action">Va dans le module Lanceur pour en marquer un.</span>
    </div>
  {:else}
    <div class="lf-grid">
      {#each favorites as link (link.id)}
        {@const icon = iconDisplay(link)}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <button
          class="lf-btn"
          title={link.name + (link.description ? ' — ' + link.description : '')}
          on:click={() => openLink(link)}
          style="--lf-color: {link.color || '#6C63FF'}"
        >
          <span class="lf-icon">
            {#if icon.type === 'img'}
              <img src={icon.value} alt="" />
            {:else}
              <span class="lf-emoji">{icon.value}</span>
            {/if}
          </span>
          <span class="lf-name">{link.name}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .lf-wrap { width: 100%; }

  .lf-empty {
    padding: 1.5rem 1.25rem;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8125rem;
  }
  .lf-empty--clickable {
    cursor: pointer;
    transition: color 0.15s;
  }
  .lf-empty--clickable:hover { color: var(--primary); }
  .lf-empty-action { color: var(--primary); }

  .lf-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.625rem;
    padding: 0.625rem 1.25rem 1.25rem;
  }

  .lf-btn {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.625rem 0.75rem;
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--lf-color, var(--primary));
    border-radius: 0.5rem;
    cursor: pointer;
    transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
    font-family: inherit;
    text-align: left;
    min-width: 0;
  }
  .lf-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    background: var(--bg-hover, var(--bg-card));
  }

  .lf-icon {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    background: color-mix(in srgb, var(--lf-color, var(--primary)) 15%, transparent);
  }
  .lf-icon img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }
  .lf-emoji {
    font-size: 1.125rem;
    line-height: 1;
  }

  .lf-name {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-heading);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }
</style>
