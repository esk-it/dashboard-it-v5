<script>
  import { onMount } from 'svelte';
  import { api } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';
  import { RefreshCw, Search, Settings as SettingsIcon, Laptop, User, AlertCircle, ExternalLink, X, Pencil, Edit3 } from 'lucide-svelte';

  // ── Tab state ─────────────────────────────────────────────
  let activeTab = 'chromebooks'; // 'chromebooks' | 'teachers'

  // ── Data ──────────────────────────────────────────────────
  let chromebooks = [];
  let teachers = [];
  let stats = { total: 0, by_status_local: {}, orphans: 0, teachers_no_device: 0, last_sync: '' };
  let cbModels = [];
  let cbSettings = { device_ou_path: '', user_ou_path: '', include_device_descendants: false, google_connected: false };
  let loading = true;
  let syncing = false;
  let lastSyncResult = null;

  // ── Selection / panels ────────────────────────────────────
  let selectedCb = null;
  let selectedCbHistory = [];
  let selectedTeacher = null;
  let selectedTeacherDevices = [];
  let selectedTeacherHistory = [];

  // ── Filters: chromebooks ──────────────────────────────────
  let cbSearch = '';
  let cbSearchDebounced = '';
  let filterStatus = '';
  let filterModel = '';
  let filterBinding = '';
  let filterHasTeacher = '';
  let cbSort = 'model';

  // ── Filters: teachers ─────────────────────────────────────
  let tSearch = '';
  let tSearchDebounced = '';
  let tStatus = '';
  let tHasDevice = '';
  let tSort = 'name';

  // ── Dialogs ───────────────────────────────────────────────
  let showSettingsDialog = false;
  let editingCbForm = null;       // null or { id, status_local, notes_local, ... }
  let editingTeacherForm = null;  // null or { id, status_local, ... }
  let manualBindForm = null;      // null or { cb, query, results }

  // ── Status maps ───────────────────────────────────────────
  const CB_STATUS = {
    en_service: { label: 'En service', color: '#22C55E' },
    a_rendre:   { label: 'À rendre',   color: '#F59E0B' },
    rendu:      { label: 'Rendu',      color: '#3B82F6' },
    panne:      { label: 'En panne',   color: '#EF4444' },
    a_effacer:  { label: 'À effacer',  color: '#A855F7' },
    stock:      { label: 'En stock',   color: '#64748B' },
  };
  const TEACHER_STATUS = {
    present:  { label: 'Présent',  color: '#22C55E' },
    partant:  { label: 'Partant',  color: '#F59E0B' },
    arrivant: { label: 'Arrivant', color: '#3B82F6' },
    parti:    { label: 'Parti',    color: '#64748B' },
  };
  const BINDING_LABELS = {
    annotated:   'Champ Admin Google',
    recent_user: 'Dernier utilisateur',
    manual:      'Manuel',
    none:        'Non identifié',
  };

  // ── Search debouncing ─────────────────────────────────────
  let cbSearchTimer = null;
  $: {
    clearTimeout(cbSearchTimer);
    const v = cbSearch;
    cbSearchTimer = setTimeout(() => cbSearchDebounced = v, 280);
  }
  let tSearchTimer = null;
  $: {
    clearTimeout(tSearchTimer);
    const v = tSearch;
    tSearchTimer = setTimeout(() => tSearchDebounced = v, 280);
  }

  // ── Reload triggers ───────────────────────────────────────
  $: if (activeTab === 'chromebooks') reloadChromebooks(cbSearchDebounced, filterStatus, filterModel, filterBinding, filterHasTeacher, cbSort);
  $: if (activeTab === 'teachers') reloadTeachers(tSearchDebounced, tStatus, tHasDevice, tSort);

  async function reloadChromebooks(...args) {
    const params = new URLSearchParams();
    if (cbSearchDebounced) params.set('search', cbSearchDebounced);
    if (filterStatus) params.set('status_local', filterStatus);
    if (filterModel) params.set('model', filterModel);
    if (filterBinding) params.set('binding_source', filterBinding);
    if (filterHasTeacher) params.set('has_teacher', filterHasTeacher);
    params.set('sort', cbSort);
    try {
      chromebooks = await api.get('/api/chromebooks?' + params.toString());
    } catch (e) {
      toastError('Erreur chargement Chromebooks : ' + e.message);
    }
  }
  async function reloadTeachers(...args) {
    const params = new URLSearchParams();
    if (tSearchDebounced) params.set('search', tSearchDebounced);
    if (tStatus) params.set('status_local', tStatus);
    if (tHasDevice) params.set('has_device', tHasDevice);
    params.set('sort', tSort);
    try {
      teachers = await api.get('/api/teachers?' + params.toString());
    } catch (e) {
      toastError('Erreur chargement profs : ' + e.message);
    }
  }
  async function reloadStats() {
    try {
      stats = await api.get('/api/chromebooks/stats');
    } catch (e) { /* silent */ }
  }
  async function reloadModels() {
    try { cbModels = await api.get('/api/chromebooks/models'); } catch (e) {}
  }
  async function reloadSettings() {
    try { cbSettings = await api.get('/api/chromebooks/settings'); } catch (e) {}
  }

  onMount(async () => {
    loading = true;
    await Promise.all([reloadSettings(), reloadStats(), reloadModels()]);
    await reloadChromebooks();
    loading = false;
  });

  // ── Sync ──────────────────────────────────────────────────
  async function runSync() {
    if (syncing) return;
    if (!cbSettings.google_connected) {
      toastError('Connecte d\'abord Google dans Paramètres → Google.');
      return;
    }
    syncing = true;
    lastSyncResult = null;
    try {
      const result = await api.post('/api/chromebooks/sync', {});
      lastSyncResult = result;
      const msg = `Sync OK — ${result.devices_total} chromebooks, ${result.teachers_total} profs (${result.duration_seconds}s)`;
      success(msg);
      await Promise.all([reloadStats(), reloadModels()]);
      if (activeTab === 'chromebooks') await reloadChromebooks();
      else await reloadTeachers();
      // If we had a panel open, refresh it
      if (selectedCb) await openChromebook(selectedCb.id);
      if (selectedTeacher) await openTeacher(selectedTeacher.id);
    } catch (e) {
      toastError('Erreur sync : ' + e.message);
    } finally {
      syncing = false;
    }
  }

  // ── Open detail ───────────────────────────────────────────
  async function openChromebook(id) {
    try {
      selectedCb = await api.get('/api/chromebooks/' + id);
      selectedTeacher = null;
      try {
        selectedCbHistory = await api.get('/api/chromebooks/' + id + '/history');
      } catch (e) { selectedCbHistory = []; }
    } catch (e) {
      toastError('Erreur chargement détail : ' + e.message);
    }
  }
  function closeCbPanel() { selectedCb = null; selectedCbHistory = []; }

  async function openTeacher(id) {
    try {
      selectedTeacher = await api.get('/api/teachers/' + id);
      selectedCb = null;
      try {
        selectedTeacherDevices = await api.get('/api/teachers/' + id + '/chromebooks');
      } catch (e) { selectedTeacherDevices = []; }
      try {
        selectedTeacherHistory = await api.get('/api/teachers/' + id + '/history');
      } catch (e) { selectedTeacherHistory = []; }
    } catch (e) {
      toastError('Erreur chargement détail : ' + e.message);
    }
  }
  function closeTeacherPanel() {
    selectedTeacher = null; selectedTeacherDevices = []; selectedTeacherHistory = [];
  }

  // ── Edit chromebook (status/notes/dates) ──────────────────
  function openCbEdit(cb) {
    editingCbForm = {
      id: cb.id,
      status_local: cb.status_local,
      service_start_date: cb.service_start_date || '',
      return_date: cb.return_date || '',
      notes_local: cb.notes_local || '',
    };
  }
  async function saveCbEdit() {
    if (!editingCbForm) return;
    try {
      await api.patch('/api/chromebooks/' + editingCbForm.id, {
        status_local: editingCbForm.status_local,
        service_start_date: editingCbForm.service_start_date || null,
        return_date: editingCbForm.return_date || null,
        notes_local: editingCbForm.notes_local,
      });
      success('Modifications enregistrées');
      editingCbForm = null;
      await Promise.all([reloadStats(), reloadChromebooks()]);
      if (selectedCb) await openChromebook(selectedCb.id);
    } catch (e) {
      toastError('Erreur sauvegarde : ' + e.message);
    }
  }

  // ── Edit teacher (status/dates/notes) ─────────────────────
  function openTeacherEdit(t) {
    editingTeacherForm = {
      id: t.id,
      status_local: t.status_local,
      arrival_date: t.arrival_date || '',
      departure_date: t.departure_date || '',
      notes: t.notes || '',
    };
  }
  async function saveTeacherEdit() {
    if (!editingTeacherForm) return;
    try {
      await api.patch('/api/teachers/' + editingTeacherForm.id, {
        status_local: editingTeacherForm.status_local,
        arrival_date: editingTeacherForm.arrival_date || null,
        departure_date: editingTeacherForm.departure_date || null,
        notes: editingTeacherForm.notes,
      });
      success('Prof mis à jour');
      editingTeacherForm = null;
      await reloadTeachers();
      if (selectedTeacher) await openTeacher(selectedTeacher.id);
    } catch (e) {
      toastError('Erreur sauvegarde : ' + e.message);
    }
  }

  // ── Manual rebind ────────────────────────────────────────
  function openManualBind(cb) {
    manualBindForm = { cb, query: '', results: [] };
  }
  async function searchTeachersForBind() {
    if (!manualBindForm) return;
    const q = (manualBindForm.query || '').trim();
    if (q.length < 2) { manualBindForm.results = []; return; }
    try {
      const params = new URLSearchParams({ search: q, sort: 'name' });
      const found = await api.get('/api/teachers?' + params.toString());
      manualBindForm.results = found.slice(0, 12);
    } catch (e) { manualBindForm.results = []; }
  }
  async function applyManualBind(teacherId) {
    if (!manualBindForm) return;
    try {
      await api.patch('/api/chromebooks/' + manualBindForm.cb.id, {
        assigned_teacher_id: teacherId,
      });
      success('Liaison appliquée');
      manualBindForm = null;
      await reloadChromebooks();
      if (selectedCb) await openChromebook(selectedCb.id);
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
  }
  async function clearManualBind(cb) {
    if (!confirm('Désassocier ce Chromebook du prof actuel ?')) return;
    try {
      await api.patch('/api/chromebooks/' + cb.id, { clear_assignment: true });
      success('Liaison supprimée');
      await reloadChromebooks();
      if (selectedCb) await openChromebook(selectedCb.id);
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
  }

  // ── Settings dialog ───────────────────────────────────────
  let settingsForm = { device_ou_path: '', user_ou_path: '', include_device_descendants: false };
  function openSettings() {
    settingsForm = {
      device_ou_path: cbSettings.device_ou_path || '',
      user_ou_path: cbSettings.user_ou_path || '',
      include_device_descendants: !!cbSettings.include_device_descendants,
    };
    showSettingsDialog = true;
  }
  async function saveSettings() {
    try {
      cbSettings = await api.put('/api/chromebooks/settings', settingsForm);
      success('Paramètres enregistrés');
      showSettingsDialog = false;
    } catch (e) {
      toastError('Erreur : ' + e.message);
    }
  }

  // ── Display helpers ───────────────────────────────────────
  function fmtDate(s) {
    if (!s) return '';
    try {
      const d = new Date(s);
      if (isNaN(d.getTime())) return s;
      return d.toLocaleDateString('fr-FR');
    } catch { return s; }
  }
  function fmtDateTime(s) {
    if (!s) return '';
    try {
      const d = new Date(s);
      if (isNaN(d.getTime())) return s;
      return d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
    } catch { return s; }
  }
  function teacherInitials(t) {
    const fn = (t.full_name || t.email || '?').trim();
    const parts = fn.split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return (fn[0] || '?').toUpperCase();
  }
  function supportSoon(s) {
    if (!s) return false;
    try {
      const d = new Date(s);
      const now = new Date();
      const diffDays = (d - now) / (1000 * 60 * 60 * 24);
      return diffDays < 180; // < 6 months
    } catch { return false; }
  }
</script>

<div class="page-root">
  <!-- ─── Topbar ────────────────────────────────────────── -->
  <div class="topbar">
    <div class="title">
      <span class="title-icon"><Laptop size={20} /></span>
      <h1>Chromebooks</h1>
      <span class="count-badge">{stats.total} appareils</span>
      {#if stats.orphans > 0}
        <span class="warn-badge" title="Chromebooks sans prof identifié">
          <AlertCircle size={12} /> {stats.orphans} orphelins
        </span>
      {/if}
    </div>
    <div class="actions">
      {#if stats.last_sync}
        <span class="last-sync">Dernière sync : {fmtDateTime(stats.last_sync)}</span>
      {:else}
        <span class="last-sync none">Jamais synchronisé</span>
      {/if}
      <button class="btn-secondary" on:click={openSettings} title="Paramètres OU">
        <SettingsIcon size={14} /> Paramètres
      </button>
      <button class="btn-primary" on:click={runSync} disabled={syncing}>
        <RefreshCw size={14} class={syncing ? 'spin' : ''} />
        {syncing ? 'Synchronisation…' : 'Synchroniser Google'}
      </button>
    </div>
  </div>

  <!-- ─── Tabs ──────────────────────────────────────────── -->
  <div class="tabs">
    <button class="tab" class:active={activeTab === 'chromebooks'} on:click={() => activeTab = 'chromebooks'}>
      <Laptop size={14} /> Chromebooks ({stats.total})
    </button>
    <button class="tab" class:active={activeTab === 'teachers'} on:click={() => { activeTab = 'teachers'; if (!teachers.length) reloadTeachers(); }}>
      <User size={14} /> Profs ({teachers.length})
    </button>
  </div>

  {#if !cbSettings.google_connected}
    <div class="banner-warn">
      <AlertCircle size={16} />
      <span>
        <strong>Google n'est pas connecté.</strong>
        Va dans <em>Paramètres → Google</em> pour autoriser l'accès. Les scopes
        Admin Directory ont été ajoutés en v7.2.0, donc tu devras re-valider les permissions.
      </span>
    </div>
  {/if}

  <!-- ═══ TAB: CHROMEBOOKS ═══════════════════════════════ -->
  {#if activeTab === 'chromebooks'}
  <div class="layout-3col">
    <!-- ── Sidebar filtres ── -->
    <aside class="filters-col">
      <div class="filter-group">
        <label>Recherche</label>
        <div class="search-wrap">
          <Search size={13} />
          <input bind:value={cbSearch} placeholder="Serial, modèle, prof…" />
        </div>
      </div>

      <div class="filter-group">
        <label>Statut local</label>
        <button class="filter-pill" class:active={!filterStatus} on:click={() => filterStatus = ''}>Tous</button>
        {#each Object.entries(CB_STATUS) as [key, def]}
          <button class="filter-pill" class:active={filterStatus === key} on:click={() => filterStatus = key}>
            <span class="dot" style="background:{def.color}"></span> {def.label}
          </button>
        {/each}
      </div>

      <div class="filter-group">
        <label>Modèle</label>
        <select bind:value={filterModel}>
          <option value="">Tous</option>
          {#each cbModels as m}
            <option value={m}>{m}</option>
          {/each}
        </select>
      </div>

      <div class="filter-group">
        <label>Liaison prof</label>
        <button class="filter-pill" class:active={!filterHasTeacher && !filterBinding} on:click={() => { filterHasTeacher = ''; filterBinding = ''; }}>Tous</button>
        <button class="filter-pill" class:active={filterHasTeacher === 'true'} on:click={() => { filterHasTeacher = 'true'; filterBinding = ''; }}>Avec prof</button>
        <button class="filter-pill" class:active={filterHasTeacher === 'false'} on:click={() => { filterHasTeacher = 'false'; filterBinding = ''; }}>Sans prof</button>
        <button class="filter-pill" class:active={filterBinding === 'none'} on:click={() => { filterBinding = 'none'; filterHasTeacher = ''; }}>Orphelins</button>
        <button class="filter-pill" class:active={filterBinding === 'manual'} on:click={() => { filterBinding = 'manual'; filterHasTeacher = ''; }}>Manuels</button>
      </div>

      <div class="filter-group">
        <label>Tri</label>
        <select bind:value={cbSort}>
          <option value="model">Modèle</option>
          <option value="serial">Numéro de série</option>
          <option value="recent_sync">Dernière sync</option>
          <option value="last_enrollment">Date d'enrôlement</option>
        </select>
      </div>
    </aside>

    <!-- ── Cards list ── -->
    <section class="cards-col">
      {#if loading}
        <div class="empty">Chargement…</div>
      {:else if chromebooks.length === 0}
        <div class="empty">
          {#if !stats.total}
            Aucun Chromebook encore.<br>
            <button class="btn-primary mt8" on:click={runSync} disabled={syncing}>
              Synchroniser depuis Google
            </button>
          {:else}
            Aucun Chromebook ne correspond aux filtres.
          {/if}
        </div>
      {:else}
        <div class="cards-grid">
          {#each chromebooks as cb (cb.id)}
            {@const st = CB_STATUS[cb.status_local] || CB_STATUS.en_service}
            <article class="card" class:selected={selectedCb && selectedCb.id === cb.id} on:click={() => openChromebook(cb.id)}>
              <header class="card-h">
                <div class="card-icon"><Laptop size={18} /></div>
                <div class="card-titles">
                  <div class="card-title">{cb.model || '(modèle inconnu)'}</div>
                  <div class="card-sub">{cb.serial_number || cb.google_device_id}</div>
                </div>
                <span class="status-pill" style="border-color:{st.color}; color:{st.color}">
                  <span class="dot" style="background:{st.color}"></span>{st.label}
                </span>
              </header>
              <div class="card-body">
                {#if cb.assigned_teacher_id}
                  <div class="row">
                    <span class="row-label">Prof :</span>
                    <span class="row-value">{cb.teacher_full_name || cb.teacher_email}</span>
                  </div>
                {:else}
                  <div class="row muted">Aucun prof identifié</div>
                {/if}
                {#if cb.binding_source && cb.binding_source !== 'none'}
                  <div class="row small muted">
                    Liaison : {BINDING_LABELS[cb.binding_source] || cb.binding_source}
                  </div>
                {/if}
                {#if cb.support_end_date}
                  <div class="row small" class:warn-text={supportSoon(cb.support_end_date)}>
                    Support Google : {fmtDate(cb.support_end_date)}
                  </div>
                {/if}
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </section>

    <!-- ── Detail panel ── -->
    <aside class="detail-col">
      {#if selectedCb}
        {@const st = CB_STATUS[selectedCb.status_local] || CB_STATUS.en_service}
        <div class="panel">
          <header class="panel-h">
            <div class="panel-title">
              <Laptop size={18} />
              <div>
                <h2>{selectedCb.model || '(modèle inconnu)'}</h2>
                <div class="panel-sub">{selectedCb.serial_number || '(sans serial)'}</div>
              </div>
            </div>
            <button class="icon-btn" on:click={closeCbPanel} title="Fermer"><X size={16} /></button>
          </header>

          <!-- Specs Google (read-only) -->
          <section class="panel-section">
            <div class="section-title">Infos Google</div>
            <div class="kv-grid">
              <div><span class="k">Statut Google</span><span class="v">{selectedCb.google_status || '—'}</span></div>
              <div><span class="k">OU Google</span><span class="v">{selectedCb.org_unit_path || '—'}</span></div>
              <div><span class="k">Asset ID</span><span class="v">{selectedCb.annotated_asset_id || '—'}</span></div>
              <div><span class="k">Utilisateur attribué</span><span class="v">{selectedCb.annotated_user || '—'}</span></div>
              <div><span class="k">Dernier utilisateur</span><span class="v">{selectedCb.last_user_email || '—'}</span></div>
              <div><span class="k">Enrôlement</span><span class="v">{fmtDate(selectedCb.last_enrollment_time)}</span></div>
              <div><span class="k">Fin support OS</span>
                <span class="v" class:warn-text={supportSoon(selectedCb.support_end_date)}>
                  {fmtDate(selectedCb.support_end_date) || '—'}
                </span>
              </div>
              <div><span class="k">ID Google</span><span class="v mono">{selectedCb.google_device_id}</span></div>
            </div>
          </section>

          <!-- Statut local éditable -->
          <section class="panel-section">
            <div class="section-title-row">
              <div class="section-title">Statut local</div>
              <button class="link-btn" on:click={() => openCbEdit(selectedCb)}><Edit3 size={12}/> Modifier</button>
            </div>
            <div class="kv-grid">
              <div><span class="k">Statut</span>
                <span class="v">
                  <span class="status-pill inline" style="border-color:{st.color}; color:{st.color}">
                    <span class="dot" style="background:{st.color}"></span>{st.label}
                  </span>
                </span>
              </div>
              <div><span class="k">Mise en service</span><span class="v">{fmtDate(selectedCb.service_start_date) || '—'}</span></div>
              <div><span class="k">Restitution</span><span class="v">{fmtDate(selectedCb.return_date) || '—'}</span></div>
            </div>
            {#if selectedCb.notes_local}
              <div class="notes-box">{selectedCb.notes_local}</div>
            {/if}
          </section>

          <!-- Affectation prof -->
          <section class="panel-section">
            <div class="section-title-row">
              <div class="section-title">Prof affecté</div>
              <div class="section-actions">
                <button class="link-btn" on:click={() => openManualBind(selectedCb)}><Pencil size={12}/> Modifier</button>
                {#if selectedCb.assigned_teacher_id}
                  <button class="link-btn danger" on:click={() => clearManualBind(selectedCb)}>Désassocier</button>
                {/if}
              </div>
            </div>
            {#if selectedCb.assigned_teacher_id}
              <div class="teacher-mini" on:click={() => openTeacher(selectedCb.assigned_teacher_id)}>
                <span class="teacher-avatar">{teacherInitials({ full_name: selectedCb.teacher_full_name, email: selectedCb.teacher_email })}</span>
                <div class="teacher-info">
                  <div class="teacher-name">{selectedCb.teacher_full_name || selectedCb.teacher_email}</div>
                  <div class="teacher-email">{selectedCb.teacher_email}</div>
                </div>
                <span class="binding-badge">{BINDING_LABELS[selectedCb.binding_source] || selectedCb.binding_source}</span>
              </div>
            {:else}
              <div class="muted small">Aucun prof identifié. Aucun « utilisateur attribué » ni « dernier utilisateur » n'a pu être relié à un compte profs synchronisé.</div>
            {/if}
          </section>

          <!-- Historique -->
          {#if selectedCbHistory.length}
            <section class="panel-section">
              <div class="section-title">Historique d'affectations ({selectedCbHistory.length})</div>
              <div class="history-list">
                {#each selectedCbHistory as h}
                  <div class="history-row">
                    <div class="history-main">
                      <span class="history-name">{h.teacher_name || h.teacher_email || '(prof supprimé)'}</span>
                      <span class="history-dates">
                        {fmtDate(h.assigned_at)}{h.returned_at ? ' → ' + fmtDate(h.returned_at) : ' → présent'}
                      </span>
                    </div>
                    {#if h.notes}
                      <div class="history-note">{h.notes}</div>
                    {/if}
                  </div>
                {/each}
              </div>
            </section>
          {/if}
        </div>
      {:else}
        <div class="empty muted">
          <Laptop size={42} />
          <p>Sélectionne un Chromebook pour voir son détail.</p>
        </div>
      {/if}
    </aside>
  </div>
  {/if}

  <!-- ═══ TAB: TEACHERS ═══════════════════════════════════ -->
  {#if activeTab === 'teachers'}
  <div class="layout-3col">
    <!-- ── Sidebar filtres ── -->
    <aside class="filters-col">
      <div class="filter-group">
        <label>Recherche</label>
        <div class="search-wrap">
          <Search size={13} />
          <input bind:value={tSearch} placeholder="Nom ou email…" />
        </div>
      </div>

      <div class="filter-group">
        <label>Statut</label>
        <button class="filter-pill" class:active={!tStatus} on:click={() => tStatus = ''}>Tous</button>
        {#each Object.entries(TEACHER_STATUS) as [key, def]}
          <button class="filter-pill" class:active={tStatus === key} on:click={() => tStatus = key}>
            <span class="dot" style="background:{def.color}"></span> {def.label}
          </button>
        {/each}
      </div>

      <div class="filter-group">
        <label>Chromebook</label>
        <button class="filter-pill" class:active={!tHasDevice} on:click={() => tHasDevice = ''}>Tous</button>
        <button class="filter-pill" class:active={tHasDevice === 'true'} on:click={() => tHasDevice = 'true'}>Avec device</button>
        <button class="filter-pill" class:active={tHasDevice === 'false'} on:click={() => tHasDevice = 'false'}>Sans device</button>
      </div>

      <div class="filter-group">
        <label>Tri</label>
        <select bind:value={tSort}>
          <option value="name">Nom</option>
          <option value="status">Statut</option>
          <option value="recent_sync">Dernière sync</option>
        </select>
      </div>

      {#if stats.teachers_no_device > 0}
        <div class="info-block">
          <AlertCircle size={14} />
          <span>{stats.teachers_no_device} prof{stats.teachers_no_device > 1 ? 's' : ''} sans Chromebook</span>
        </div>
      {/if}
    </aside>

    <!-- ── Cards list ── -->
    <section class="cards-col">
      {#if teachers.length === 0}
        <div class="empty">
          {#if stats.last_sync}
            Aucun prof ne correspond aux filtres.
          {:else}
            Aucun prof encore.<br>
            <button class="btn-primary mt8" on:click={runSync} disabled={syncing}>
              Synchroniser depuis Google
            </button>
          {/if}
        </div>
      {:else}
        <div class="cards-grid">
          {#each teachers as t (t.id)}
            {@const ts = TEACHER_STATUS[t.status_local] || TEACHER_STATUS.present}
            <article class="card teacher-card" class:selected={selectedTeacher && selectedTeacher.id === t.id} on:click={() => openTeacher(t.id)}>
              <header class="card-h">
                <span class="teacher-avatar large">{teacherInitials(t)}</span>
                <div class="card-titles">
                  <div class="card-title">{t.full_name || t.email}</div>
                  <div class="card-sub">{t.email}</div>
                </div>
                <span class="status-pill" style="border-color:{ts.color}; color:{ts.color}">
                  <span class="dot" style="background:{ts.color}"></span>{ts.label}
                </span>
              </header>
              <div class="card-body">
                {#if t.chromebook_count > 0}
                  <div class="row">
                    <span class="row-label">{t.chromebook_count} Chromebook{t.chromebook_count > 1 ? 's' : ''} :</span>
                    <span class="row-value">{t.primary_chromebook_model || ''} — {t.primary_chromebook_serial || ''}</span>
                  </div>
                {:else}
                  <div class="row muted">Aucun Chromebook identifié</div>
                {/if}
                {#if t.is_suspended}
                  <div class="row small warn-text">Compte Google suspendu</div>
                {/if}
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </section>

    <!-- ── Detail panel ── -->
    <aside class="detail-col">
      {#if selectedTeacher}
        {@const ts = TEACHER_STATUS[selectedTeacher.status_local] || TEACHER_STATUS.present}
        <div class="panel">
          <header class="panel-h">
            <div class="panel-title">
              <span class="teacher-avatar large">{teacherInitials(selectedTeacher)}</span>
              <div>
                <h2>{selectedTeacher.full_name || selectedTeacher.email}</h2>
                <div class="panel-sub">{selectedTeacher.email}</div>
              </div>
            </div>
            <button class="icon-btn" on:click={closeTeacherPanel} title="Fermer"><X size={16} /></button>
          </header>

          <section class="panel-section">
            <div class="section-title">Infos Google</div>
            <div class="kv-grid">
              <div><span class="k">OU Google</span><span class="v">{selectedTeacher.google_ou_path || '—'}</span></div>
              <div><span class="k">Compte</span><span class="v">{selectedTeacher.is_suspended ? 'Suspendu' : 'Actif'}</span></div>
              <div><span class="k">ID Google</span><span class="v mono">{selectedTeacher.google_user_id || '—'}</span></div>
            </div>
          </section>

          <section class="panel-section">
            <div class="section-title-row">
              <div class="section-title">Statut local</div>
              <button class="link-btn" on:click={() => openTeacherEdit(selectedTeacher)}><Edit3 size={12}/> Modifier</button>
            </div>
            <div class="kv-grid">
              <div><span class="k">Statut</span>
                <span class="v">
                  <span class="status-pill inline" style="border-color:{ts.color}; color:{ts.color}">
                    <span class="dot" style="background:{ts.color}"></span>{ts.label}
                  </span>
                </span>
              </div>
              <div><span class="k">Arrivée</span><span class="v">{fmtDate(selectedTeacher.arrival_date) || '—'}</span></div>
              <div><span class="k">Départ</span><span class="v">{fmtDate(selectedTeacher.departure_date) || '—'}</span></div>
            </div>
            {#if selectedTeacher.notes}
              <div class="notes-box">{selectedTeacher.notes}</div>
            {/if}
          </section>

          <section class="panel-section">
            <div class="section-title">Chromebooks affectés ({selectedTeacherDevices.length})</div>
            {#if selectedTeacherDevices.length === 0}
              <div class="muted small">Aucun Chromebook actuellement identifié pour ce prof.</div>
            {:else}
              <div class="device-list">
                {#each selectedTeacherDevices as d}
                  {@const ds = CB_STATUS[d.status_local] || CB_STATUS.en_service}
                  <div class="device-row" on:click={() => { activeTab='chromebooks'; openChromebook(d.id); }}>
                    <Laptop size={14} />
                    <div class="device-info">
                      <div class="device-title">{d.model || '(modèle inconnu)'}</div>
                      <div class="device-serial">{d.serial_number}</div>
                    </div>
                    <span class="status-pill inline small" style="border-color:{ds.color}; color:{ds.color}">
                      <span class="dot" style="background:{ds.color}"></span>{ds.label}
                    </span>
                  </div>
                {/each}
              </div>
            {/if}
          </section>

          {#if selectedTeacherHistory.length}
            <section class="panel-section">
              <div class="section-title">Historique ({selectedTeacherHistory.length})</div>
              <div class="history-list">
                {#each selectedTeacherHistory as h}
                  <div class="history-row">
                    <div class="history-main">
                      <span class="history-name">{h.chromebook_model || ''} — {h.chromebook_serial || ''}</span>
                      <span class="history-dates">
                        {fmtDate(h.assigned_at)}{h.returned_at ? ' → ' + fmtDate(h.returned_at) : ' → présent'}
                      </span>
                    </div>
                    {#if h.notes}<div class="history-note">{h.notes}</div>{/if}
                  </div>
                {/each}
              </div>
            </section>
          {/if}
        </div>
      {:else}
        <div class="empty muted">
          <User size={42} />
          <p>Sélectionne un prof pour voir son détail.</p>
        </div>
      {/if}
    </aside>
  </div>
  {/if}

  <!-- ═══ Dialogs ═══════════════════════════════════════ -->

  {#if showSettingsDialog}
    <div class="dialog-overlay" on:click|self={() => showSettingsDialog = false}>
      <div class="dialog">
        <header class="dialog-h">
          <h3>Paramètres Chromebooks</h3>
          <button class="icon-btn" on:click={() => showSettingsDialog = false}><X size={16} /></button>
        </header>
        <div class="dialog-body">
          <p class="help">
            Chemins des unités organisationnelles Google Workspace à synchroniser.
            Le chemin commence toujours par <code>/</code>. Exemple :
            <code>/1. Chromebooks/1. Personnel éducatif</code>.
          </p>
          <label>
            <span>OU des Chromebooks (devices)</span>
            <input bind:value={settingsForm.device_ou_path} placeholder="/1. Chromebooks/1. Personnel éducatif" />
          </label>
          <label>
            <span>OU des Profs (utilisateurs Workspace)</span>
            <input bind:value={settingsForm.user_ou_path} placeholder="/1. Personnel éducatif" />
          </label>
          <label class="checkbox">
            <input type="checkbox" bind:checked={settingsForm.include_device_descendants} />
            <span>Inclure les sous-OU pour les Chromebooks (utile si les devices sont éclatés en sous-dossiers)</span>
          </label>
        </div>
        <footer class="dialog-f">
          <button class="btn-secondary" on:click={() => showSettingsDialog = false}>Annuler</button>
          <button class="btn-primary" on:click={saveSettings}>Enregistrer</button>
        </footer>
      </div>
    </div>
  {/if}

  {#if editingCbForm}
    <div class="dialog-overlay" on:click|self={() => editingCbForm = null}>
      <div class="dialog">
        <header class="dialog-h">
          <h3>Modifier le Chromebook</h3>
          <button class="icon-btn" on:click={() => editingCbForm = null}><X size={16} /></button>
        </header>
        <div class="dialog-body">
          <label>
            <span>Statut local</span>
            <select bind:value={editingCbForm.status_local}>
              {#each Object.entries(CB_STATUS) as [key, def]}
                <option value={key}>{def.label}</option>
              {/each}
            </select>
          </label>
          <div class="row-2">
            <label>
              <span>Mise en service</span>
              <input type="date" bind:value={editingCbForm.service_start_date} />
            </label>
            <label>
              <span>Date de restitution</span>
              <input type="date" bind:value={editingCbForm.return_date} />
            </label>
          </div>
          <label>
            <span>Notes</span>
            <textarea bind:value={editingCbForm.notes_local} rows="4" placeholder="Ex. « clavier qwerty », « chargeur perdu »…"></textarea>
          </label>
        </div>
        <footer class="dialog-f">
          <button class="btn-secondary" on:click={() => editingCbForm = null}>Annuler</button>
          <button class="btn-primary" on:click={saveCbEdit}>Enregistrer</button>
        </footer>
      </div>
    </div>
  {/if}

  {#if editingTeacherForm}
    <div class="dialog-overlay" on:click|self={() => editingTeacherForm = null}>
      <div class="dialog">
        <header class="dialog-h">
          <h3>Modifier le prof</h3>
          <button class="icon-btn" on:click={() => editingTeacherForm = null}><X size={16} /></button>
        </header>
        <div class="dialog-body">
          <label>
            <span>Statut</span>
            <select bind:value={editingTeacherForm.status_local}>
              {#each Object.entries(TEACHER_STATUS) as [key, def]}
                <option value={key}>{def.label}</option>
              {/each}
            </select>
          </label>
          <div class="row-2">
            <label>
              <span>Arrivée</span>
              <input type="date" bind:value={editingTeacherForm.arrival_date} />
            </label>
            <label>
              <span>Départ</span>
              <input type="date" bind:value={editingTeacherForm.departure_date} />
            </label>
          </div>
          <label>
            <span>Notes</span>
            <textarea bind:value={editingTeacherForm.notes} rows="4"></textarea>
          </label>
        </div>
        <footer class="dialog-f">
          <button class="btn-secondary" on:click={() => editingTeacherForm = null}>Annuler</button>
          <button class="btn-primary" on:click={saveTeacherEdit}>Enregistrer</button>
        </footer>
      </div>
    </div>
  {/if}

  {#if manualBindForm}
    <div class="dialog-overlay" on:click|self={() => manualBindForm = null}>
      <div class="dialog">
        <header class="dialog-h">
          <h3>Associer ce Chromebook à un prof</h3>
          <button class="icon-btn" on:click={() => manualBindForm = null}><X size={16} /></button>
        </header>
        <div class="dialog-body">
          <p class="help">
            La liaison sera marquée « Manuelle » et ne sera plus modifiée
            automatiquement par la sync. Pour réactiver la détection auto,
            désassocie le Chromebook puis re-sync.
          </p>
          <label>
            <span>Rechercher un prof</span>
            <input bind:value={manualBindForm.query} on:input={searchTeachersForBind} placeholder="Nom ou email…" />
          </label>
          {#if manualBindForm.results && manualBindForm.results.length}
            <div class="bind-results">
              {#each manualBindForm.results as t}
                <button class="bind-row" on:click={() => applyManualBind(t.id)}>
                  <span class="teacher-avatar">{teacherInitials(t)}</span>
                  <div class="bind-info">
                    <div class="bind-name">{t.full_name || t.email}</div>
                    <div class="bind-email">{t.email}</div>
                  </div>
                  {#if t.chromebook_count > 0}
                    <span class="bind-already">Déjà {t.chromebook_count} device(s)</span>
                  {/if}
                </button>
              {/each}
            </div>
          {:else if manualBindForm.query && manualBindForm.query.length >= 2}
            <div class="muted small">Aucun prof trouvé.</div>
          {/if}
        </div>
        <footer class="dialog-f">
          <button class="btn-secondary" on:click={() => manualBindForm = null}>Fermer</button>
        </footer>
      </div>
    </div>
  {/if}
</div>

<style>
  .page-root { display: flex; flex-direction: column; gap: 14px; height: 100%; }

  /* Topbar */
  .topbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .title { display: flex; align-items: center; gap: 10px; }
  .title h1 { margin: 0; font-size: 22px; font-weight: 700; color: var(--text-heading); }
  .title-icon { color: var(--accent); display: flex; align-items: center; }
  .count-badge { font-size: 12px; padding: 3px 10px; border-radius: 999px; background: var(--bg-elev-2); color: var(--text-secondary); }
  .warn-badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 12px; padding: 3px 10px; border-radius: 999px;
    background: rgba(245, 158, 11, 0.15); color: #F59E0B; font-weight: 600;
  }
  .actions { display: flex; align-items: center; gap: 10px; }
  .last-sync { font-size: 12px; color: var(--text-secondary); }
  .last-sync.none { color: var(--text-muted); font-style: italic; }
  .btn-primary {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--accent); color: #fff; border: none;
    padding: 8px 14px; border-radius: 8px; font-weight: 600; cursor: pointer;
    font-size: 13px;
  }
  .btn-primary:hover:not(:disabled) { filter: brightness(1.1); }
  .btn-primary:disabled { opacity: 0.6; cursor: wait; }
  .btn-secondary {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--bg-elev-1); color: var(--text-primary);
    border: 1px solid var(--border-color);
    padding: 8px 12px; border-radius: 8px; font-weight: 500; cursor: pointer;
    font-size: 13px;
  }
  .btn-secondary:hover { background: var(--bg-elev-2); }
  :global(.spin) { animation: spin 1s linear infinite; }
  @keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }

  /* Tabs */
  .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color); }
  .tab {
    display: inline-flex; align-items: center; gap: 6px;
    background: transparent; color: var(--text-secondary);
    border: none; border-bottom: 2px solid transparent;
    padding: 8px 14px; font-size: 13px; font-weight: 600;
    cursor: pointer;
  }
  .tab:hover { color: var(--text-primary); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  /* Banner */
  .banner-warn {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 14px; border-radius: 8px;
    background: rgba(245, 158, 11, 0.12); color: var(--text-primary);
    border: 1px solid rgba(245, 158, 11, 0.4);
    font-size: 13px;
  }
  .banner-warn strong { color: #F59E0B; }
  .banner-warn em { font-style: italic; color: var(--accent); }

  /* 3-col layout */
  .layout-3col {
    display: grid;
    grid-template-columns: 220px 1fr 380px;
    gap: 14px;
    flex: 1; min-height: 0;
  }
  .filters-col, .cards-col, .detail-col {
    background: var(--bg-elev-1);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 14px;
    overflow-y: auto;
  }

  /* Filters */
  .filter-group { margin-bottom: 16px; }
  .filter-group label {
    display: block; font-size: 11px; text-transform: uppercase;
    color: var(--text-muted); font-weight: 700; letter-spacing: 0.5px;
    margin-bottom: 6px;
  }
  .filter-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--bg-elev-2); color: var(--text-secondary);
    border: 1px solid transparent; border-radius: 6px;
    padding: 5px 10px; font-size: 12px; cursor: pointer;
    margin: 2px 4px 2px 0;
  }
  .filter-pill:hover { background: var(--bg-elev-3); color: var(--text-primary); }
  .filter-pill.active { background: var(--accent); color: #fff; }
  .filter-group select {
    width: 100%; padding: 6px 8px; border-radius: 6px;
    background: var(--bg-elev-2); color: var(--text-primary);
    border: 1px solid var(--border-color); font-size: 13px;
  }
  .search-wrap {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 8px; border-radius: 6px;
    background: var(--bg-elev-2); border: 1px solid var(--border-color);
  }
  .search-wrap input {
    flex: 1; background: transparent; border: none;
    color: var(--text-primary); font-size: 13px; outline: none;
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

  .info-block {
    display: flex; align-items: center; gap: 6px;
    margin-top: 12px; padding: 8px 10px; border-radius: 6px;
    background: rgba(59, 130, 246, 0.12); color: var(--text-primary);
    font-size: 12px;
  }

  /* Cards */
  .cards-col { padding: 14px; }
  .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
  .card {
    background: var(--bg-elev-2); border: 1px solid var(--border-color);
    border-radius: 10px; padding: 12px; cursor: pointer;
    transition: border-color 0.15s, transform 0.15s;
  }
  .card:hover { border-color: var(--accent); }
  .card.selected { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .card-h { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
  .card-icon {
    width: 36px; height: 36px; border-radius: 8px;
    background: var(--bg-elev-3); color: var(--accent);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .card-titles { flex: 1; min-width: 0; }
  .card-title {
    font-weight: 600; color: var(--text-heading); font-size: 14px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .card-sub { font-size: 12px; color: var(--text-muted); }
  .status-pill {
    display: inline-flex; align-items: center; gap: 4px;
    border: 1px solid; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600;
    background: transparent;
  }
  .status-pill.inline { padding: 1px 6px; font-size: 10px; }
  .status-pill.small { font-size: 10px; padding: 1px 6px; }
  .card-body .row {
    display: flex; gap: 6px; font-size: 12px;
    color: var(--text-primary); margin-top: 4px;
  }
  .card-body .row.small { font-size: 11px; color: var(--text-secondary); }
  .card-body .row.muted { color: var(--text-muted); font-style: italic; }
  .row-label { color: var(--text-muted); }
  .row-value { color: var(--text-primary); font-weight: 500; }
  .warn-text { color: #F59E0B; font-weight: 600; }

  /* Teacher avatar */
  .teacher-avatar {
    width: 32px; height: 32px; border-radius: 50%;
    background: var(--accent); color: #fff;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 12px; flex-shrink: 0;
  }
  .teacher-avatar.large { width: 40px; height: 40px; font-size: 14px; }
  .teacher-card .card-icon { display: none; }

  /* Detail panel */
  .panel { display: flex; flex-direction: column; gap: 0; }
  .panel-h {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 10px; padding-bottom: 14px;
    border-bottom: 1px solid var(--border-color); margin-bottom: 14px;
  }
  .panel-title { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
  .panel-title h2 { margin: 0; font-size: 16px; font-weight: 700; color: var(--text-heading); }
  .panel-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .icon-btn {
    background: transparent; border: none; cursor: pointer;
    color: var(--text-muted); padding: 6px; border-radius: 6px;
  }
  .icon-btn:hover { background: var(--bg-elev-2); color: var(--text-primary); }
  .panel-section { padding: 12px 0; border-bottom: 1px solid var(--border-color); }
  .panel-section:last-child { border-bottom: none; }
  .section-title { font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700; letter-spacing: 0.5px; margin-bottom: 8px; }
  .section-title-row { display: flex; align-items: center; justify-content: space-between; }
  .section-actions { display: flex; gap: 8px; }
  .kv-grid { display: grid; grid-template-columns: 1fr; gap: 6px; font-size: 12px; }
  .kv-grid > div { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
  .k { color: var(--text-muted); }
  .v { color: var(--text-primary); text-align: right; word-break: break-all; }
  .v.mono { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; }
  .notes-box {
    margin-top: 10px; padding: 8px 10px; border-radius: 6px;
    background: var(--bg-elev-2); color: var(--text-primary);
    font-size: 12px; white-space: pre-wrap;
  }
  .link-btn {
    background: transparent; border: none; cursor: pointer;
    color: var(--accent); font-size: 11px; font-weight: 600;
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 4px;
  }
  .link-btn:hover { text-decoration: underline; }
  .link-btn.danger { color: #EF4444; }

  /* Teacher mini-card inside chromebook detail */
  .teacher-mini {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 10px; border-radius: 8px;
    background: var(--bg-elev-2); cursor: pointer;
    transition: background 0.15s;
  }
  .teacher-mini:hover { background: var(--bg-elev-3); }
  .teacher-info { flex: 1; min-width: 0; }
  .teacher-name { font-weight: 600; font-size: 13px; color: var(--text-heading); }
  .teacher-email { font-size: 11px; color: var(--text-muted); }
  .binding-badge {
    font-size: 10px; padding: 2px 8px; border-radius: 999px;
    background: var(--bg-elev-3); color: var(--text-secondary);
  }

  /* History */
  .history-list { display: flex; flex-direction: column; gap: 8px; }
  .history-row { padding: 8px 10px; background: var(--bg-elev-2); border-radius: 6px; font-size: 12px; }
  .history-main { display: flex; justify-content: space-between; gap: 8px; }
  .history-name { color: var(--text-heading); font-weight: 500; }
  .history-dates { color: var(--text-muted); font-size: 11px; }
  .history-note { color: var(--text-secondary); font-size: 11px; margin-top: 3px; font-style: italic; }

  /* Devices list (teacher panel) */
  .device-list { display: flex; flex-direction: column; gap: 6px; }
  .device-row {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px; background: var(--bg-elev-2); border-radius: 6px;
    cursor: pointer; font-size: 12px;
  }
  .device-row:hover { background: var(--bg-elev-3); }
  .device-info { flex: 1; min-width: 0; }
  .device-title { font-weight: 600; color: var(--text-heading); }
  .device-serial { font-size: 11px; color: var(--text-muted); }

  /* Empty states */
  .empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    min-height: 200px; gap: 8px;
    color: var(--text-muted); font-size: 13px;
  }
  .empty.muted { color: var(--text-muted); }
  .mt8 { margin-top: 8px; }

  .small { font-size: 11px; }
  .muted { color: var(--text-muted); }

  /* Dialogs */
  .dialog-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    z-index: 9999; display: flex; align-items: center; justify-content: center;
    padding: 20px;
  }
  .dialog {
    background: var(--bg-elev-1); border: 1px solid var(--border-color);
    border-radius: 12px; padding: 20px; max-width: 520px; width: 100%;
    max-height: 90vh; overflow-y: auto;
  }
  .dialog-h { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
  .dialog-h h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--text-heading); }
  .dialog-body { display: flex; flex-direction: column; gap: 12px; }
  .dialog-body .help { font-size: 12px; color: var(--text-secondary); line-height: 1.4; margin: 0; }
  .dialog-body code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; background: var(--bg-elev-2); padding: 1px 4px; border-radius: 3px; }
  .dialog-body label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary); }
  .dialog-body label.checkbox { flex-direction: row; align-items: center; gap: 8px; font-size: 12px; }
  .dialog-body label input[type="text"], .dialog-body label input:not([type]), .dialog-body label input[type="date"], .dialog-body label select, .dialog-body label textarea {
    padding: 8px 10px; border-radius: 6px;
    background: var(--bg-elev-2); color: var(--text-primary);
    border: 1px solid var(--border-color); font-size: 13px;
    font-family: inherit;
  }
  .dialog-body textarea { resize: vertical; }
  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .dialog-f { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-color); }

  /* Bind dialog */
  .bind-results { display: flex; flex-direction: column; gap: 4px; max-height: 280px; overflow-y: auto; }
  .bind-row {
    display: flex; align-items: center; gap: 10px;
    background: var(--bg-elev-2); border: 1px solid transparent; border-radius: 6px;
    padding: 8px 10px; cursor: pointer; text-align: left; width: 100%;
  }
  .bind-row:hover { background: var(--bg-elev-3); border-color: var(--accent); }
  .bind-info { flex: 1; min-width: 0; }
  .bind-name { font-weight: 600; font-size: 13px; color: var(--text-heading); }
  .bind-email { font-size: 11px; color: var(--text-muted); }
  .bind-already { font-size: 10px; padding: 2px 6px; border-radius: 999px; background: var(--bg-elev-3); color: var(--text-secondary); }
</style>
