<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';
  import { Doughnut, Bar } from 'svelte-chartjs';
  import { Chart, ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from 'chart.js';

  Chart.register(ArcElement, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

  // ── State ──────────────────────────────────────────────────
  let stats = { total_hosts: 0, available: 0, unavailable: 0, unknown: 0, active_problems: 0, synced_at: null };
  let hosts = [];
  let problems = [];
  let overview = { host_availability: {}, problems_by_severity: {}, groups: [] };
  let config = { configured: false, url: '', api_token: '', auth_mode: 'token', username: '' };
  let loading = true;
  let syncing = false;
  let searchQuery = '';

  // Config dialog
  let showConfigDialog = false;
  let configForm = { url: '', api_token: '', username: '', password: '' };
  let authMode = 'token';
  let savingConfig = false;

  // Host detail panel
  let selectedHost = null;
  let hostDetail = null;
  let loadingDetail = false;

  // Derived
  $: filteredHosts = hosts.filter(h => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (h.name || '').toLowerCase().includes(q) ||
           (h.host || '').toLowerCase().includes(q) ||
           (h.ip || '').toLowerCase().includes(q) ||
           (h.groups || []).some(g => g.toLowerCase().includes(q));
  });

  $: filteredProblems = problems.filter(p => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (p.host || '').toLowerCase().includes(q) ||
           (p.name || '').toLowerCase().includes(q) ||
           (p.severity || '').toLowerCase().includes(q);
  });

  // Chart data
  $: availChart = {
    labels: ['En ligne', 'Hors ligne', 'Inconnu'],
    datasets: [{
      data: [overview.host_availability?.available || 0, overview.host_availability?.unavailable || 0, overview.host_availability?.unknown || 0],
      backgroundColor: ['#22C55E', '#EF4444', '#94A3B8'],
      borderWidth: 0,
    }],
  };

  $: sevChart = {
    labels: Object.keys(overview.problems_by_severity || {}).filter(k => k !== 'non classe' && k !== 'information'),
    datasets: [{
      data: Object.entries(overview.problems_by_severity || {}).filter(([k]) => k !== 'non classe' && k !== 'information').map(([, v]) => v),
      backgroundColor: ['#FBBF24', '#EAB308', '#F97316', '#EF4444'],
      borderWidth: 0,
      borderRadius: 4,
    }],
  };

  const chartOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } };
  const barOptions = { ...chartOptions, scales: { y: { beginAtZero: true, ticks: { stepSize: 1, color: 'var(--text-muted)' }, grid: { color: 'rgba(128,128,128,0.1)' } }, x: { ticks: { color: 'var(--text-muted)' }, grid: { display: false } } } };

  // ── Load ───────────────────────────────────────────────────
  onMount(() => { loadAll(); });

  async function loadAll() {
    loading = true;
    try {
      const [cfg, st] = await Promise.all([
        api.get('/api/monitoring/config'),
        api.get('/api/monitoring/stats').catch(() => stats),
      ]);
      config = cfg;
      stats = st;
      if (cfg.configured) {
        const [h, p, ov] = await Promise.all([
          api.get('/api/monitoring/hosts'),
          api.get('/api/monitoring/problems'),
          api.get('/api/monitoring/overview').catch(() => overview),
        ]);
        hosts = h;
        problems = p;
        overview = ov;
      }
    } catch (e) {
      toastError('Erreur chargement monitoring : ' + e.message);
    }
    loading = false;
  }

  async function triggerSync() {
    syncing = true;
    try {
      const result = await api.post('/api/monitoring/sync');
      success(`Sync terminee — ${result.total_hosts} hotes, ${result.total_problems} problemes`);
      await loadAll();
    } catch (e) {
      toastError('Erreur sync : ' + e.message);
    }
    syncing = false;
  }

  // ── Host detail ────────────────────────────────────────────
  async function openHostDetail(host) {
    selectedHost = host;
    hostDetail = null;
    loadingDetail = true;
    try {
      hostDetail = await api.get(`/api/monitoring/hosts/${host.id}`);
    } catch (e) {
      toastError('Erreur detail hote : ' + e.message);
    }
    loadingDetail = false;
  }

  function closeHostDetail() {
    selectedHost = null;
    hostDetail = null;
  }

  // ── Config Dialog ──────────────────────────────────────────
  function openConfig() {
    configForm = { url: config.configured ? config.url : '', api_token: '', username: '', password: '' };
    authMode = config.auth_mode || 'token';
    if (config.configured && config.username) { configForm.username = config.username; authMode = 'login'; }
    showConfigDialog = true;
  }

  async function saveMonitoringConfig() {
    if (!configForm.url) { toastError('URL requise'); return; }
    if (authMode === 'token' && !configForm.api_token) { toastError('API Token requis'); return; }
    if (authMode === 'login' && (!configForm.username || !configForm.password)) { toastError('Login et mot de passe requis'); return; }
    savingConfig = true;
    try {
      await api.put('/api/monitoring/config', configForm);
      success('Configuration sauvegardee');
      showConfigDialog = false;
      await loadAll();
    } catch (e) { toastError('Erreur : ' + e.message); }
    savingConfig = false;
  }

  async function deleteMonitoringConfig() {
    try {
      await api.delete('/api/monitoring/config');
      success('Configuration supprimee');
      showConfigDialog = false;
      hosts = []; problems = []; overview = { host_availability: {}, problems_by_severity: {}, groups: [] };
      await loadAll();
    } catch (e) { toastError('Erreur : ' + e.message); }
  }

  // ── Helpers ────────────────────────────────────────────────
  function formatDate(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
    catch { return iso; }
  }

  function timeSince(iso) {
    if (!iso) return '';
    try {
      const diff = Date.now() - new Date(iso).getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 60) return `${mins}min`;
      const hours = Math.floor(mins / 60);
      if (hours < 24) return `${hours}h`;
      return `${Math.floor(hours / 24)}j`;
    } catch { return ''; }
  }

  function severityClass(sev) {
    const s = (sev || '').toLowerCase();
    if (s === 'catastrophe') return 'disaster';
    if (s.startsWith('elev') || s.startsWith('élev')) return 'high';
    if (s === 'moyen') return 'average';
    if (s === 'avertissement') return 'warning';
    if (s === 'information') return 'info';
    return 'default';
  }

  function availDot(a) {
    if (a === 'available') return '#22C55E';
    if (a === 'unavailable') return '#EF4444';
    return '#94A3B8';
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->

{#if !config.configured}
  <!-- ═══ Not configured ═══ -->
  <div class="ya-page-card">
    <div class="ya-page-card__body" style="padding:3rem;text-align:center">
      <span style="font-size:3rem;display:block;margin-bottom:1rem">📡</span>
      <h2 style="margin:0 0 0.5rem;font-size:1.125rem;color:var(--text-heading)">Zabbix non configure</h2>
      <p style="color:var(--text-secondary);font-size:0.8125rem;margin-bottom:1.25rem">Configurez votre serveur Zabbix pour superviser votre infrastructure.</p>
      <div class="setup-steps">
        <h3>Pour commencer :</h3>
        <ol>
          <li>Installez Zabbix sur votre serveur</li>
          <li>Creez un API token ou utilisez un compte login/password</li>
          <li>Cliquez sur <strong>Configurer</strong> ci-dessous</li>
        </ol>
      </div>
      <button class="ya-btn ya-btn--primary" on:click={openConfig}>Configurer</button>
    </div>
  </div>

{:else if loading}
  <div class="loading">Chargement...</div>

{:else}
  <!-- ═══ Section 1: KPIs ═══ -->
  <div class="ya-kpi-row" style="margin-bottom:1.25rem">
    <div class="ya-kpi ya-kpi--primary">
      <span class="ya-kpi__value">{stats.total_hosts}</span>
      <span class="ya-kpi__label">Hotes</span>
    </div>
    <div class="ya-kpi ya-kpi--success">
      <span class="ya-kpi__value">{stats.available}</span>
      <span class="ya-kpi__label">En ligne</span>
    </div>
    <div class="ya-kpi ya-kpi--danger">
      <span class="ya-kpi__value">{stats.unavailable}</span>
      <span class="ya-kpi__label">Hors ligne</span>
    </div>
    <div class="ya-kpi ya-kpi--warning">
      <span class="ya-kpi__value">{stats.active_problems}</span>
      <span class="ya-kpi__label">Problemes actifs</span>
    </div>
  </div>

  <!-- ═══ Toolbar ═══ -->
  <div class="mon-toolbar">
    <div class="mon-toolbar__left">
      <button class="ya-btn ya-btn--ghost" on:click={openConfig}>⚙️ Config</button>
      <button class="ya-btn ya-btn--primary" on:click={triggerSync} disabled={syncing}>
        {syncing ? '⏳ Sync...' : '🔄 Synchroniser'}
      </button>
      {#if stats.synced_at}
        <span class="sync-info">Derniere sync : {formatDate(stats.synced_at)}</span>
      {/if}
    </div>
    <div class="mon-toolbar__search">
      <input type="text" placeholder="Rechercher hote, IP, groupe..." bind:value={searchQuery} />
    </div>
  </div>

  <!-- ═══ Section 2: Charts ═══ -->
  <div class="mon-charts-row">
    <div class="mon-chart-card">
      <h4>Disponibilite des hotes</h4>
      <div class="mon-chart-wrap">
        <Doughnut data={availChart} options={{ ...chartOptions, cutout: '65%', plugins: { legend: { display: true, position: 'bottom', labels: { color: 'var(--text-muted)', padding: 12, font: { size: 11 } } } } }} />
      </div>
    </div>
    <div class="mon-chart-card">
      <h4>Problemes par severite</h4>
      <div class="mon-chart-wrap">
        {#if Object.values(overview.problems_by_severity || {}).some(v => v > 0)}
          <Bar data={sevChart} options={barOptions} />
        {:else}
          <div class="mon-chart-empty">
            <span style="font-size:2rem">✅</span>
            <p>Aucun probleme actif</p>
          </div>
        {/if}
      </div>
    </div>
  </div>

  <!-- ═══ Section 3: Active Problems ═══ -->
  {#if problems.length > 0}
    <div class="mon-section">
      <h3 class="mon-section__title">🚨 Problemes actifs ({problems.length})</h3>
      <div class="mon-problems-grid">
        {#each filteredProblems as problem}
          <div class="mon-problem-card">
            <div class="mon-problem-card__severity">
              <span class="severity-badge {severityClass(problem.severity)}">{problem.severity}</span>
            </div>
            <div class="mon-problem-card__content">
              <span class="mon-problem-card__host">{problem.host || '—'}</span>
              <span class="mon-problem-card__name">{problem.name}</span>
            </div>
            <div class="mon-problem-card__meta">
              <span class="mon-problem-card__time">{timeSince(problem.timestamp)}</span>
              {#if problem.acknowledged}<span class="mon-ack">✅</span>{/if}
            </div>
          </div>
        {/each}
      </div>
    </div>
  {:else}
    <div class="mon-section mon-no-problems">
      <span style="font-size:2.5rem">✅</span>
      <h3>Aucun probleme actif</h3>
      <p>Tous les hotes fonctionnent normalement</p>
    </div>
  {/if}

  <!-- ═══ Section 4: Hosts Table ═══ -->
  <div class="mon-section">
    <h3 class="mon-section__title">🖥️ Hotes ({filteredHosts.length})</h3>

    {#if selectedHost}
      <!-- Host detail panel -->
      <div class="mon-host-detail">
        <div class="mon-host-detail__header">
          <div class="mon-host-detail__info">
            <span class="mon-avail-dot" style="background:{availDot(selectedHost.available)}"></span>
            <h4>{selectedHost.name}</h4>
            <span class="mon-host-ip">{selectedHost.ip || '—'}</span>
            {#each (selectedHost.groups || []) as group}
              <span class="ya-badge ya-badge--primary">{group}</span>
            {/each}
          </div>
          <button class="ya-btn ya-btn--ghost" on:click={closeHostDetail}>✕ Fermer</button>
        </div>

        {#if loadingDetail}
          <div class="loading">Chargement du detail...</div>
        {:else if hostDetail}
          <!-- Host problems -->
          {#if hostDetail.problems?.length > 0}
            <div class="mon-host-detail__section">
              <h5>Problemes actifs ({hostDetail.problems.length})</h5>
              {#each hostDetail.problems as p}
                <div class="mon-host-detail__problem">
                  <span class="severity-badge {severityClass(p.severity)}">{p.severity}</span>
                  <span>{p.name}</span>
                </div>
              {/each}
            </div>
          {:else}
            <div class="mon-host-detail__section">
              <p style="color:var(--text-muted)">✅ Aucun probleme sur cet hote</p>
            </div>
          {/if}

          <!-- Host metrics/items -->
          {#if hostDetail.items?.length > 0}
            <div class="mon-host-detail__section">
              <h5>Metriques ({hostDetail.items.length})</h5>
              <div class="mon-items-grid">
                {#each hostDetail.items.slice(0, 20) as item}
                  <div class="mon-item">
                    <span class="mon-item__name">{item.name}</span>
                    <span class="mon-item__value">{item.value}{item.units ? ` ${item.units}` : ''}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        {/if}
      </div>
    {/if}

    <div class="ya-table-wrap">
      <table class="ya-table">
        <thead>
          <tr>
            <th style="width:40px">Etat</th>
            <th>Nom</th>
            <th>IP</th>
            <th>Groupes</th>
            <th>Statut</th>
            <th>Probleme</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredHosts as host}
            <tr class="mon-host-row" class:row-selected={selectedHost?.id === host.id} on:click={() => openHostDetail(host)}>
              <td><span class="mon-avail-dot" style="background:{availDot(host.available)}"></span></td>
              <td class="hostname">{host.name || host.host}</td>
              <td class="mono">{host.ip || '—'}</td>
              <td>
                {#each (host.groups || []).slice(0, 3) as group}
                  <span class="ya-badge ya-badge--primary" style="margin-right:0.25rem">{group}</span>
                {/each}
              </td>
              <td>
                {#if host.status === 'enabled'}
                  <span class="ya-badge ya-badge--success">Actif</span>
                {:else}
                  <span class="ya-badge ya-badge--secondary">Desactive</span>
                {/if}
              </td>
              <td class="problem-cell">{host.last_problem || '—'}</td>
              <td class="desc">{host.description || '—'}</td>
            </tr>
          {/each}
          {#if filteredHosts.length === 0}
            <tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:2rem">Aucun hote trouve</td></tr>
          {/if}
        </tbody>
      </table>
    </div>
  </div>

  <!-- ═══ Section 5: Groups ═══ -->
  {#if overview.groups?.length > 0}
    <div class="mon-section">
      <h3 class="mon-section__title">📂 Groupes</h3>
      <div class="mon-groups-grid">
        {#each overview.groups as group}
          <div class="mon-group-card">
            <span class="mon-group-card__count">{group.host_count}</span>
            <span class="mon-group-card__name">{group.name}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
{/if}

<!-- ═══ Config Dialog ═══ -->
{#if showConfigDialog}
<div class="ya-dialog-overlay" on:click|self={() => showConfigDialog = false}>
  <div class="ya-dialog" style="width:480px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Configuration Zabbix</h2>
      <button class="ya-dialog__close" on:click={() => showConfigDialog = false}>×</button>
    </div>
    <div class="ya-dialog__body">
      <p class="config-help">Entrez l'URL de votre serveur Zabbix et choisissez le mode d'authentification.</p>
      <label>URL du serveur <input type="text" bind:value={configForm.url} placeholder="https://zabbix.example.com" /></label>
      <div class="auth-mode-toggle">
        <button class="auth-mode-btn" class:active={authMode === 'token'} on:click={() => authMode = 'token'}>API Token</button>
        <button class="auth-mode-btn" class:active={authMode === 'login'} on:click={() => authMode = 'login'}>Login / Password</button>
      </div>
      {#if authMode === 'token'}
        <label>API Token <input type="password" bind:value={configForm.api_token} placeholder="votre-api-token" /></label>
      {:else}
        <label>Nom d'utilisateur <input type="text" bind:value={configForm.username} placeholder="Admin" /></label>
        <label>Mot de passe <input type="password" bind:value={configForm.password} placeholder="********" /></label>
      {/if}
    </div>
    <div class="ya-dialog__footer">
      {#if config.configured}
        <button class="ya-btn" style="background:#EF4444;color:#fff;border:none" on:click={deleteMonitoringConfig}>Supprimer</button>
      {/if}
      <div style="flex:1"></div>
      <button class="ya-btn ya-btn--ghost" on:click={() => showConfigDialog = false}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={saveMonitoringConfig} disabled={savingConfig}>
        {savingConfig ? 'Enregistrement...' : 'Enregistrer'}
      </button>
    </div>
  </div>
</div>
{/if}

<style>
  /* ── Toolbar ── */
  .mon-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
  .mon-toolbar__left { display: flex; align-items: center; gap: 0.5rem; }
  .mon-toolbar__search { position: relative; }
  .mon-toolbar__search input {
    padding: 0.5rem 0.75rem; background: var(--bg-card); border: 1px solid var(--border-card);
    border-radius: 0.5rem; color: var(--text-heading); font-size: 0.8125rem; width: 250px; font-family: inherit;
  }
  .mon-toolbar__search input:focus { outline: none; border-color: var(--accent); }
  .sync-info { font-size: 0.75rem; color: var(--text-muted); }

  /* ── Charts row ── */
  .mon-charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.25rem; }
  .mon-chart-card {
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.75rem; padding: 1.25rem;
  }
  .mon-chart-card h4 { margin: 0 0 1rem; font-size: 0.875rem; font-weight: 600; color: var(--text-heading); }
  .mon-chart-wrap { height: 200px; position: relative; }
  .mon-chart-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 0.5rem; color: var(--text-muted); }

  /* ── Sections ── */
  .mon-section { margin-bottom: 1.25rem; }
  .mon-section__title { font-size: 1rem; font-weight: 600; color: var(--text-heading); margin: 0 0 0.75rem; }

  /* ── Problems grid ── */
  .mon-problems-grid { display: flex; flex-direction: column; gap: 0.5rem; }
  .mon-problem-card {
    display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1rem;
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.625rem;
    transition: background 0.15s;
  }
  .mon-problem-card:hover { background: var(--bg-hover); }
  .mon-problem-card__content { flex: 1; min-width: 0; }
  .mon-problem-card__host { font-weight: 600; color: var(--text-heading); margin-right: 0.5rem; }
  .mon-problem-card__name { color: var(--text-secondary); font-size: 0.8125rem; }
  .mon-problem-card__meta { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
  .mon-problem-card__time { font-size: 0.75rem; color: var(--text-muted); }
  .mon-ack { font-size: 0.75rem; }

  .mon-no-problems {
    text-align: center; padding: 2rem; background: var(--bg-card);
    border: 1px solid var(--border-card); border-radius: 0.75rem;
  }
  .mon-no-problems h3 { margin: 0.5rem 0 0.25rem; color: var(--text-heading); font-size: 1rem; }
  .mon-no-problems p { margin: 0; color: var(--text-muted); font-size: 0.8125rem; }

  /* ── Host table ── */
  .mon-host-row { cursor: pointer; }
  .mon-avail-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
  .hostname { font-weight: 600; color: var(--text-heading); }
  .mono { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }
  .desc, .problem-cell { max-width: 12rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.75rem; color: var(--text-muted); }
  .loading { text-align: center; color: var(--text-muted); padding: 2.5rem; }

  /* ── Host detail panel ── */
  .mon-host-detail {
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.75rem;
    padding: 1.25rem; margin-bottom: 1rem;
  }
  .mon-host-detail__header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
  .mon-host-detail__info { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .mon-host-detail__info h4 { margin: 0; font-size: 1rem; font-weight: 700; color: var(--text-heading); }
  .mon-host-ip { font-family: 'JetBrains Mono', monospace; font-size: 0.8125rem; color: var(--text-muted); }
  .mon-host-detail__section { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-subtle); }
  .mon-host-detail__section h5 { margin: 0 0 0.5rem; font-size: 0.875rem; color: var(--text-heading); }
  .mon-host-detail__problem {
    display: flex; align-items: center; gap: 0.5rem; padding: 0.375rem 0; font-size: 0.8125rem;
  }

  /* ── Metrics grid ── */
  .mon-items-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.5rem; }
  .mon-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.5rem 0.75rem; background: var(--bg-base); border-radius: 0.375rem; font-size: 0.75rem;
  }
  .mon-item__name { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 60%; }
  .mon-item__value { font-weight: 600; color: var(--text-heading); font-family: 'JetBrains Mono', monospace; }

  /* ── Groups grid ── */
  .mon-groups-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 0.75rem; }
  .mon-group-card {
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.625rem;
    padding: 0.75rem 1rem; display: flex; flex-direction: column; gap: 0.125rem;
  }
  .mon-group-card__count { font-size: 1.25rem; font-weight: 700; color: var(--primary); }
  .mon-group-card__name { font-size: 0.75rem; color: var(--text-secondary); }

  /* ── Severity badges ── */
  .severity-badge {
    border-radius: 0.625rem; padding: 0.125rem 0.625rem; font-size: 0.6875rem; font-weight: 600;
    text-transform: capitalize; display: inline-block; white-space: nowrap;
  }
  .severity-badge.disaster { background: rgba(239,68,68,0.15); color: #EF4444; }
  .severity-badge.high { background: rgba(249,115,22,0.15); color: #F97316; }
  .severity-badge.average { background: rgba(234,179,8,0.15); color: #EAB308; }
  .severity-badge.warning { background: rgba(251,191,36,0.15); color: #FBBF24; }
  .severity-badge.info { background: rgba(88,186,215,0.15); color: #58bad7; }
  .severity-badge.default { background: rgba(148,163,184,0.15); color: #94A3B8; }

  /* ── Config dialog ── */
  .config-help { font-size: 0.8125rem; color: var(--text-secondary); margin: 0 0 1rem; }
  .auth-mode-toggle { display: flex; border: 1px solid var(--border-card); border-radius: 0.5rem; overflow: hidden; margin-bottom: 0.75rem; }
  .auth-mode-btn { flex: 1; padding: 0.5rem; background: none; border: none; color: var(--text-muted); font-size: 0.8125rem; font-weight: 600; cursor: pointer; font-family: inherit; }
  .auth-mode-btn.active { background: var(--accent); color: #fff; }
  label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8125rem; color: var(--text-secondary); margin-bottom: 0.75rem; }
  input { padding: 0.5rem 0.75rem; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.625rem; color: var(--text-heading); font-size: 0.8125rem; font-family: inherit; }
  input:focus { outline: none; border-color: var(--accent); }

  /* ── Setup steps ── */
  .setup-steps { text-align: left; background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.625rem; padding: 1rem 1.25rem; margin-bottom: 1.25rem; }
  .setup-steps h3 { margin: 0 0 0.5rem; color: var(--text-secondary); font-size: 0.8125rem; }
  .setup-steps ol { margin: 0; padding-left: 1.25rem; color: var(--text-secondary); font-size: 0.8125rem; line-height: 1.8; }

  @media (max-width: 768px) {
    .mon-charts-row { grid-template-columns: 1fr; }
    .mon-toolbar { flex-direction: column; align-items: stretch; }
  }
</style>
