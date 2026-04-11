<script>
  import { onMount } from 'svelte';
  import { api } from '../../api/client.js';
  import { currentPage } from '../../stores/navigation.js';
  import GlassCard from '../GlassCard.svelte';

  let configured = false;
  let stats = { total_hosts: 0, available: 0, unavailable: 0, active_problems: 0 };
  let problems = [];
  let loaded = false;

  export function refresh() {
    fetchData();
  }

  onMount(() => { fetchData(); });

  async function fetchData() {
    try {
      const cfg = await api.get('/api/monitoring/config');
      configured = cfg.configured;
      if (!configured) { loaded = true; return; }
      const [st, pb] = await Promise.all([
        api.get('/api/monitoring/stats'),
        api.get('/api/monitoring/problems'),
      ]);
      stats = st;
      problems = pb.slice(0, 5);
    } catch { /* keep defaults */ }
    loaded = true;
  }

  function severityColor(sev) {
    const s = (sev || '').toLowerCase();
    if (s === 'catastrophe') return '#EF4444';
    if (s === 'élevé') return '#F97316';
    if (s === 'moyen') return '#EAB308';
    if (s === 'avertissement') return '#FBBF24';
    return '#64748B';
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<GlassCard padding="0">
  <div class="zabbix-card" on:click={() => currentPage.set('/monitoring')}>
    <div class="zabbix-header">
      <h3>Zabbix</h3>
      {#if configured && stats.active_problems > 0}
        <span class="zabbix-badge" style="background:#EF4444">{stats.active_problems}</span>
      {:else if configured}
        <span class="zabbix-dot ok"></span>
      {/if}
    </div>

    {#if !loaded}
      <p class="zabbix-muted">Chargement...</p>
    {:else if !configured}
      <p class="zabbix-muted">Non configure</p>
    {:else if stats.active_problems === 0}
      <div class="zabbix-ok">
        <span class="zabbix-ok-icon">&#10003;</span>
        <span>Aucun probleme</span>
      </div>
      <div class="zabbix-stats">
        <span>{stats.total_hosts} hotes</span>
        <span class="zabbix-dot-inline ok"></span>
        <span>Tout OK</span>
      </div>
    {:else}
      <div class="zabbix-problems">
        {#each problems as p}
          <div class="zabbix-problem">
            <span class="zabbix-sev" style="background:{severityColor(p.severity)}"></span>
            <span class="zabbix-problem-host">{p.host}</span>
            <span class="zabbix-problem-name">{p.name}</span>
          </div>
        {/each}
      </div>
      <div class="zabbix-stats">
        <span>{stats.total_hosts} hotes</span>
        <span class="sep">|</span>
        <span style="color:#EF4444">{stats.active_problems} probleme{stats.active_problems > 1 ? 's' : ''}</span>
      </div>
    {/if}
  </div>
</GlassCard>

<style>
  .zabbix-card { padding: 1rem 1.25rem; cursor: pointer; }
  .zabbix-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
  .zabbix-header h3 { margin: 0; font-size: 0.875rem; font-weight: 600; color: var(--text-heading); }
  .zabbix-badge {
    min-width: 20px; height: 20px; border-radius: 10px; color: #fff;
    font-size: 0.6875rem; font-weight: 700; display: flex; align-items: center; justify-content: center; padding: 0 6px;
  }
  .zabbix-dot { width: 10px; height: 10px; border-radius: 50%; }
  .zabbix-dot.ok { background: #22C55E; }
  .zabbix-muted { color: var(--text-muted); font-size: 0.8125rem; margin: 0; }

  .zabbix-ok { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; }
  .zabbix-ok-icon { color: #22C55E; font-size: 1.25rem; font-weight: 700; }
  .zabbix-ok span { color: var(--text-heading); font-size: 0.875rem; font-weight: 500; }

  .zabbix-problems { display: flex; flex-direction: column; gap: 0.375rem; margin-bottom: 0.75rem; max-height: 120px; overflow-y: auto; }
  .zabbix-problem { display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem; }
  .zabbix-sev { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .zabbix-problem-host { font-weight: 600; color: var(--text-heading); white-space: nowrap; }
  .zabbix-problem-name { color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .zabbix-stats { font-size: 0.75rem; color: var(--text-muted); display: flex; align-items: center; gap: 0.375rem; }
  .zabbix-dot-inline { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
  .zabbix-dot-inline.ok { background: #22C55E; }
  .sep { opacity: 0.4; }
</style>
