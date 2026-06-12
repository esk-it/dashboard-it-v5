<script>
  /**
   * v7.5.0 — « Ce qui demande ton attention »
   *
   * Card cross-module sur la home qui agrège les items urgents/importants :
   * tâches en retard, dossiers sans activité, chromebooks fin de support,
   * garanties qui expirent, backups qui dorment, etc. Source unique :
   * GET /api/dashboard/attention. Chaque item a une cible (page) cliquable.
   */
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';
  import {
    AlertTriangle, AlertCircle, Folder, FileText, Laptop, Shield,
    Database, CheckCircle2,
  } from 'lucide-svelte';

  let items = [];
  let loading = true;
  let lastError = '';

  // Map of icon name from backend → component (frontend doesn't depend on backend).
  const iconMap = {
    AlertTriangle, Folder, FileText, Laptop, Shield, Database,
  };

  async function refresh() {
    loading = true;
    try {
      const data = await api.get('/api/dashboard/attention');
      items = data.items || [];
      lastError = '';
    } catch (e) {
      lastError = e.message || 'Erreur';
      items = [];
    }
    loading = false;
  }

  function go(target) {
    if (target) currentPage.set(target);
  }

  // Expose refresh to parent
  export { refresh };

  onMount(() => { refresh(); });
</script>

<div class="attention-card" class:empty={items.length === 0}>
  <header class="attention-header">
    <h3>À regarder</h3>
    {#if items.length > 0}
      <span class="attention-count">{items.length}</span>
    {/if}
  </header>

  {#if loading}
    <div class="attention-loading">Chargement…</div>
  {:else if lastError}
    <div class="attention-error">Erreur : {lastError}</div>
  {:else if items.length === 0}
    <div class="attention-empty">
      <CheckCircle2 size={28} />
      <p>Tout va bien — rien à signaler pour le moment.</p>
    </div>
  {:else}
    <div class="attention-list">
      {#each items as item (item.kind)}
        {@const Icon = iconMap[item.icon] || AlertCircle}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="attention-item severity-{item.severity}" on:click={() => go(item.target)}>
          <div class="attention-icon">
            <Icon size={16} />
          </div>
          <div class="attention-content">
            <div class="attention-title">{item.title}</div>
            <div class="attention-sub">{item.sub}</div>
          </div>
          <div class="attention-arrow">→</div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .attention-card {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    padding: 16px 18px 14px;
    display: flex; flex-direction: column; gap: 10px;
    box-shadow: var(--shadow-card, none);
  }
  .attention-card.empty { padding-bottom: 18px; }

  .attention-header {
    display: flex; justify-content: space-between; align-items: center;
  }
  .attention-header h3 {
    margin: 0; font-size: 15px; font-weight: 700;
    color: var(--text-heading);
  }
  .attention-count {
    background: var(--accent); color: #fff;
    padding: 2px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 700;
  }

  .attention-loading,
  .attention-error,
  .attention-empty {
    font-size: 13px; color: var(--text-secondary);
    text-align: center; padding: 18px 0;
  }
  .attention-empty {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    color: var(--text-muted);
  }
  .attention-empty :global(svg) { color: #22C55E; }
  .attention-empty p { margin: 0; }
  .attention-error { color: #EF4444; }

  .attention-list {
    display: flex; flex-direction: column; gap: 6px;
  }
  .attention-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; border-radius: 8px;
    background: var(--bg-input);
    border: 1px solid transparent;
    cursor: pointer;
    transition: border-color 0.15s, transform 0.15s;
  }
  .attention-item:hover {
    border-color: var(--accent);
    transform: translateX(2px);
  }
  .attention-item.severity-critical { border-left: 3px solid #EF4444; }
  .attention-item.severity-warning { border-left: 3px solid #F59E0B; }
  .attention-item.severity-info { border-left: 3px solid #3B82F6; }

  .attention-icon {
    width: 32px; height: 32px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    background: var(--bg-card);
    flex-shrink: 0;
  }
  .severity-critical .attention-icon { color: #EF4444; background: rgba(239, 68, 68, 0.12); }
  .severity-warning .attention-icon { color: #F59E0B; background: rgba(245, 158, 11, 0.12); }
  .severity-info .attention-icon { color: #3B82F6; background: rgba(59, 130, 246, 0.12); }

  .attention-content { flex: 1; min-width: 0; }
  .attention-title {
    font-size: 13px; font-weight: 600; color: var(--text-heading);
    margin-bottom: 2px;
  }
  .attention-sub {
    font-size: 11px; color: var(--text-muted);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .attention-arrow {
    color: var(--text-muted);
    font-size: 16px; font-weight: 700;
    flex-shrink: 0;
    transition: transform 0.15s, color 0.15s;
  }
  .attention-item:hover .attention-arrow { color: var(--accent); transform: translateX(2px); }
</style>
