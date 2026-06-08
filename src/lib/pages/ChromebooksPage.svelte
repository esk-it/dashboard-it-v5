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
  let cbSettings = { device_ou_path: '', user_ou_path: '', include_device_descendants: false, include_user_descendants: true, google_connected: false };
  let loading = true;
  let syncing = false;
  let lastSyncResult = null;
  let showSyncResultDialog = false; // v7.2.1

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
  let filterSupportSoon = false; // v7.2.1
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
    asset_id:    'Email dans Asset ID',
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
  $: if (activeTab === 'chromebooks') reloadChromebooks(cbSearchDebounced, filterStatus, filterModel, filterBinding, filterHasTeacher, filterSupportSoon, cbSort);
  $: if (activeTab === 'teachers') reloadTeachers(tSearchDebounced, tStatus, tHasDevice, tSort);

  async function reloadChromebooks(...args) {
    const params = new URLSearchParams();
    if (cbSearchDebounced) params.set('search', cbSearchDebounced);
    if (filterStatus) params.set('status_local', filterStatus);
    if (filterModel) params.set('model', filterModel);
    if (filterBinding) params.set('binding_source', filterBinding);
    if (filterHasTeacher) params.set('has_teacher', filterHasTeacher);
    if (filterSupportSoon) params.set('support_ending_soon', 'true');
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
      // Open the result modal so the user can see the matching breakdown
      // (matched via annotated / recent user / orphans). v7.2.1.
      showSyncResultDialog = true;
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
  let settingsForm = { device_ou_path: '', user_ou_path: '', include_device_descendants: false, include_user_descendants: true };
  // v7.2.3 — OU explorer state. Populated lazily when user clicks "Parcourir les OU".
  let ouBrowser = { open: false, loading: false, ous: [], error: '' };

  async function loadGoogleOus() {
    ouBrowser = { open: true, loading: true, ous: [], error: '' };
    try {
      const list = await api.get('/api/chromebooks/google-ous');
      ouBrowser = { open: true, loading: false, ous: list, error: '' };
    } catch (e) {
      ouBrowser = { open: true, loading: false, ous: [], error: e.message || 'Erreur' };
    }
  }
  function pickOu(path) {
    settingsForm.user_ou_path = path;
    ouBrowser.open = false;
  }

  function openSettings() {
    settingsForm = {
      device_ou_path: cbSettings.device_ou_path || '',
      user_ou_path: cbSettings.user_ou_path || '',
      include_device_descendants: !!cbSettings.include_device_descendants,
      include_user_descendants: cbSettings.include_user_descendants !== false,
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
  // v7.2.1 — open this device in the Google Admin Chrome console.
  function googleAdminUrl(cb) {
    return 'https://admin.google.com/ac/chrome/devices/' + (cb.google_device_id || '');
  }
  function openInGoogleAdmin(cb) {
    if (!cb || !cb.google_device_id) return;
    window.open(googleAdminUrl(cb), '_blank');
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
        <label>Fin de support Google</label>
        <label class="check-row">
          <input type="checkbox" bind:checked={filterSupportSoon} />
          <span>Sous 6 mois (ou dépassée)</span>
        </label>
      </div>

      <div class="filter-group">
        <label>Tri</label>
        <select bind:value={cbSort}>
          <option value="model">Modèle</option>
          <option value="serial">Numéro de série</option>
          <option value="recent_sync">Dernière sync</option>
          <option value="last_enrollment">Date d'enrôlement</option>
          <option value="support_end">Fin de support (croissant)</option>
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
                <span class="status-pill" style="border-color:{st.color}; background:{st.color}26">
                  <span class="dot" style="background:{st.color}"></span>{st.label}
                </span>
              </header>
              <div class="card-body">
                {#if cb.assigned_teacher_id}
                  <div class="row">
                    <span class="row-label">Prof :</span>
                    <span class="row-value">{cb.teacher_full_name || cb.teacher_email}</span>
                  </div>
                {:else if cb.last_user_email}
                  <!-- v7.2.10 — user not in synced profs, surface the raw email. -->
                  <div class="row">
                    <span class="row-label">Utilisateur :</span>
                    <span class="row-value">{cb.last_user_email}</span>
                    <span class="badge-outside">Hors profs</span>
                  </div>
                {:else}
                  <div class="row muted">Jamais utilisé</div>
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
            <div class="panel-actions">
              <button class="icon-btn" on:click={() => openInGoogleAdmin(selectedCb)} title="Ouvrir dans Google Admin">
                <ExternalLink size={16} />
              </button>
              <button class="icon-btn" on:click={closeCbPanel} title="Fermer"><X size={16} /></button>
            </div>
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
                  <span class="status-pill inline" style="border-color:{st.color}; background:{st.color}26">
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
            {:else if selectedCb.last_user_email}
              <!-- v7.2.10 — Google connait l'utilisateur, mais il n'est pas
                   dans nos profs synchronises. On affiche l'info et on
                   laisse l'utilisateur decider. -->
              <div class="diag-box">
                <div class="diag-title">
                  <AlertCircle size={14} /> Pas dans les profs synchronisés
                </div>
                <div class="diag-lines">
                  <div class="diag-line">
                    <span class="diag-key">Utilisateur Google actuel :</span>
                    <span class="diag-val">{selectedCb.last_user_email}</span>
                  </div>
                  {#if selectedCb.annotated_asset_id && selectedCb.annotated_asset_id !== selectedCb.last_user_email}
                    <div class="diag-line">
                      <span class="diag-key">Asset ID (historique) :</span>
                      <span class="diag-val">{selectedCb.annotated_asset_id}</span>
                    </div>
                  {/if}
                </div>
                <div class="diag-hint">
                  Cet email n'est pas dans tes profs synchronisés. C'est peut-être
                  un AESH, du personnel admin, ou quelqu'un en dehors de l'OU
                  configurée. Si c'est bien un prof, utilise « Modifier »
                  ci-dessus pour l'associer manuellement.
                </div>
              </div>
            {:else}
              <!-- Chromebook jamais utilise (recentUsers vide cote Google). -->
              <div class="diag-box">
                <div class="diag-title">
                  <AlertCircle size={14} /> Jamais utilisé
                </div>
                <div class="diag-hint">
                  Aucun utilisateur n'a encore connecté sur ce Chromebook (recentUsers vide côté Google). Probablement un appareil neuf ou en stock.
                  {#if selectedCb.annotated_asset_id}
                    Asset ID indique : <strong>{selectedCb.annotated_asset_id}</strong>.
                  {/if}
                </div>
              </div>
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
          {#if stats.last_sync && (!tSearchDebounced && !tStatus && !tHasDevice)}
            <!-- Sync a deja eu lieu mais aucun prof : le chemin OU est sans doute faux. -->
            <AlertCircle size={28} />
            <p><strong>0 prof récupéré lors de la dernière sync.</strong></p>
            <p class="muted small">
              Le chemin OU des utilisateurs ne correspond probablement à rien
              côté Google. Le chemin actuel est :
              <code>{cbSettings.user_ou_path || '(non défini)'}</code>
            </p>
            <button class="btn-secondary mt8" on:click={openSettings}>
              <SettingsIcon size={13} /> Ajuster le chemin OU
            </button>
          {:else if stats.last_sync}
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
                <span class="status-pill" style="border-color:{ts.color}; background:{ts.color}26">
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
                  <span class="status-pill inline" style="border-color:{ts.color}; background:{ts.color}26">
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
                    <span class="status-pill inline small" style="border-color:{ds.color}; background:{ds.color}26">
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
            <span>
              OU des Profs (utilisateurs Workspace)
              <button class="link-btn" type="button" on:click={loadGoogleOus} style="margin-left:8px">
                Parcourir les OU Google
              </button>
            </span>
            <input bind:value={settingsForm.user_ou_path} placeholder="/1. Personnel éducatif" />
            <span class="hint-line">
              Astuce : si tu n'es pas sûr du chemin, mets <code>/</code> (avec « inclure les sous-OU » ci-dessous) — ça pullera tous les comptes Workspace et le matching par email se débrouillera.
            </span>
          </label>

          {#if ouBrowser.open}
            <div class="ou-browser">
              <div class="ou-browser-h">
                <strong>Sélectionne l'OU des profs</strong>
                <button class="icon-btn" type="button" on:click={() => ouBrowser.open = false}><X size={14} /></button>
              </div>
              {#if ouBrowser.loading}
                <div class="muted small">Chargement des OU Google…</div>
              {:else if ouBrowser.error}
                <div class="muted small warn-text">{ouBrowser.error}</div>
              {:else if ouBrowser.ous.length === 0}
                <div class="muted small">Aucune OU trouvée.</div>
              {:else}
                <div class="ou-list">
                  {#each ouBrowser.ous as o}
                    <button class="ou-row" type="button" on:click={() => pickOu(o.path)} class:current={o.path === settingsForm.user_ou_path}>
                      <div class="ou-main">
                        <span class="ou-path">{o.path}</span>
                        <span class="ou-count">{o.user_count} utilisateur{o.user_count > 1 ? 's' : ''}</span>
                      </div>
                      {#if o.samples && o.samples.length}
                        <div class="ou-samples">{o.samples.join(' · ')}</div>
                      {/if}
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
          <label class="checkbox">
            <input type="checkbox" bind:checked={settingsForm.include_device_descendants} />
            <span>Inclure les sous-OU pour les Chromebooks (utile si les devices sont éclatés en sous-dossiers)</span>
          </label>
          <label class="checkbox">
            <input type="checkbox" bind:checked={settingsForm.include_user_descendants} />
            <span>Inclure les sous-OU pour les Profs (utile si profs nested par établissement)</span>
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

  <!-- v7.2.1 — Sync result modal with diagnostic breakdown. -->
  {#if showSyncResultDialog && lastSyncResult}
    {@const r = lastSyncResult}
    {@const totalMatched = (r.matched_via_asset_id || 0) + (r.matched_via_annotated || 0) + (r.matched_via_recent_user || 0)}
    {@const pctMatched = r.devices_total > 0 ? Math.round(100 * totalMatched / r.devices_total) : 0}
    <div class="dialog-overlay" on:click|self={() => showSyncResultDialog = false}>
      <div class="dialog">
        <header class="dialog-h">
          <h3>Résultat de la synchronisation</h3>
          <button class="icon-btn" on:click={() => showSyncResultDialog = false}><X size={16} /></button>
        </header>
        <div class="dialog-body">
          <div class="sync-summary">
            <div class="sync-kpi">
              <div class="sync-kpi-v">{r.devices_total}</div>
              <div class="sync-kpi-k">Chromebooks</div>
              <div class="sync-kpi-sub">{r.devices_inserted} nouveaux · {r.devices_updated} maj</div>
            </div>
            <div class="sync-kpi">
              <div class="sync-kpi-v">{r.teachers_total + (r.teachers_discovered || 0)}</div>
              <div class="sync-kpi-k">Profs</div>
              <div class="sync-kpi-sub">
                {r.teachers_inserted} nouveaux · {r.teachers_updated} maj{#if r.teachers_discovered}
                  · {r.teachers_discovered} hors OU{/if}
              </div>
            </div>
            <div class="sync-kpi" class:warn={pctMatched < 80}>
              <div class="sync-kpi-v">{pctMatched}%</div>
              <div class="sync-kpi-k">Profs associés</div>
              <div class="sync-kpi-sub">{totalMatched} / {r.devices_total} chromebooks</div>
            </div>
          </div>

          <div class="sync-breakdown">
            <div class="bd-row">
              <span class="bd-label">Via dernier utilisateur (priorité 1)</span>
              <span class="bd-value">{r.matched_via_recent_user || 0} / {r.devices_with_recent_user || 0}</span>
            </div>
            <div class="bd-row">
              <span class="bd-label">Via email dans Asset ID (fallback)</span>
              <span class="bd-value">{r.matched_via_asset_id || 0} / {r.devices_with_asset_id_email || 0}</span>
            </div>
            <div class="bd-row">
              <span class="bd-label">Via « utilisateur attribué » (Admin Google)</span>
              <span class="bd-value">{r.matched_via_annotated || 0} / {r.devices_with_annotated || 0}</span>
            </div>
            <div class="bd-row">
              <span class="bd-label">Orphelins (aucun email exploitable)</span>
              <span class="bd-value warn-text">{r.devices_orphaned || 0}</span>
            </div>
            <div class="bd-row">
              <span class="bd-label">Re-bindés cette sync (changement de prof)</span>
              <span class="bd-value">{r.devices_rebound || 0}</span>
            </div>
            <div class="bd-row">
              <span class="bd-label">Durée</span>
              <span class="bd-value">{r.duration_seconds}s</span>
            </div>
          </div>

          {#if r.devices_total > 0 && r.teachers_total === 0}
            <div class="banner-warn">
              <AlertCircle size={14} />
              <span>
                <strong>0 prof synchronisé.</strong> Le chemin OU des utilisateurs
                est probablement incorrect. Vérifie dans <em>Paramètres Chromebooks</em>.
              </span>
            </div>
          {/if}

          {#if r.shared_annotated_skipped && r.shared_annotated_skipped.length > 0}
            <!-- v7.2.4 — comptes "partagés" detectes et ignores pour le binding. -->
            <div class="shared-skipped">
              <div class="orphan-title">Comptes génériques ignorés ({r.shared_annotated_skipped.length})</div>
              <p class="shared-explain">
                Ces emails apparaissaient en « utilisateur attribué » sur plusieurs
                Chromebooks — probablement des comptes admin/service, pas de
                vrais profs. Le binding utilise <code>dernier utilisateur</code> à la place.
              </p>
              {#each r.shared_annotated_skipped as s}
                <div class="shared-row">
                  <span class="shared-email">{s.email}</span>
                  <span class="shared-count">{s.device_count} chromebooks</span>
                </div>
              {/each}
            </div>
          {/if}

          {#if r.orphan_samples && r.orphan_samples.length > 0}
            <div class="orphan-samples">
              <div class="orphan-title">Exemples d'orphelins (max 20)</div>
              {#each r.orphan_samples as s}
                <div class="orphan-row">
                  <div class="orphan-device">{s.model || '(modèle inconnu)'} · {s.serial_number || '(sans serial)'}</div>
                  <div class="orphan-emails">
                    <span class="orphan-tag">asset ID :</span> <span>{s.annotated_asset_id || '—'}</span>
                  </div>
                  <div class="orphan-emails">
                    <span class="orphan-tag">attribué :</span> <span>{s.annotated_user || '—'}</span>
                  </div>
                  {#if s.recent_user_emails && s.recent_user_emails.length > 0}
                    <div class="orphan-emails">
                      <span class="orphan-tag">utilisateurs récents :</span>
                      <span>{s.recent_user_emails.join(' · ')}</span>
                    </div>
                  {:else}
                    <div class="orphan-emails">
                      <span class="orphan-tag">utilisateurs récents :</span>
                      <span>—</span>
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}

          {#if r.errors && r.errors.length}
            <div class="banner-warn">
              <AlertCircle size={14} />
              <span>
                Erreurs survenues pendant la sync :
                <ul>{#each r.errors as e}<li>{e}</li>{/each}</ul>
              </span>
            </div>
          {/if}
        </div>
        <footer class="dialog-f">
          <button class="btn-primary" on:click={() => showSyncResultDialog = false}>Fermer</button>
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
  .count-badge { font-size: 12px; padding: 3px 10px; border-radius: 999px; background: var(--bg-input); color: var(--text-secondary); }
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
    background: var(--bg-card); color: var(--text-primary);
    border: 1px solid var(--border-card);
    padding: 8px 12px; border-radius: 8px; font-weight: 500; cursor: pointer;
    font-size: 13px;
  }
  .btn-secondary:hover { background: var(--bg-input); }
  :global(.spin) { animation: spin 1s linear infinite; }
  @keyframes spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }

  /* Tabs */
  .tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-card); }
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
    background: var(--bg-card);
    border: 1px solid var(--border-card);
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
    background: var(--bg-input); color: var(--text-secondary);
    border: 1px solid transparent; border-radius: 6px;
    padding: 5px 10px; font-size: 12px; cursor: pointer;
    margin: 2px 4px 2px 0;
  }
  .filter-pill:hover { background: var(--bg-hover); color: var(--text-primary); }
  .filter-pill.active { background: var(--accent); color: #fff; }
  .filter-group select {
    width: 100%; padding: 6px 8px; border-radius: 6px;
    background: var(--bg-input); color: var(--text-primary);
    border: 1px solid var(--border-card); font-size: 13px;
  }
  .search-wrap {
    display: flex; align-items: center; gap: 8px;
    padding: 9px 12px; border-radius: 8px;
    background: var(--bg-input);
    border: 1px solid var(--border-card);
    color: var(--text-muted);
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .search-wrap:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(var(--accent-rgb), 0.18);
  }
  .search-wrap input {
    flex: 1; background: transparent; border: none;
    color: var(--text-primary); font-size: 13px; outline: none;
    padding: 0; min-width: 0;
  }
  .search-wrap input::placeholder { color: var(--text-muted); }
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
    background: var(--bg-input); border: 1px solid var(--border-card);
    border-radius: 10px; padding: 12px; cursor: pointer;
    transition: border-color 0.15s, transform 0.15s;
  }
  .card:hover { border-color: var(--accent); }
  .card.selected { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .card-h { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
  .card-icon {
    width: 36px; height: 36px; border-radius: 8px;
    background: var(--bg-hover); color: var(--accent);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .card-titles { flex: 1; min-width: 0; }
  .card-title {
    font-weight: 600; color: var(--text-heading); font-size: 14px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .card-sub { font-size: 12px; color: var(--text-muted); }
  /* v7.2.1 — pastille statut : fond teinté + texte qui suit le thème.
     L'ancienne version (background transparent + color: <hex>) devenait
     illisible en theme light selon le hex utilisé. La couleur est désormais
     conservée uniquement sur le fond, la bordure et le dot — le texte
     reste sur var(--text-heading) qui est toujours lisible. */
  .status-pill {
    display: inline-flex; align-items: center; gap: 4px;
    border: 1px solid; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600;
    color: var(--text-heading) !important;
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
  /* v7.2.10 — small badge for chromebook users not in synced profs */
  .badge-outside {
    font-size: 10px; padding: 1px 6px; border-radius: 999px;
    background: rgba(168, 85, 247, 0.15); color: #A855F7;
    font-weight: 600;
  }

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
    border-bottom: 1px solid var(--border-card); margin-bottom: 14px;
  }
  .panel-title { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
  .panel-title h2 { margin: 0; font-size: 16px; font-weight: 700; color: var(--text-heading); }
  .panel-sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  .icon-btn {
    background: transparent; border: none; cursor: pointer;
    color: var(--text-muted); padding: 6px; border-radius: 6px;
  }
  .icon-btn:hover { background: var(--bg-input); color: var(--text-primary); }
  .panel-section { padding: 12px 0; border-bottom: 1px solid var(--border-card); }
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
    background: var(--bg-input); color: var(--text-primary);
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
    background: var(--bg-input); cursor: pointer;
    transition: background 0.15s;
  }
  .teacher-mini:hover { background: var(--bg-hover); }
  .teacher-info { flex: 1; min-width: 0; }
  .teacher-name { font-weight: 600; font-size: 13px; color: var(--text-heading); }
  .teacher-email { font-size: 11px; color: var(--text-muted); }
  .binding-badge {
    font-size: 10px; padding: 2px 8px; border-radius: 999px;
    background: var(--bg-hover); color: var(--text-secondary);
  }

  /* History */
  .history-list { display: flex; flex-direction: column; gap: 8px; }
  .history-row { padding: 8px 10px; background: var(--bg-input); border-radius: 6px; font-size: 12px; }
  .history-main { display: flex; justify-content: space-between; gap: 8px; }
  .history-name { color: var(--text-heading); font-weight: 500; }
  .history-dates { color: var(--text-muted); font-size: 11px; }
  .history-note { color: var(--text-secondary); font-size: 11px; margin-top: 3px; font-style: italic; }

  /* Devices list (teacher panel) */
  .device-list { display: flex; flex-direction: column; gap: 6px; }
  .device-row {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px; background: var(--bg-input); border-radius: 6px;
    cursor: pointer; font-size: 12px;
  }
  .device-row:hover { background: var(--bg-hover); }
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

  /* Dialogs — v7.2.4 polish */
  .dialog-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.55);
    z-index: 9999; display: flex; align-items: center; justify-content: center;
    padding: 24px;
    backdrop-filter: blur(2px);
  }
  .dialog {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 14px;
    max-width: 560px; width: 100%;
    max-height: 88vh;
    /* Make the header + footer sticky by using a flex column with the body
       scrolling. Otherwise on a tall dialog the footer (Annuler/Enregistrer)
       slides off-screen. */
    display: flex; flex-direction: column;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.18);
    overflow: hidden;
  }
  .dialog-h {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    padding: 18px 22px; border-bottom: 1px solid var(--border-card);
    flex-shrink: 0;
  }
  .dialog-h h3 { margin: 0; font-size: 17px; font-weight: 700; color: var(--text-heading); }
  .dialog-body {
    display: flex; flex-direction: column; gap: 16px;
    padding: 20px 22px;
    overflow-y: auto;
    flex: 1; min-height: 0;
  }
  .dialog-body .help {
    font-size: 13px; color: var(--text-secondary);
    line-height: 1.5; margin: 0;
    padding: 12px 14px; border-radius: 8px;
    background: var(--bg-input);
    border-left: 3px solid var(--accent);
  }
  .dialog-body code {
    font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px;
    background: var(--bg-hover); padding: 2px 6px; border-radius: 4px;
    color: var(--text-heading);
  }
  .dialog-body label {
    display: flex; flex-direction: column; gap: 6px;
    font-size: 12px; font-weight: 600; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .dialog-body label.checkbox {
    flex-direction: row; align-items: center; gap: 10px;
    font-size: 13px; font-weight: 400; color: var(--text-primary);
    text-transform: none; letter-spacing: 0;
    cursor: pointer;
    padding: 8px 10px; border-radius: 6px;
    background: var(--bg-input);
  }
  .dialog-body label.checkbox input[type="checkbox"] { margin: 0; }
  .dialog-body label input[type="text"], .dialog-body label input:not([type]), .dialog-body label input[type="date"], .dialog-body label select, .dialog-body label textarea {
    padding: 10px 12px; border-radius: 8px;
    background: var(--bg-input); color: var(--text-primary);
    border: 1px solid var(--border-card); font-size: 13px;
    font-family: inherit; font-weight: 400;
    text-transform: none; letter-spacing: 0;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .dialog-body label input:focus, .dialog-body label select:focus, .dialog-body label textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(var(--accent-rgb), 0.15);
  }
  .dialog-body textarea { resize: vertical; min-height: 80px; }
  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .dialog-f {
    display: flex; justify-content: flex-end; gap: 10px;
    padding: 14px 22px; border-top: 1px solid var(--border-card);
    background: var(--bg-card);
    flex-shrink: 0;
  }

  /* v7.2.1 — checkbox row inside a filter group */
  .check-row {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: var(--text-primary);
    cursor: pointer; padding: 4px 0;
    text-transform: none; letter-spacing: 0; font-weight: 400;
  }
  .check-row input[type="checkbox"] { margin: 0; cursor: pointer; }

  /* Multiple buttons in panel header */
  .panel-actions { display: flex; gap: 4px; align-items: center; }

  /* v7.2.1 — diagnostic box (binding=none) */
  .diag-box {
    padding: 10px 12px; border-radius: 8px;
    background: rgba(245, 158, 11, 0.10);
    border: 1px solid rgba(245, 158, 11, 0.35);
    font-size: 12px; color: var(--text-primary);
  }
  .diag-title { display: flex; align-items: center; gap: 6px; font-weight: 700; color: #F59E0B; margin-bottom: 6px; }
  .diag-lines { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
  .diag-line { display: flex; gap: 6px; flex-wrap: wrap; align-items: baseline; }
  .diag-key { color: var(--text-muted); flex-shrink: 0; }
  .diag-val { color: var(--text-heading); font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; word-break: break-all; }
  .diag-val.muted { color: var(--text-muted); font-family: inherit; font-style: italic; }
  .diag-tag { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--bg-hover); color: var(--text-secondary); }
  .diag-hint { color: var(--text-secondary); font-size: 11px; line-height: 1.4; font-style: italic; }

  /* Sync result modal — v7.2.4 polish */
  .sync-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .sync-kpi {
    background: var(--bg-input);
    border: 1px solid var(--border-card);
    border-radius: 10px; padding: 14px 16px;
    display: flex; flex-direction: column; gap: 4px;
  }
  .sync-kpi.warn { border-color: rgba(245, 158, 11, 0.55); background: rgba(245, 158, 11, 0.10); }
  .sync-kpi-v { font-size: 26px; font-weight: 700; color: var(--text-heading); line-height: 1; }
  .sync-kpi-k { font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.6px; font-weight: 600; }
  .sync-kpi-sub { font-size: 11px; color: var(--text-secondary); }
  .sync-breakdown {
    display: flex; flex-direction: column; gap: 6px;
    padding: 12px 16px; background: var(--bg-input); border-radius: 10px;
    border: 1px solid var(--border-card);
  }
  .bd-row {
    display: flex; justify-content: space-between; gap: 8px;
    font-size: 13px; align-items: baseline;
    padding: 2px 0;
  }
  .bd-label { color: var(--text-secondary); }
  .bd-value { color: var(--text-heading); font-weight: 700; font-variant-numeric: tabular-nums; }

  /* v7.2.4 — shared annotated_user accounts ignored */
  .shared-skipped {
    padding: 12px 16px;
    background: rgba(168, 85, 247, 0.08);
    border: 1px solid rgba(168, 85, 247, 0.30);
    border-radius: 10px;
  }
  .shared-explain { font-size: 12px; color: var(--text-secondary); line-height: 1.45; margin: 4px 0 10px; }
  .shared-explain code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px; background: var(--bg-hover); padding: 1px 5px; border-radius: 3px; }
  .shared-row {
    display: flex; justify-content: space-between; gap: 8px;
    padding: 6px 0; font-size: 12px;
    border-top: 1px solid rgba(168, 85, 247, 0.15);
  }
  .shared-row:first-of-type { border-top: none; }
  .shared-email { color: var(--text-heading); font-family: ui-monospace, "SF Mono", Menlo, monospace; font-weight: 500; word-break: break-all; }
  .shared-count { color: var(--text-muted); font-variant-numeric: tabular-nums; flex-shrink: 0; }

  .orphan-samples { padding: 12px 16px; background: var(--bg-input); border: 1px solid var(--border-card); border-radius: 10px; }
  .orphan-title { font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700; letter-spacing: 0.5px; margin-bottom: 8px; }
  .orphan-row { padding: 6px 0; border-top: 1px solid var(--border-card); font-size: 11px; }
  .orphan-row:first-of-type { border-top: none; padding-top: 0; }
  .orphan-device { color: var(--text-heading); font-weight: 600; margin-bottom: 2px; }
  .orphan-emails { color: var(--text-secondary); display: flex; gap: 6px; flex-wrap: wrap; align-items: baseline; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .orphan-tag { color: var(--text-muted); font-family: inherit; }

  /* v7.2.3 — OU explorer inside settings dialog */
  .hint-line {
    font-size: 12px; color: var(--text-secondary);
    line-height: 1.45; margin-top: 6px; display: block;
    font-weight: 400; text-transform: none; letter-spacing: 0;
  }
  .hint-line code {
    font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px;
    background: var(--bg-hover); padding: 2px 6px; border-radius: 4px;
    color: var(--text-heading); font-weight: 600;
  }
  .ou-browser {
    margin-top: -4px;
    border: 1px solid var(--border-card); border-radius: 8px;
    background: var(--bg-input); padding: 10px 12px;
    max-height: 300px; overflow-y: auto;
  }
  .ou-browser-h { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 12px; }
  .ou-list { display: flex; flex-direction: column; gap: 4px; }
  .ou-row {
    background: var(--bg-card); border: 1px solid transparent;
    border-radius: 6px; padding: 8px 10px;
    cursor: pointer; text-align: left;
    display: flex; flex-direction: column; gap: 4px;
  }
  .ou-row:hover { border-color: var(--accent); }
  .ou-row.current { border-color: var(--accent); background: var(--bg-hover); }
  .ou-main { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
  .ou-path { color: var(--text-heading); font-weight: 600; font-size: 12px; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .ou-count { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .ou-samples { font-size: 10px; color: var(--text-secondary); font-family: ui-monospace, "SF Mono", Menlo, monospace; word-break: break-all; }

  /* Bind dialog */
  .bind-results { display: flex; flex-direction: column; gap: 4px; max-height: 280px; overflow-y: auto; }
  .bind-row {
    display: flex; align-items: center; gap: 10px;
    background: var(--bg-input); border: 1px solid transparent; border-radius: 6px;
    padding: 8px 10px; cursor: pointer; text-align: left; width: 100%;
  }
  .bind-row:hover { background: var(--bg-hover); border-color: var(--accent); }
  .bind-info { flex: 1; min-width: 0; }
  .bind-name { font-weight: 600; font-size: 13px; color: var(--text-heading); }
  .bind-email { font-size: 11px; color: var(--text-muted); }
  .bind-already { font-size: 10px; padding: 2px 6px; border-radius: 999px; background: var(--bg-hover); color: var(--text-secondary); }
</style>
