<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';

  // ── State ──────────────────────────────────────────────────
  let stats = { total_hosts: 0, available: 0, unavailable: 0, unknown: 0, active_problems: 0, synced_at: null };
  let hosts = [];
  let problems = [];
  let config = { configured: false, url: '', api_token: '' };
  let loading = true;
  let syncing = false;
  let searchQuery = '';

  // Config dialog
  let showConfigDialog = false;
  let configForm = { url: '', api_token: '' };
  let savingConfig = false;

  // Tabs
  let activeTab = 'hosts';

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

  // ── Load ───────────────────────────────────────────────────
  onMount(() => { loadAll(); });

  async function loadAll() {
    loading = true;
    try {
      const [cfg, st] = await Promise.all([
        api.get('/api/monitoring/config'),
        api.get('/api/monitoring/stats'),
      ]);
      config = cfg;
      stats = st;
      if (cfg.configured) {
        const [h, p] = await Promise.all([
          api.get('/api/monitoring/hosts'),
          api.get('/api/monitoring/problems'),
        ]);
        hosts = h;
        problems = p;
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
      success(`Sync terminée — ${result.total_hosts} hôtes, ${result.total_problems} problèmes`);
      await loadAll();
    } catch (e) {
      toastError('Erreur sync : ' + e.message);
    }
    syncing = false;
  }

  // ── Config Dialog ──────────────────────────────────────────
  function openConfig() {
    configForm = {
      url: config.configured ? config.url : '',
      api_token: '',
    };
    showConfigDialog = true;
  }

  async function saveMonitoringConfig() {
    if (!configForm.url || !configForm.api_token) {
      toastError('Remplissez les deux champs');
      return;
    }
    savingConfig = true;
    try {
      await api.put('/api/monitoring/config', configForm);
      success('Configuration sauvegardée');
      showConfigDialog = false;
      await loadAll();
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
    savingConfig = false;
  }

  async function deleteMonitoringConfig() {
    try {
      await api.delete('/api/monitoring/config');
      success('Configuration supprimée');
      showConfigDialog = false;
      hosts = [];
      problems = [];
      await loadAll();
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
  }

  function formatDate(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('fr-FR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      });
    } catch { return iso; }
  }

  function severityClass(sev) {
    const s = (sev || '').toLowerCase();
    if (s === 'catastrophe') return 'disaster';
    if (s === 'élevé') return 'high';
    if (s === 'moyen') return 'average';
    if (s === 'avertissement') return 'warning';
    if (s === 'information') return 'info';
    return 'default';
  }
</script>

<!-- ── Header + KPIs ──────────────────────────────────────── -->
{#if config.configured}
  <div class="ya-kpi-row" style="margin-bottom:1rem">
    <div class="ya-kpi ya-kpi--primary">
      <span class="ya-kpi__value">{stats.total_hosts}</span>
      <span class="ya-kpi__label">Hôtes</span>
    </div>
    <div class="ya-kpi ya-kpi--success">
      <span class="ya-kpi__value">{stats.available}</span>
      <span class="ya-kpi__label">Disponibles</span>
    </div>
    <div class="ya-kpi ya-kpi--danger">
      <span class="ya-kpi__value">{stats.unavailable}</span>
      <span class="ya-kpi__label">Indisponibles</span>
    </div>
    <div class="ya-kpi ya-kpi--warning">
      <span class="ya-kpi__value">{stats.active_problems}</span>
      <span class="ya-kpi__label">Problèmes</span>
    </div>
  </div>
{/if}

<!-- ── Content ────────────────────────────────────────────── -->
{#if !config.configured}
  <div class="ya-page-card">
    <div class="ya-page-card__body" style="padding:3rem;text-align:center">
      <span style="font-size:3rem;display:block;margin-bottom:1rem">📡</span>
      <h2 style="margin:0 0 0.5rem;font-size:1rem;color:var(--text-heading)">Zabbix non configuré</h2>
      <p style="color:var(--text-secondary);font-size:0.8125rem;margin-bottom:1.25rem">Configurez votre serveur Zabbix pour superviser l'état de votre infrastructure réseau.</p>
      <div class="setup-steps">
        <h3>Pour commencer :</h3>
        <ol>
          <li>Installez Zabbix sur votre serveur</li>
          <li>Créez un API token dans <strong>Administration → API tokens</strong></li>
          <li>Cliquez sur <strong>Configurer</strong> ci-dessous et entrez l'URL + token</li>
        </ol>
      </div>
      <button class="ya-btn ya-btn--primary" on:click={openConfig}>Configurer</button>
    </div>
  </div>
{:else if loading}
  <div class="loading">Chargement…</div>
{:else}
  <div class="ya-page-card" style="margin-bottom:1rem">
    <div class="ya-page-card__body" style="padding:1rem 1.25rem">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.75rem">
        <div style="display:flex;align-items:center;gap:0.5rem">
          <div class="ya-tabs">
            <button class="ya-tab" class:ya-tab--active={activeTab === 'hosts'} on:click={() => activeTab = 'hosts'}>
              Hôtes <span class="ya-badge ya-badge--secondary" style="margin-left:0.25rem">{hosts.length}</span>
            </button>
            <button class="ya-tab" class:ya-tab--active={activeTab === 'problems'} on:click={() => activeTab = 'problems'}>
              Problèmes <span class="ya-badge" class:ya-badge--danger={problems.length > 0} class:ya-badge--secondary={problems.length === 0} style="margin-left:0.25rem">{problems.length}</span>
            </button>
          </div>
          <button class="ya-btn ya-btn--ghost" on:click={openConfig} title="Configuration">⚙️ Config</button>
          <button class="ya-btn ya-btn--primary" on:click={triggerSync} disabled={syncing || !config.configured}>
            {syncing ? '⏳ Sync en cours…' : '🔄 Synchroniser'}
          </button>
        </div>
        <div class="ya-toolbar__search">
          <span class="search-icon-inner">🔍</span>
          <input type="text" placeholder="Rechercher hôte, IP, groupe…" bind:value={searchQuery} />
        </div>
      </div>
      {#if stats.synced_at}
        <p class="sync-info">Dernière sync : {formatDate(stats.synced_at)}</p>
      {/if}
    </div>
  </div>

  {#if activeTab === 'hosts'}
    <div class="ya-table-wrap">
      <table class="ya-table">
        <thead>
          <tr>
            <th>Nom</th>
            <th>IP</th>
            <th>Groupes</th>
            <th>Statut</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredHosts as host}
            <tr>
              <td class="hostname">{host.name || host.host}</td>
              <td class="mono">{host.ip || '—'}</td>
              <td>
                {#each (host.groups || []) as group}
                  <span class="ya-badge ya-badge--primary" style="margin-right:0.25rem">{group}</span>
                {/each}
                {#if !(host.groups || []).length}—{/if}
              </td>
              <td>
                {#if host.status === 'enabled'}
                  <span class="ya-badge ya-badge--success">Actif</span>
                {:else}
                  <span class="ya-badge ya-badge--secondary">Désactivé</span>
                {/if}
              </td>
              <td class="desc">{host.description || '—'}</td>
            </tr>
          {/each}
          {#if filteredHosts.length === 0}
            <tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:2rem">Aucun hôte trouvé</td></tr>
          {/if}
        </tbody>
      </table>
    </div>

  {:else if activeTab === 'problems'}
    <div class="ya-table-wrap">
      <table class="ya-table">
        <thead>
          <tr>
            <th>Sévérité</th>
            <th>Hôte</th>
            <th>Problème</th>
            <th>Depuis</th>
            <th>Acquitté</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredProblems as problem}
            <tr>
              <td>
                <span class="severity-badge {severityClass(problem.severity)}">
                  {problem.severity}
                </span>
              </td>
              <td class="hostname">{problem.host || '—'}</td>
              <td>{problem.name || '—'}</td>
              <td>{formatDate(problem.timestamp)}</td>
              <td>{problem.acknowledged ? '✅' : '—'}</td>
            </tr>
          {/each}
          {#if filteredProblems.length === 0}
            <tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:2rem">Aucun problème actif</td></tr>
          {/if}
        </tbody>
      </table>
    </div>
  {/if}
{/if}

<!-- ── Config Dialog ──────────────────────────────────────── -->
{#if showConfigDialog}
<div class="ya-dialog-overlay" on:click|self={() => showConfigDialog = false}>
  <div class="ya-dialog" style="width:480px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Configuration Zabbix</h2>
      <button class="ya-dialog__close" on:click={() => showConfigDialog = false}>×</button>
    </div>
    <div class="ya-dialog__body">
      <p class="config-help">
        Entrez l'URL de votre serveur Zabbix et un API token.<br>
        <small>Le token se crée dans Zabbix → Administration → API tokens.</small>
      </p>
      <label>
        URL du serveur
        <input type="text" bind:value={configForm.url} placeholder="https://zabbix.example.com" />
      </label>
      <label>
        API Token
        <input type="password" bind:value={configForm.api_token}
               placeholder={config.configured ? 'Laisser vide pour ne pas changer' : 'votre-api-token'} />
      </label>
    </div>
    <div class="ya-dialog__footer">
      {#if config.configured}
        <button class="ya-btn" style="background:#EF4444;color:#fff;border:none" on:click={deleteMonitoringConfig}>Supprimer config</button>
      {/if}
      <div style="flex:1"></div>
      <button class="ya-btn ya-btn--ghost" on:click={() => showConfigDialog = false}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={saveMonitoringConfig} disabled={savingConfig}>
        {savingConfig ? 'Enregistrement…' : 'Enregistrer'}
      </button>
    </div>
  </div>
</div>
{/if}

<style>
  /* ── Sync info ─────────────────────────────────────────── */
  .sync-info { font-size: 0.75rem; color: var(--text-muted); margin: 0.5rem 0 0; }

  /* ── Empty state setup steps ────────────────────────────── */
  .setup-steps {
    text-align: left;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    padding: 1rem 1.25rem;
    margin-bottom: 1.25rem;
  }
  .setup-steps h3 { margin: 0 0 0.5rem; color: var(--text-secondary); font-size: 0.8125rem; }
  .setup-steps ol { margin: 0; padding-left: 1.25rem; color: var(--text-secondary); font-size: 0.8125rem; line-height: 1.8; }
  .setup-steps li strong { color: var(--text-heading); }

  /* ── Search icon ────────────────────────────────────────── */
  .search-icon-inner {
    position: absolute; left: 0.625rem; top: 50%; transform: translateY(-50%);
    font-size: 0.8125rem; pointer-events: none;
  }

  /* ── Table extras ──────────────────────────────────────── */
  .hostname { font-weight: 600; color: var(--text-heading); }
  .mono { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }
  .desc { max-width: 15rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .loading { text-align: center; color: var(--text-muted); padding: 2.5rem; font-size: 0.8125rem; }

  /* ── Severity badges ───────────────────────────────────── */
  .severity-badge {
    border-radius: 0.625rem; padding: 0.125rem 0.625rem; font-size: 0.75rem; font-weight: 600;
    text-transform: capitalize; display: inline-block;
  }
  .severity-badge.disaster { background: rgba(var(--danger-rgb), 0.15); color: var(--danger); }
  .severity-badge.high { background: rgba(249,115,22,0.15); color: #F97316; }
  .severity-badge.average { background: rgba(var(--warning-rgb), 0.15); color: var(--warning); }
  .severity-badge.warning { background: rgba(234,179,8,0.15); color: #EAB308; }
  .severity-badge.info { background: rgba(var(--info-rgb), 0.15); color: var(--info); }
  .severity-badge.default { background: rgba(var(--secondary-rgb), 0.15); color: var(--secondary); }

  /* ── Dialog form ───────────────────────────────────────── */
  .config-help { font-size: 0.8125rem; color: var(--text-secondary); margin: 0 0 1rem; }
  .config-help small { color: var(--text-muted); }

  label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8125rem; color: var(--text-secondary); margin-bottom: 0.75rem; }
  input {
    padding: 0.5rem 0.75rem; background: var(--bg-card);
    border: 1px solid var(--border-card); border-radius: 0.625rem;
    color: var(--text-heading); font-size: 0.8125rem;
  }
  input:focus { outline: none; border-color: var(--accent); }
</style>
