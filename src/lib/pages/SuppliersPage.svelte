<script>
  // v7.1.0 — Module Prestataires repensé comme un mini-CRM.
  // Avant : une liste passive (nom, contact, logo) avec un tab "Documents liés"
  // qui était au final juste un fragment de la vue à plat des documents.
  // Maintenant : un tableau de pilotage relationnel avec, pour chaque presta,
  // l'état de la relation, les KPIs financiers, la timeline d'activité, le
  // catalogue de services déduit des docs reçus, et des actions rapides.
  //
  // Tout le CRUD existant est conservé (create/edit/delete, contacts, logo,
  // gestion des domaines) — juste réorganisé visuellement et accessible
  // depuis le panel détail à droite.

  import { onMount } from 'svelte';
  import { api, API_BASE } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';
  import { currentPage } from '../stores/navigation.js';

  // ── State ────────────────────────────────────────────────
  let suppliers = [];
  let domains = [];
  let loading = true;

  // Filters
  let searchQuery = '';
  let searchTimer;
  let filterStatus = '';        // '' | 'actif_recent' | 'actif' | 'dormant' | 'inactif' | 'jamais_utilise'
  let filterDomain = '';
  let filterHasActiveDossier = false;

  // Detail panel
  let selectedSupplierId = null;
  let selectedSupplier = null;  // enriched response with timeline + services
  let detailLoading = false;

  // Supplier dialog (create + edit unified)
  let showSupplierDialog = false;
  let editingSupplierId = null;
  let form = defaultForm();
  let logoFile = null;
  let logoPreview = null;
  let fileInputEl;
  let saving = false;
  let confirmDeleteSupplier = null;
  let deleting = false;

  // Domain management dialog (separate workflow)
  let showDomainDialog = false;
  let domainEdits = [];
  let newDomain = { name: '', color_hex: '#64748B', icon_key: '', sort_order: 0 };

  // Logo error tracking — fall back to initials if a logo fails to load
  let logoErrors = {};

  // ── Constants ────────────────────────────────────────────
  const STATUS_LABELS = {
    actif_recent: { label: 'Actif récent',  short: 'Récent',  color: '#22C55E', hint: 'Dernier doc reçu il y a moins de 30 jours' },
    actif:        { label: 'Actif',         short: 'Actif',   color: '#10B981', hint: 'Doc reçu dans les 90 derniers jours' },
    dormant:      { label: 'Dormant',       short: 'Dormant', color: '#F59E0B', hint: 'Doc reçu entre 90 et 180 jours' },
    inactif:      { label: 'Inactif',       short: 'Inactif', color: '#6B7280', hint: 'Pas de doc reçu depuis plus de 6 mois' },
    jamais_utilise:{ label: 'Pas encore utilisé', short: 'Jamais', color: '#94A3B8', hint: 'Aucun doc lié à ce prestataire' },
  };

  const DOC_TYPE_LABELS = {
    DEVIS: 'Devis', PROPOSITION: 'Proposition', BPA: 'BPA', BON: 'Bon',
    CONTRAT: 'Contrat', FACTURE: 'Facture', RAPPORT: 'Rapport', AUTRE: 'Autre',
  };

  // ── Helpers ──────────────────────────────────────────────
  function defaultForm() {
    return {
      name: '', domain: '', phone: '', email: '', contact: '', notes: '',
      contacts: [],
    };
  }
  function newContactRow() {
    return { name: '', role: '', phone: '', email: '' };
  }
  function addContactRow() { form.contacts = [...form.contacts, newContactRow()]; }
  function removeContactRow(idx) { form.contacts = form.contacts.filter((_, i) => i !== idx); }

  function getInitials(name) {
    if (!name) return '??';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }

  function getDomainColor(domainName, fallback) {
    if (!domainName) return fallback || 'var(--text-muted)';
    const d = domains.find(d => d.name === domainName);
    return d?.color_hex || fallback || 'var(--text-muted)';
  }

  function logoUrl(s) {
    if (!s || !s.logo_path) return null;
    return `${API_BASE}/api/suppliers/${s.id}/logo`;
  }

  function fmtEur(n) {
    if (!n || isNaN(n)) return '0 €';
    return Math.round(n).toLocaleString('fr-FR') + ' €';
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return iso;
    return `${m[3]}/${m[2]}/${m[1]}`;
  }

  function fmtRelative(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const day = 86400000;
    if (diff < day) return "aujourd'hui";
    if (diff < 2 * day) return 'hier';
    if (diff < 7 * day) return `il y a ${Math.floor(diff / day)}j`;
    if (diff < 30 * day) return `il y a ${Math.floor(diff / day)}j`;
    return fmtDate(iso);
  }

  async function copyToClipboard(text, label = 'Copié') {
    try {
      await navigator.clipboard.writeText(text);
      success(`${label} : ${text}`);
    } catch {
      toastError('Copie impossible');
    }
  }

  function openMail(email) {
    if (!email) return;
    window.location.href = `mailto:${email}`;
  }

  // ── Data loading ─────────────────────────────────────────
  async function loadSuppliers() {
    loading = true;
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set('status_auto', filterStatus);
      if (filterDomain) params.set('domain', filterDomain);
      if (filterHasActiveDossier) params.set('has_active_dossier', 'true');
      if (searchQuery) params.set('search', searchQuery);
      const q = params.toString();
      suppliers = await api.get('/api/suppliers' + (q ? '?' + q : ''));
    } catch { suppliers = []; }
    loading = false;
  }

  async function loadDomains() {
    try { domains = await api.get('/api/suppliers/domains'); }
    catch { domains = []; }
  }

  onMount(async () => {
    await Promise.all([loadDomains(), loadSuppliers()]);
  });

  $: filterStatus, filterDomain, filterHasActiveDossier, loadSuppliers();

  function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadSuppliers, 280);
  }

  // ── Detail panel ────────────────────────────────────────
  async function selectSupplier(id) {
    selectedSupplierId = id;
    detailLoading = true;
    try {
      selectedSupplier = await api.get(`/api/suppliers/${id}`);
    } catch (e) {
      toastError('Impossible de charger la fiche');
      selectedSupplier = null;
    }
    detailLoading = false;
  }

  // ── Supplier CRUD ────────────────────────────────────────
  function openNew() {
    editingSupplierId = null;
    form = defaultForm();
    logoFile = null; logoPreview = null;
    showSupplierDialog = true;
  }

  function openEdit() {
    if (!selectedSupplier) return;
    editingSupplierId = selectedSupplier.id;
    form = {
      name: selectedSupplier.name || '',
      domain: selectedSupplier.domain || '',
      phone: selectedSupplier.phone || '',
      email: selectedSupplier.email || '',
      contact: selectedSupplier.contact || '',
      notes: selectedSupplier.notes || '',
      contacts: (selectedSupplier.contacts || []).map(c => ({...c})),
    };
    logoFile = null; logoPreview = null;
    showSupplierDialog = true;
  }

  async function saveSupplier() {
    if (!form.name.trim()) return;
    saving = true;
    try {
      let saved;
      if (editingSupplierId) {
        saved = await api.put(`/api/suppliers/${editingSupplierId}`, form);
      } else {
        saved = await api.post('/api/suppliers', form);
      }
      // Upload logo if a new one was picked
      if (logoFile && saved.id) {
        const fd = new FormData();
        fd.append('file', logoFile);
        try {
          await fetch(`${API_BASE}/api/suppliers/${saved.id}/logo`, { method: 'POST', body: fd });
        } catch { /* keep going — supplier saved, just logo failed */ }
      }
      showSupplierDialog = false;
      await loadSuppliers();
      // Re-load the detail panel if we edited the currently selected one
      if (editingSupplierId === selectedSupplierId) {
        await selectSupplier(selectedSupplierId);
      } else if (saved?.id) {
        await selectSupplier(saved.id);
      }
      success(editingSupplierId ? 'Prestataire modifié' : 'Prestataire créé');
    } catch (e) {
      toastError(`Erreur : ${e.message || e}`);
    } finally {
      saving = false;
    }
  }

  async function deleteSupplier() {
    if (!confirmDeleteSupplier) return;
    deleting = true;
    try {
      await api.delete(`/api/suppliers/${confirmDeleteSupplier.id}`);
      if (confirmDeleteSupplier.id === selectedSupplierId) {
        selectedSupplier = null;
        selectedSupplierId = null;
      }
      confirmDeleteSupplier = null;
      await loadSuppliers();
      success('Prestataire supprimé');
    } catch (e) {
      toastError(`Erreur : ${e.message || e}`);
    } finally {
      deleting = false;
    }
  }

  function onLogoChange(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    logoFile = f;
    const reader = new FileReader();
    reader.onload = () => logoPreview = reader.result;
    reader.readAsDataURL(f);
  }

  async function removeLogo() {
    if (!selectedSupplier) return;
    if (!confirm('Retirer le logo de ce prestataire ?')) return;
    try {
      // No dedicated DELETE endpoint — upload an empty file? Simpler: use the existing logo POST with no file.
      // Actually the suppliers backend exposes neither — we just set logo_path to '' via PUT.
      await api.put(`/api/suppliers/${selectedSupplier.id}`, { ...selectedSupplier, logo_path: '' });
      await selectSupplier(selectedSupplier.id);
      await loadSuppliers();
      success('Logo retiré');
    } catch (e) {
      toastError(`Erreur : ${e.message || e}`);
    }
  }

  // ── Domain management ──────────────────────────────────
  function openDomainManager() {
    domainEdits = domains.map(d => ({...d}));
    newDomain = { name: '', color_hex: '#64748B', icon_key: '', sort_order: 0 };
    showDomainDialog = true;
  }

  async function addDomain() {
    if (!newDomain.name.trim()) return;
    try {
      await api.post('/api/suppliers/domains', newDomain);
      await loadDomains();
      domainEdits = domains.map(d => ({...d}));
      newDomain = { name: '', color_hex: '#64748B', icon_key: '', sort_order: 0 };
      success('Domaine créé');
    } catch (e) { toastError(`Erreur : ${e.message || e}`); }
  }

  async function saveDomain(d) {
    try {
      await api.put(`/api/suppliers/domains/${d.id}`, d);
      await loadDomains();
      success('Domaine modifié');
    } catch (e) { toastError(`Erreur : ${e.message || e}`); }
  }

  async function deleteDomain(d) {
    if (!confirm(`Supprimer le domaine "${d.name}" ?\nLes prestataires qui y étaient assignés garderont leur valeur de domaine en texte libre.`)) return;
    try {
      await api.delete(`/api/suppliers/domains/${d.id}`);
      await loadDomains();
      domainEdits = domains.map(d => ({...d}));
    } catch (e) { toastError(`Erreur : ${e.message || e}`); }
  }

  // ── Quick actions from detail panel ─────────────────────
  function openDossiersForSupplier() {
    if (!selectedSupplier) return;
    try {
      sessionStorage.setItem('dossiers.filterSupplierId', String(selectedSupplier.id));
    } catch {}
    currentPage.set('/documents');
  }

  // ── Smart counts for the sidebar filter chips ──────────
  $: statusCounts = (() => {
    const c = { actif_recent: 0, actif: 0, dormant: 0, inactif: 0, jamais_utilise: 0 };
    for (const s of suppliers) {
      const k = s.status_auto || 'jamais_utilise';
      if (k in c) c[k]++;
    }
    return c;
  })();
</script>

<div class="suppliers-page">
  <!-- Top bar -->
  <header class="sp-topbar">
    <h1>Prestataires · <span class="sp-crumb">CRM</span></h1>
    <div class="sp-search">
      <span class="sp-search__icon">🔎</span>
      <input
        type="text"
        placeholder="Rechercher par nom, contact, email…"
        bind:value={searchQuery}
        on:input={onSearchInput}
      />
    </div>
    <div class="sp-spacer"></div>
    <button class="sp-btn-secondary" on:click={openDomainManager}>⚙ Domaines</button>
    <button class="sp-btn-primary" on:click={openNew}>+ Nouveau prestataire</button>
  </header>

  <div class="sp-layout">
    <!-- ── FILTERS sidebar ── -->
    <aside class="sp-filters">
      <div class="sp-filter-section">
        <h3>État de la relation</h3>
        <div class="sp-filter-item" class:active={filterStatus === ''} on:click={() => filterStatus = ''}>
          <span>Tous</span>
          <span class="sp-count">{suppliers.length}</span>
        </div>
        {#each Object.entries(STATUS_LABELS) as [key, info]}
          <div class="sp-filter-item" class:active={filterStatus === key} on:click={() => filterStatus = key} title={info.hint}>
            <span class="sp-filter-icon">
              <span class="sp-filter-dot" style="background:{info.color}"></span>
              {info.label}
            </span>
            <span class="sp-count">{statusCounts[key]}</span>
          </div>
        {/each}
      </div>

      <div class="sp-filter-section">
        <h3>Domaine</h3>
        <div class="sp-filter-item" class:active={filterDomain === ''} on:click={() => filterDomain = ''}>
          <span>Tous</span>
        </div>
        {#each domains as d}
          <div class="sp-filter-item" class:active={filterDomain === d.name} on:click={() => filterDomain = d.name}>
            <span class="sp-filter-icon">
              <span class="sp-filter-dot" style="background:{d.color_hex}"></span>
              {d.name}
            </span>
          </div>
        {/each}
      </div>

      <div class="sp-filter-section">
        <h3>Activité</h3>
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="sp-filter-item" class:active={filterHasActiveDossier} on:click={() => filterHasActiveDossier = !filterHasActiveDossier}>
          <span class="sp-filter-icon">📁 A des dossiers en cours</span>
          <span class="sp-toggle">{filterHasActiveDossier ? '✓' : ''}</span>
        </div>
      </div>
    </aside>

    <!-- ── SUPPLIERS LIST ── -->
    <main class="sp-list">
      <div class="sp-list-header">
        <h2>
          <strong>{suppliers.length}</strong>
          prestataire{suppliers.length > 1 ? 's' : ''}
        </h2>
      </div>

      {#if loading}
        <div class="sp-empty">Chargement…</div>
      {:else if suppliers.length === 0}
        <div class="sp-empty">
          {#if searchQuery || filterStatus || filterDomain || filterHasActiveDossier}
            Aucun prestataire ne correspond aux filtres.
          {:else}
            Aucun prestataire. Clique sur "+ Nouveau prestataire" pour commencer.
          {/if}
        </div>
      {:else}
        {#each suppliers as s (s.id)}
          {@const info = STATUS_LABELS[s.status_auto] || STATUS_LABELS.jamais_utilise}
          {@const url = logoUrl(s)}
          <article
            class="sp-card"
            class:selected={selectedSupplierId === s.id}
            on:click={() => selectSupplier(s.id)}
          >
            <div class="sp-card__top">
              {#if url && !logoErrors[s.id]}
                <img class="sp-avatar sp-avatar--img" src={url} alt={s.name} on:error={() => logoErrors[s.id] = true} />
              {:else}
                <div class="sp-avatar" style="background:{s.domain_color || getDomainColor(s.domain, '#6B7280')}">
                  {getInitials(s.name)}
                </div>
              {/if}
              <div class="sp-card__main">
                <div class="sp-card__title">{s.name}</div>
                <div class="sp-card__meta">
                  {#if s.domain}
                    <span class="sp-chip" style="background:{(s.domain_color || '#94A3B8') + '22'}; color:{s.domain_color || '#94A3B8'}">{s.domain}</span>
                  {/if}
                </div>
              </div>
              <span class="sp-status-pill" style="background:{info.color}22; color:{info.color}" title={info.hint}>
                {info.short}
              </span>
            </div>

            <div class="sp-kpis">
              <div class="sp-kpi">
                <span class="sp-kpi__label">Engagé YTD</span>
                <span class="sp-kpi__value">{fmtEur(s.engaged_ytd)}</span>
              </div>
              <div class="sp-kpi">
                <span class="sp-kpi__label">Dossiers actifs</span>
                <span class="sp-kpi__value">{s.active_dossiers_count} / {s.total_dossiers_count}</span>
              </div>
              <div class="sp-kpi">
                <span class="sp-kpi__label">Dernier contact</span>
                <span class="sp-kpi__value sp-kpi__value--sm">{s.last_interaction ? fmtDate(s.last_interaction) : '—'}</span>
              </div>
            </div>

            {#if s.phone || s.email}
              <div class="sp-card__footer">
                {#if s.phone}<span class="sp-mini">📞 {s.phone}</span>{/if}
                {#if s.email}<span class="sp-mini">✉️ {s.email}</span>{/if}
              </div>
            {/if}
          </article>
        {/each}
      {/if}
    </main>

    <!-- ── DETAIL PANEL ── -->
    <aside class="sp-detail">
      {#if !selectedSupplier}
        <div class="sp-detail__empty">
          <span class="sp-detail__empty-icon">📇</span>
          <p>Sélectionne un prestataire pour voir sa fiche complète.</p>
        </div>
      {:else}
        {@const info = STATUS_LABELS[selectedSupplier.status_auto] || STATUS_LABELS.jamais_utilise}
        {@const url = logoUrl(selectedSupplier)}

        <!-- Header -->
        <header class="sp-detail-header">
          <div class="sp-detail-header__top">
            <div class="sp-detail-id">
              {#if url && !logoErrors[selectedSupplier.id]}
                <img class="sp-avatar sp-avatar--lg sp-avatar--img" src={url} alt={selectedSupplier.name} on:error={() => logoErrors[selectedSupplier.id] = true} />
              {:else}
                <div class="sp-avatar sp-avatar--lg" style="background:{selectedSupplier.domain_color || getDomainColor(selectedSupplier.domain, '#6B7280')}">
                  {getInitials(selectedSupplier.name)}
                </div>
              {/if}
              <div>
                <h2>{selectedSupplier.name}</h2>
                <div class="sp-detail-meta">
                  {#if selectedSupplier.domain}
                    <span class="sp-chip" style="background:{(selectedSupplier.domain_color || '#94A3B8') + '22'}; color:{selectedSupplier.domain_color || '#94A3B8'}">{selectedSupplier.domain}</span>
                  {/if}
                  <span class="sp-chip" style="background:{info.color}22; color:{info.color}" title={info.hint}>
                    ● {info.label}
                  </span>
                </div>
              </div>
            </div>
            <div class="sp-detail-actions">
              <button class="sp-icon-btn" on:click={openEdit} title="Éditer">✏️</button>
              <button class="sp-icon-btn sp-icon-btn--danger" on:click={() => confirmDeleteSupplier = selectedSupplier} title="Supprimer">🗑</button>
            </div>
          </div>
        </header>

        <!-- KPI grid -->
        <section class="sp-detail-section">
          <div class="sp-kpi-grid">
            <div class="sp-kpi-card">
              <span class="sp-kpi-card__label">Engagé total</span>
              <span class="sp-kpi-card__value">{fmtEur(selectedSupplier.engaged_total)}</span>
            </div>
            <div class="sp-kpi-card">
              <span class="sp-kpi-card__label">Engagé {new Date().getFullYear()}</span>
              <span class="sp-kpi-card__value">{fmtEur(selectedSupplier.engaged_ytd)}</span>
            </div>
            <div class="sp-kpi-card">
              <span class="sp-kpi-card__label">Dossiers actifs</span>
              <span class="sp-kpi-card__value">{selectedSupplier.active_dossiers_count}</span>
              <span class="sp-kpi-card__sub">sur {selectedSupplier.total_dossiers_count} au total</span>
            </div>
            <div class="sp-kpi-card">
              <span class="sp-kpi-card__label">Dernière interaction</span>
              <span class="sp-kpi-card__value sp-kpi-card__value--sm">
                {selectedSupplier.last_interaction ? fmtDate(selectedSupplier.last_interaction) : '—'}
              </span>
              {#if selectedSupplier.last_interaction}
                <span class="sp-kpi-card__sub">{fmtRelative(selectedSupplier.last_interaction)}</span>
              {/if}
            </div>
          </div>
        </section>

        <!-- Quick actions -->
        <section class="sp-detail-section">
          <div class="sp-actions">
            <button class="sp-action" on:click={openDossiersForSupplier}>
              📁 Voir tous les dossiers
            </button>
            {#if selectedSupplier.email}
              <button class="sp-action" on:click={() => openMail(selectedSupplier.email)}>
                ✉️ Envoyer un mail
              </button>
            {/if}
            {#if selectedSupplier.phone}
              <button class="sp-action" on:click={() => copyToClipboard(selectedSupplier.phone, 'Téléphone')}>
                📞 Copier le téléphone
              </button>
            {/if}
          </div>
        </section>

        <!-- Contacts -->
        <section class="sp-detail-section">
          <div class="sp-section-header"><h3>Contacts</h3></div>
          {#if selectedSupplier.contact || selectedSupplier.phone || selectedSupplier.email}
            <div class="sp-contact-card">
              <div class="sp-contact-name">{selectedSupplier.contact || '(contact principal)'}</div>
              <div class="sp-contact-row">
                {#if selectedSupplier.phone}
                  <span class="sp-contact-bit">📞 {selectedSupplier.phone}</span>
                  <button class="sp-tiny-btn" on:click={() => copyToClipboard(selectedSupplier.phone, 'Téléphone')}>📋</button>
                {/if}
                {#if selectedSupplier.email}
                  <span class="sp-contact-bit">✉️ {selectedSupplier.email}</span>
                  <button class="sp-tiny-btn" on:click={() => copyToClipboard(selectedSupplier.email, 'Email')}>📋</button>
                  <button class="sp-tiny-btn" on:click={() => openMail(selectedSupplier.email)}>↗</button>
                {/if}
              </div>
            </div>
          {/if}
          {#each selectedSupplier.contacts || [] as c}
            <div class="sp-contact-card">
              <div class="sp-contact-name">
                {c.name || '(sans nom)'}
                {#if c.role}<span class="sp-contact-role">· {c.role}</span>{/if}
              </div>
              <div class="sp-contact-row">
                {#if c.phone}
                  <span class="sp-contact-bit">📞 {c.phone}</span>
                  <button class="sp-tiny-btn" on:click={() => copyToClipboard(c.phone, 'Téléphone')}>📋</button>
                {/if}
                {#if c.email}
                  <span class="sp-contact-bit">✉️ {c.email}</span>
                  <button class="sp-tiny-btn" on:click={() => copyToClipboard(c.email, 'Email')}>📋</button>
                  <button class="sp-tiny-btn" on:click={() => openMail(c.email)}>↗</button>
                {/if}
              </div>
            </div>
          {/each}
        </section>

        <!-- Services catalog -->
        {#if (selectedSupplier.services || []).length > 0}
          <section class="sp-detail-section">
            <div class="sp-section-header"><h3>Catalogue déduit</h3></div>
            <div class="sp-services">
              {#each selectedSupplier.services as svc}
                <span class="sp-service">
                  {DOC_TYPE_LABELS[svc.doc_type] || svc.doc_type}
                  <span class="sp-service__count">×{svc.count}</span>
                </span>
              {/each}
            </div>
          </section>
        {/if}

        <!-- Activity timeline -->
        <section class="sp-detail-section">
          <div class="sp-section-header"><h3>Activité récente</h3></div>
          {#if (selectedSupplier.timeline || []).length === 0}
            <p class="sp-section-empty">Aucune activité récente. Crée un dossier ou rattache un document pour faire vivre la fiche.</p>
          {:else}
            <div class="sp-timeline">
              {#each selectedSupplier.timeline as ev}
                <div class="sp-tl-item">
                  <div class="sp-tl-icon">{ev.icon || '•'}</div>
                  <div class="sp-tl-body">
                    <div class="sp-tl-text">{ev.body || ev.kind}</div>
                    <div class="sp-tl-meta">
                      {#if ev.dossier_title}<span class="sp-tl-dossier">📁 {ev.dossier_title}</span>{/if}
                      <span class="sp-tl-date">{fmtRelative(ev.created_at)}</span>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </section>

        {#if selectedSupplier.notes}
          <section class="sp-detail-section">
            <div class="sp-section-header"><h3>Notes</h3></div>
            <p class="sp-notes">{selectedSupplier.notes}</p>
          </section>
        {/if}
      {/if}
    </aside>
  </div>
</div>

<!-- ─── CREATE/EDIT SUPPLIER DIALOG ─── -->
{#if showSupplierDialog}
  <div class="sp-overlay" on:mousedown|self={() => showSupplierDialog = false}>
    <div class="sp-dialog">
      <div class="sp-dialog-header">
        <h2>{editingSupplierId ? 'Éditer le prestataire' : 'Nouveau prestataire'}</h2>
        <button class="sp-icon-btn" on:click={() => showSupplierDialog = false}>✕</button>
      </div>
      <div class="sp-dialog-body">
        <div class="sp-logo-row">
          <div class="sp-logo-preview">
            {#if logoPreview}
              <img src={logoPreview} alt="aperçu" />
            {:else if editingSupplierId && selectedSupplier?.logo_path}
              <img src={logoUrl(selectedSupplier)} alt={selectedSupplier.name} />
            {:else}
              <span class="sp-logo-placeholder">{getInitials(form.name || '??')}</span>
            {/if}
          </div>
          <div class="sp-logo-actions">
            <label class="sp-btn-secondary">
              📁 Choisir un logo
              <input type="file" accept="image/*" bind:this={fileInputEl} on:change={onLogoChange} style="display:none" />
            </label>
            {#if logoFile}
              <span class="sp-file-note">📎 {logoFile.name}</span>
            {/if}
            {#if editingSupplierId && selectedSupplier?.logo_path && !logoFile}
              <button class="sp-btn-link-danger" on:click={removeLogo}>Retirer le logo</button>
            {/if}
          </div>
        </div>

        <div class="sp-field-row">
          <label class="sp-field">
            <span>Nom *</span>
            <input type="text" bind:value={form.name} placeholder="Ageona, Konica Minolta…" />
          </label>
          <label class="sp-field">
            <span>Domaine</span>
            <select bind:value={form.domain}>
              <option value="">— Aucun —</option>
              {#each domains as d}<option value={d.name}>{d.name}</option>{/each}
            </select>
          </label>
        </div>

        <div class="sp-field-row">
          <label class="sp-field">
            <span>Téléphone</span>
            <input type="tel" bind:value={form.phone} placeholder="01 23 45 67 89" />
          </label>
          <label class="sp-field">
            <span>Email</span>
            <input type="email" bind:value={form.email} placeholder="contact@..." />
          </label>
        </div>

        <label class="sp-field">
          <span>Contact principal (nom)</span>
          <input type="text" bind:value={form.contact} placeholder="Prénom Nom" />
        </label>

        <label class="sp-field">
          <span>Notes</span>
          <textarea bind:value={form.notes} rows="2" placeholder="Optionnel — infos de relation, conditions, etc."></textarea>
        </label>

        <!-- Secondary contacts -->
        <div class="sp-contacts-editor">
          <div class="sp-contacts-header">
            <span>Contacts secondaires</span>
            <button class="sp-btn-link" on:click={addContactRow}>+ Ajouter</button>
          </div>
          {#each form.contacts as c, idx}
            <div class="sp-contact-edit">
              <input type="text" placeholder="Nom" bind:value={c.name} />
              <input type="text" placeholder="Rôle" bind:value={c.role} />
              <input type="tel" placeholder="Tél" bind:value={c.phone} />
              <input type="email" placeholder="Email" bind:value={c.email} />
              <button class="sp-icon-btn" on:click={() => removeContactRow(idx)}>✕</button>
            </div>
          {/each}
        </div>
      </div>
      <div class="sp-dialog-footer">
        <button class="sp-btn-secondary" on:click={() => showSupplierDialog = false}>Annuler</button>
        <button class="sp-btn-primary" on:click={saveSupplier} disabled={saving || !form.name.trim()}>
          {saving ? 'En cours…' : editingSupplierId ? 'Enregistrer' : 'Créer'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ─── DELETE CONFIRM ─── -->
{#if confirmDeleteSupplier}
  <div class="sp-overlay" on:mousedown|self={() => confirmDeleteSupplier = null}>
    <div class="sp-dialog" style="max-width:420px">
      <div class="sp-dialog-header">
        <h2>Supprimer ce prestataire ?</h2>
        <button class="sp-icon-btn" on:click={() => confirmDeleteSupplier = null}>✕</button>
      </div>
      <div class="sp-dialog-body">
        <p>« {confirmDeleteSupplier.name} » va être supprimé définitivement. Les dossiers et documents qui y étaient liés <strong>ne sont pas supprimés</strong> — ils garderont un supplier_id à <em>null</em> et apparaîtront comme "sans prestataire" jusqu'à ce que tu les réassignes.</p>
      </div>
      <div class="sp-dialog-footer">
        <button class="sp-btn-secondary" on:click={() => confirmDeleteSupplier = null}>Annuler</button>
        <button class="sp-btn-primary sp-btn-primary--danger" on:click={deleteSupplier} disabled={deleting}>
          {deleting ? 'Suppression…' : 'Supprimer'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ─── DOMAIN MANAGER ─── -->
{#if showDomainDialog}
  <div class="sp-overlay" on:mousedown|self={() => showDomainDialog = false}>
    <div class="sp-dialog" style="max-width:600px">
      <div class="sp-dialog-header">
        <h2>Gestion des domaines</h2>
        <button class="sp-icon-btn" on:click={() => showDomainDialog = false}>✕</button>
      </div>
      <div class="sp-dialog-body">
        <p style="font-size:12px; color:var(--text-muted); margin:0 0 12px">
          Les domaines servent à catégoriser les prestataires et leur donnent une couleur d'accent (badge sur la card + avatar de fallback).
        </p>
        {#each domainEdits as d}
          <div class="sp-domain-row">
            <input type="text" bind:value={d.name} on:blur={() => saveDomain(d)} />
            <input type="color" bind:value={d.color_hex} on:change={() => saveDomain(d)} />
            <input type="number" min="0" bind:value={d.sort_order} on:blur={() => saveDomain(d)} style="width:60px" title="Ordre" />
            <button class="sp-icon-btn" on:click={() => deleteDomain(d)}>🗑</button>
          </div>
        {/each}
        <div class="sp-domain-row sp-domain-row--new">
          <input type="text" placeholder="Nouveau domaine…" bind:value={newDomain.name} />
          <input type="color" bind:value={newDomain.color_hex} />
          <input type="number" min="0" bind:value={newDomain.sort_order} style="width:60px" />
          <button class="sp-btn-primary" on:click={addDomain} disabled={!newDomain.name.trim()}>+ Ajouter</button>
        </div>
      </div>
      <div class="sp-dialog-footer">
        <button class="sp-btn-secondary" on:click={() => showDomainDialog = false}>Fermer</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .suppliers-page {
    display: flex;
    flex-direction: column;
    height: calc(100vh - var(--header-height));
    overflow: hidden;
    margin: -1.875rem;
  }

  /* ── Top bar ── */
  .sp-topbar {
    height: 56px;
    background: var(--bg-card);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    padding: 0 18px;
    gap: 14px;
    flex-shrink: 0;
  }
  .sp-topbar h1 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-heading);
    margin: 0;
  }
  .sp-crumb { color: var(--text-muted); font-weight: 400; }
  .sp-search {
    flex: 1;
    max-width: 460px;
    position: relative;
  }
  .sp-search input {
    width: 100%;
    background: var(--bg-input, rgba(0,0,0,0.04));
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 7px 12px 7px 34px;
    color: var(--text-primary);
    font-size: 13px;
    outline: none;
    font-family: inherit;
  }
  .sp-search input:focus { border-color: var(--primary); }
  .sp-search__icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 11px;
    opacity: 0.5;
  }
  .sp-spacer { flex: 1; }

  .sp-btn-primary {
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }
  .sp-btn-primary:hover:not(:disabled) { filter: brightness(1.1); }
  .sp-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .sp-btn-primary--danger { background: #EF4444; }
  .sp-btn-secondary {
    background: rgba(255,255,255,0.06);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
  }
  .sp-btn-secondary:hover { background: rgba(255,255,255,0.1); }
  .sp-btn-link {
    background: none;
    border: none;
    color: var(--primary);
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    text-decoration: underline;
  }
  .sp-btn-link-danger {
    background: none;
    border: none;
    color: #EF4444;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    text-decoration: underline;
  }

  /* ── Layout ── */
  .sp-layout {
    flex: 1;
    display: grid;
    grid-template-columns: 240px 1fr 480px;
    overflow: hidden;
  }

  /* ── Filters sidebar ── */
  .sp-filters {
    background: var(--bg-card);
    border-right: 1px solid var(--border-subtle);
    overflow-y: auto;
    padding: 14px;
  }
  .sp-filter-section { margin-bottom: 18px; }
  .sp-filter-section h3 {
    font-size: 10px;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
  }
  .sp-filter-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12.5px;
    color: var(--text-secondary);
    transition: background 0.1s, color 0.1s;
  }
  .sp-filter-item:hover { background: rgba(255,255,255,0.04); color: var(--text-primary); }
  .sp-filter-item.active {
    background: rgba(var(--primary-rgb,136,105,225),0.14);
    color: var(--primary);
    font-weight: 500;
  }
  .sp-count {
    font-size: 11px;
    color: var(--text-muted);
    background: rgba(255,255,255,0.04);
    padding: 1px 6px;
    border-radius: 8px;
  }
  .sp-filter-item.active .sp-count {
    background: rgba(var(--primary-rgb,136,105,225),0.2);
    color: var(--primary);
  }
  .sp-filter-icon { display: inline-flex; align-items: center; gap: 7px; }
  .sp-filter-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .sp-toggle {
    font-size: 14px;
    color: var(--success, #22C55E);
    font-weight: 700;
  }

  /* ── Supplier cards list ── */
  .sp-list {
    overflow-y: auto;
    background: var(--bg-base);
    padding: 14px;
  }
  .sp-list-header {
    padding: 0 4px 10px;
  }
  .sp-list-header h2 {
    font-size: 13px;
    color: var(--text-secondary);
    font-weight: 500;
    margin: 0;
  }
  .sp-list-header h2 strong { color: var(--text-heading); }
  .sp-empty {
    text-align: center;
    color: var(--text-muted);
    padding: 32px 16px;
    font-size: 13px;
  }

  .sp-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .sp-card:hover { border-color: rgba(255,255,255,0.18); }
  .sp-card.selected {
    border-color: var(--primary);
    box-shadow: 0 0 0 1px var(--primary), 0 4px 14px rgba(var(--primary-rgb,136,105,225),0.2);
  }
  .sp-card__top {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    margin-bottom: 10px;
  }
  .sp-card__main { flex: 1; min-width: 0; }
  .sp-card__title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-heading);
    margin-bottom: 3px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .sp-card__meta {
    font-size: 11.5px;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .sp-status-pill {
    padding: 3px 9px;
    border-radius: 11px;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.02em;
    flex-shrink: 0;
    white-space: nowrap;
  }
  .sp-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }

  .sp-avatar {
    width: 38px;
    height: 38px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-weight: 700;
    font-size: 12px;
    flex-shrink: 0;
  }
  .sp-avatar--img {
    background: rgba(255, 255, 255, 0.9);
    object-fit: contain;
    padding: 3px;
  }
  .sp-avatar--lg {
    width: 56px;
    height: 56px;
    font-size: 16px;
    border-radius: 10px;
  }

  .sp-kpis {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--border-subtle);
  }
  .sp-kpi { display: flex; flex-direction: column; gap: 1px; }
  .sp-kpi__label {
    font-size: 9.5px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .sp-kpi__value {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-heading);
    font-variant-numeric: tabular-nums;
  }
  .sp-kpi__value--sm { font-size: 11.5px; }

  .sp-card__footer {
    display: flex;
    gap: 12px;
    margin-top: 8px;
    font-size: 11px;
    color: var(--text-muted);
  }
  .sp-mini { display: inline-flex; gap: 4px; align-items: center; }

  /* ── Detail panel ── */
  .sp-detail {
    background: var(--bg-card);
    border-left: 1px solid var(--border-subtle);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .sp-detail__empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    text-align: center;
    padding: 40px;
    gap: 12px;
  }
  .sp-detail__empty-icon { font-size: 40px; opacity: 0.4; }

  .sp-detail-header {
    padding: 16px 18px 12px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .sp-detail-header__top {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  .sp-detail-id {
    display: flex;
    gap: 12px;
    flex: 1;
    min-width: 0;
  }
  .sp-detail-header h2 {
    font-size: 17px;
    color: var(--text-heading);
    font-weight: 600;
    margin: 0 0 6px;
  }
  .sp-detail-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .sp-detail-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }

  .sp-icon-btn {
    background: transparent;
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    padding: 5px 8px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    font-family: inherit;
  }
  .sp-icon-btn:hover { background: rgba(255,255,255,0.06); color: var(--text-primary); }
  .sp-icon-btn--danger:hover {
    background: rgba(239,68,68,0.15);
    border-color: rgba(239,68,68,0.5);
    color: #EF4444;
  }

  .sp-detail-section {
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .sp-section-header {
    margin-bottom: 10px;
  }
  .sp-section-header h3 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    margin: 0;
    font-weight: 700;
  }
  .sp-section-empty {
    color: var(--text-muted);
    font-size: 12.5px;
    margin: 6px 0;
    font-style: italic;
  }

  /* KPI grid */
  .sp-kpi-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .sp-kpi-card {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .sp-kpi-card__label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  .sp-kpi-card__value {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-heading);
    font-variant-numeric: tabular-nums;
  }
  .sp-kpi-card__value--sm { font-size: 14px; }
  .sp-kpi-card__sub { font-size: 11px; color: var(--text-muted); }

  /* Actions */
  .sp-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .sp-action {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
  }
  .sp-action:hover { border-color: var(--primary); background: rgba(var(--primary-rgb,136,105,225),0.08); }

  /* Contacts */
  .sp-contact-card {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 6px;
  }
  .sp-contact-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-heading);
    margin-bottom: 4px;
  }
  .sp-contact-role { color: var(--text-muted); font-weight: 400; font-size: 11.5px; }
  .sp-contact-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .sp-contact-bit { display: inline-flex; gap: 4px; align-items: center; }
  .sp-tiny-btn {
    background: none;
    border: 1px solid var(--border-subtle);
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 10px;
    color: var(--text-secondary);
    cursor: pointer;
    font-family: inherit;
  }
  .sp-tiny-btn:hover { background: rgba(255,255,255,0.05); }

  /* Services */
  .sp-services {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .sp-service {
    background: var(--bg-base);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11.5px;
    color: var(--text-secondary);
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .sp-service__count {
    background: rgba(var(--primary-rgb,136,105,225),0.15);
    color: var(--primary);
    border-radius: 8px;
    padding: 0 6px;
    font-size: 10px;
    font-weight: 700;
  }

  /* Timeline */
  .sp-timeline {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .sp-tl-item {
    display: flex;
    gap: 10px;
    padding-left: 4px;
  }
  .sp-tl-icon {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--bg-base);
    border: 1.5px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    flex-shrink: 0;
  }
  .sp-tl-body { flex: 1; min-width: 0; }
  .sp-tl-text {
    font-size: 12.5px;
    color: var(--text-primary);
    line-height: 1.4;
    white-space: pre-line;
  }
  .sp-tl-meta {
    margin-top: 2px;
    font-size: 11px;
    color: var(--text-muted);
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .sp-tl-dossier { color: var(--text-secondary); }

  .sp-notes {
    font-size: 12.5px;
    color: var(--text-secondary);
    line-height: 1.5;
    margin: 0;
    white-space: pre-line;
  }

  /* ── Dialog ── */
  .sp-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 20, 35, 0.72);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
  }
  .sp-dialog {
    background: var(--bg-card, #fff);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 12px;
    width: min(540px, 92vw);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 70px rgba(0,0,0,0.55), 0 4px 12px rgba(0,0,0,0.3);
  }
  .sp-dialog-header {
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .sp-dialog-header h2 {
    margin: 0;
    font-size: 15px;
    color: var(--text-heading);
    font-weight: 600;
  }
  .sp-dialog-body {
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
  }
  .sp-dialog-footer {
    padding: 12px 18px;
    border-top: 1px solid var(--border-subtle);
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .sp-logo-row {
    display: flex;
    gap: 14px;
    align-items: center;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .sp-logo-preview {
    width: 72px;
    height: 72px;
    border-radius: 12px;
    background: rgba(255,255,255,0.04);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    flex-shrink: 0;
  }
  .sp-logo-preview img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }
  .sp-logo-placeholder {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-secondary);
  }
  .sp-logo-actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .sp-file-note { font-size: 11.5px; color: var(--text-muted); }

  .sp-field { display: flex; flex-direction: column; gap: 4px; }
  .sp-field span {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
  }
  .sp-field input,
  .sp-field textarea,
  .sp-field select {
    background: var(--bg-input, rgba(255,255,255,0.04));
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    padding: 7px 10px;
    color: var(--text-primary);
    font-size: 13px;
    font-family: inherit;
    outline: none;
  }
  .sp-field input:focus,
  .sp-field textarea:focus,
  .sp-field select:focus { border-color: var(--primary); }
  .sp-field textarea { resize: vertical; min-height: 56px; }
  .sp-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

  .sp-contacts-editor {
    border-top: 1px solid var(--border-subtle);
    padding-top: 10px;
  }
  .sp-contacts-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  .sp-contact-edit {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr 32px;
    gap: 6px;
    margin-bottom: 6px;
  }
  .sp-contact-edit input {
    background: var(--bg-input, rgba(255,255,255,0.04));
    border: 1px solid var(--border-subtle);
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 12px;
    color: var(--text-primary);
    font-family: inherit;
    outline: none;
    min-width: 0;
  }

  .sp-domain-row {
    display: grid;
    grid-template-columns: 1fr 50px 60px 36px;
    gap: 8px;
    margin-bottom: 6px;
    align-items: center;
  }
  .sp-domain-row--new {
    grid-template-columns: 1fr 50px 60px auto;
    border-top: 1px solid var(--border-subtle);
    padding-top: 10px;
    margin-top: 10px;
  }
  .sp-domain-row input[type="text"],
  .sp-domain-row input[type="number"] {
    background: var(--bg-input, rgba(255,255,255,0.04));
    border: 1px solid var(--border-subtle);
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 12px;
    color: var(--text-primary);
    font-family: inherit;
    outline: none;
  }
  .sp-domain-row input[type="color"] {
    width: 50px;
    height: 28px;
    border: 1px solid var(--border-subtle);
    border-radius: 4px;
    background: transparent;
    cursor: pointer;
  }
</style>
