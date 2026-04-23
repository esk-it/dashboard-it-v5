<script>
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';
  import GlassCard from '../GlassCard.svelte';

  let projects = [];
  let loaded = false;

  export function refresh() { fetchData(); }

  onMount(() => { fetchData(); });

  async function fetchData() {
    try {
      const all = await api.get('/api/projects');
      projects = (all || []).filter(p => p.status === 'in_progress').slice(0, 4);
    } catch { /* keep defaults */ }
    loaded = true;
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<GlassCard padding="0">
  <div class="projects-card" on:click={() => currentPage.set('/projects')}>
    <div class="pc-header">
      <h3>Projets actifs</h3>
      <span class="pc-count">{projects.length}</span>
    </div>

    {#if !loaded}
      <p class="pc-muted">Chargement...</p>
    {:else if projects.length === 0}
      <p class="pc-muted">Aucun projet en cours</p>
    {:else}
      <div class="pc-list">
        {#each projects as p}
          <div class="pc-item">
            <div class="pc-item-info">
              <span class="pc-item-color" style="background:{p.color}"></span>
              <span class="pc-item-title">{p.title}</span>
            </div>
            <div class="pc-item-progress">
              <div class="pc-bar"><div class="pc-bar-fill" style="width:{p.progress}%;background:{p.color}"></div></div>
              <span class="pc-pct">{p.progress}%</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</GlassCard>

<style>
  .projects-card { padding: 1rem 1.25rem; cursor: pointer; }
  .pc-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
  .pc-header h3 { margin: 0; font-size: 0.875rem; font-weight: 600; color: var(--text-heading); }
  .pc-count { font-size: 0.75rem; font-weight: 700; color: var(--primary); background: rgba(var(--primary-rgb,99,102,241),0.1); padding: 0.125rem 0.5rem; border-radius: 0.75rem; }
  .pc-muted { color: var(--text-muted); font-size: 0.8125rem; margin: 0; }
  .pc-list { display: flex; flex-direction: column; gap: 0.625rem; }
  .pc-item { }
  .pc-item-info { display: flex; align-items: center; gap: 0.375rem; margin-bottom: 0.25rem; }
  .pc-item-color { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .pc-item-title { font-size: 0.75rem; font-weight: 600; color: var(--text-heading); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pc-item-progress { display: flex; align-items: center; gap: 0.5rem; }
  .pc-bar { flex: 1; height: 4px; background: var(--bg-base); border-radius: 2px; overflow: hidden; }
  .pc-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
  .pc-pct { font-size: 0.625rem; font-weight: 700; color: var(--text-muted); min-width: 28px; text-align: right; }
</style>
