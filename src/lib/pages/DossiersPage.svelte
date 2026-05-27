<script>
  // v7.0.0 — Module Documents reconçu autour de la notion de "Dossier".
  // Un dossier regroupe les pièces (Devis, BPA, Facture) d'une même opération
  // d'achat IT, plus ses notes et son état d'avancement. Voir la maquette
  // docs/documents-redesign-mockup.html pour le rationnel.
  //
  // Cette page propose deux vues :
  //  - "Dossiers" (3 colonnes : filtres / liste / détail) — vue par défaut
  //  - "Documents (à plat)" — l'ancienne vue conservée comme filet de sécurité
  //    en attendant qu'on soit certain que les Dossiers couvrent 100% des cas

  import { onMount, tick } from 'svelte';
  import { api, API_BASE } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';
  import { establishments } from '../stores/establishments.js';
  import EstablishmentBadge from '../components/EstablishmentBadge.svelte';
  import DocumentsPage from './DocumentsPage.svelte';

  // ── State ─────────────────────────────────────────────────
  let viewMode = 'dossiers'; // 'dossiers' | 'flat'

  let dossiers = [];
  let selectedDossierId = null;
  let selectedDossier = null;
  let loading = true;
  let stats = { total: 0, per_status: {}, smart: {} };

  // Filters
  let filterStatus = '';
  let filterSupplier = null;
  let filterSite = '';
  let searchQuery = '';
  let searchTimer;

  // For supplier filter chips
  let allSuppliers = [];

  // Dialogs — single form reused for both create and edit modes. `editingDossierId`
  // is null in create mode, set to a dossier.id in edit mode.
  let showDossierDialog = false;
  let editingDossierId = null;
  let dossierForm = blankForm();
  let saving = false;

  let showAttachDialog = false;
  let attachableDocs = [];
  let attachLoading = false;

  // Track in-flight amount edits so we don't double-fire on every keystroke.
  let pendingAmountSaves = {};

  let allProjects = [];

  // ── Constants ─────────────────────────────────────────────
  // Order matters: it drives the dropdown ordering AND the sidebar filter order.
  // `hint` is shown as a tooltip on the filter item so the user understands that
  // each state = "stage actuel", not "le dossier contient ce type de doc".
  const STATUSES = [
    { value: 'demande_envoyee', label: 'Demande envoyée',     color: '#94A3B8', shortLabel: 'Demande',  hint: 'En attente d\'un devis du presta' },
    { value: 'devis_recu',      label: 'Devis · sans BPA',    color: '#3B82F6', shortLabel: 'Devis',    hint: 'Devis reçu, BPA pas encore signé' },
    { value: 'bpa_signe',       label: 'BPA · sans commande', color: '#8B5CF6', shortLabel: 'BPA',      hint: 'BPA signé, commande pas encore passée/facturée' },
    { value: 'commande',        label: 'Commandé',            color: '#22C55E', shortLabel: 'Commandé', hint: 'Facture reçue, en attente de livraison' },
    { value: 'livre',           label: 'Livré / Installé',    color: '#16A34A', shortLabel: 'Livré',    hint: 'Matériel reçu et déployé' },
    { value: 'archive',         label: 'Archivé',             color: '#6B7280', shortLabel: 'Archivé',  hint: 'Clos, plus de suivi à faire' },
  ];

  const DOC_TYPE_COLORS = {
    DEVIS:   '#3B82F6',
    BPA:     '#8B5CF6',
    BON:     '#8B5CF6',
    CONTRAT: '#14B8A6',
    FACTURE: '#22C55E',
    RAPPORT: '#F59E0B',
    AUTRE:   '#6B7280',
  };

  function blankForm() {
    return {
      title: '',
      description: '',
      status: 'demande_envoyee',
      supplier_id: null,
      project_id: null,
      site: '',
      estimated_budget: 0,
      notes: '',
    };
  }

  function statusInfo(value) {
    return STATUSES.find(s => s.value === value) || STATUSES[0];
  }

  // ── Loading ───────────────────────────────────────────────
  onMount(async () => {
    await Promise.all([loadDossiers(), loadStats(), loadSuppliers(), loadProjects()]);
  });

  async function loadProjects() {
    try {
      allProjects = await api.get('/api/projects');
    } catch { allProjects = []; }
  }

  async function loadDossiers() {
    loading = true;
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set('status', filterStatus);
      if (filterSupplier) params.set('supplier_id', filterSupplier);
      if (filterSite) params.set('site', filterSite);
      if (searchQuery) params.set('search', searchQuery);
      const q = params.toString();
      dossiers = await api.get('/api/dossiers' + (q ? '?' + q : ''));
      // Keep selected dossier if still in list, else clear.
      if (selectedDossierId && !dossiers.find(d => d.id === selectedDossierId)) {
        selectedDossierId = null;
        selectedDossier = null;
      }
    } catch (e) {
      toastError('Erreur chargement dossiers');
      dossiers = [];
    } finally {
      loading = false;
    }
  }

  async function loadStats() {
    try {
      stats = await api.get('/api/dossiers/stats/summary');
    } catch {}
  }

  async function loadSuppliers() {
    try {
      allSuppliers = await api.get('/api/suppliers');
    } catch { allSuppliers = []; }
  }

  // Reactive: reload when filters change. Search is debounced.
  $: filterStatus, filterSupplier, filterSite, loadDossiers();

  function onSearchInput() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadDossiers, 280);
  }

  // ── Selection ─────────────────────────────────────────────
  async function selectDossier(id) {
    selectedDossierId = id;
    try {
      selectedDossier = await api.get(`/api/dossiers/${id}`);
    } catch (e) {
      toastError('Impossible de charger le dossier');
      selectedDossier = null;
    }
  }

  // ── Mutations ─────────────────────────────────────────────
  function openCreateDialog() {
    editingDossierId = null;
    dossierForm = blankForm();
    showDossierDialog = true;
  }

  function openEditDialog() {
    if (!selectedDossier) return;
    editingDossierId = selectedDossier.id;
    dossierForm = {
      title: selectedDossier.title || '',
      description: selectedDossier.description || '',
      status: selectedDossier.status || 'demande_envoyee',
      supplier_id: selectedDossier.supplier_id || null,
      project_id: selectedDossier.project_id || null,
      site: selectedDossier.site || '',
      estimated_budget: selectedDossier.estimated_budget || 0,
      notes: selectedDossier.notes || '',
    };
    showDossierDialog = true;
  }

  async function saveDossier() {
    if (!dossierForm.title.trim()) return;
    saving = true;
    try {
      // Coerce empty selects ('' from <select>) to null for FK fields so the
      // backend doesn't try to UPDATE with the empty string.
      const payload = {
        ...dossierForm,
        supplier_id: dossierForm.supplier_id || null,
        project_id: dossierForm.project_id || null,
      };
      let result;
      if (editingDossierId) {
        result = await api.put(`/api/dossiers/${editingDossierId}`, payload);
        success('Dossier modifié');
      } else {
        result = await api.post('/api/dossiers', payload);
        success('Dossier créé');
      }
      showDossierDialog = false;
      dossierForm = blankForm();
      editingDossierId = null;
      await loadDossiers();
      await loadStats();
      selectedDossierId = result.id;
      selectedDossier = result;
    } catch (e) {
      toastError('Erreur : ' + (e.message || ''));
    } finally {
      saving = false;
    }
  }

  async function changeStatus(newStatus) {
    if (!selectedDossier || newStatus === selectedDossier.status) return;
    try {
      selectedDossier = await api.put(`/api/dossiers/${selectedDossier.id}/status`, {
        status: newStatus,
      });
      // Refresh the list so the card reflects the new state too.
      await loadDossiers();
      await loadStats();
      success('Statut mis à jour');
    } catch (e) {
      toastError('Erreur changement statut');
    }
  }

  async function updateField(field, value) {
    if (!selectedDossier) return;
    try {
      selectedDossier = await api.put(`/api/dossiers/${selectedDossier.id}`, {
        [field]: value,
      });
      await loadDossiers();
    } catch {
      toastError(`Échec mise à jour ${field}`);
    }
  }

  async function deleteDossier() {
    if (!selectedDossier) return;
    if (!confirm(`Supprimer le dossier "${selectedDossier.title}" ?\n\nLes documents qu'il contient ne seront PAS supprimés — ils redeviendront simplement non-rattachés et tu pourras les rattacher à un autre dossier ensuite.`)) return;
    try {
      await api.delete(`/api/dossiers/${selectedDossier.id}`);
      selectedDossier = null;
      selectedDossierId = null;
      await loadDossiers();
      await loadStats();
      success('Dossier supprimé');
    } catch (e) {
      toastError('Erreur suppression');
    }
  }

  // ── Document attach/detach ────────────────────────────────
  async function openAttachDialog() {
    showAttachDialog = true;
    attachLoading = true;
    try {
      const allDocs = await api.get('/api/documents');
      // Show only docs not already in this dossier — backend has no filter
      // for this yet, so we drop them client-side. List is small enough that
      // it doesn't matter performance-wise.
      const attachedIds = new Set((selectedDossier?.documents || []).map(d => d.id));
      attachableDocs = (allDocs || []).filter(d => !attachedIds.has(d.id));
    } catch {
      attachableDocs = [];
    } finally {
      attachLoading = false;
    }
  }

  async function attachDoc(docId) {
    if (!selectedDossier) return;
    try {
      selectedDossier = await api.post(`/api/dossiers/${selectedDossier.id}/attach`, {
        document_id: docId,
      });
      showAttachDialog = false;
      await loadDossiers();
      success('Document rattaché');
    } catch (e) {
      toastError('Erreur rattachement');
    }
  }

  async function detachDoc(docId) {
    if (!selectedDossier) return;
    if (!confirm('Détacher ce document du dossier ? Le document n\'est pas supprimé.')) return;
    try {
      await api.delete(`/api/dossiers/${selectedDossier.id}/documents/${docId}`);
      selectedDossier = await api.get(`/api/dossiers/${selectedDossier.id}`);
      await loadDossiers();
      success('Document détaché');
    } catch {
      toastError('Erreur détachement');
    }
  }

  // ── Document amount edit (inline) ─────────────────────────
  // Triggered on blur — coerces the input value to a number, saves it, and
  // refreshes the dossier so the budget summary stays in sync.
  async function saveDocAmount(docId, field, rawValue) {
    if (!selectedDossier) return;
    const doc = (selectedDossier.documents || []).find(d => d.id === docId);
    if (!doc) return;
    const num = Number(rawValue) || 0;
    if (num === (doc[field] || 0)) return;  // no change, skip
    const payload = {
      amount: field === 'amount' ? num : (doc.amount || 0),
      amount_accepted: field === 'amount_accepted' ? num : (doc.amount_accepted || 0),
    };
    pendingAmountSaves[docId] = true;
    try {
      await api.put(`/api/documents/${docId}/amount`, payload);
      selectedDossier = await api.get(`/api/dossiers/${selectedDossier.id}`);
      await loadDossiers();
    } catch {
      toastError('Échec mise à jour montant');
    } finally {
      pendingAmountSaves[docId] = false;
    }
  }

  // ── Helpers ───────────────────────────────────────────────
  function formatDate(iso) {
    if (!iso) return '—';
    const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return iso;
    return `${m[3]}/${m[2]}/${m[1]}`;
  }

  function formatRelative(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const day = 86400000;
    if (diff < day) return "aujourd'hui";
    if (diff < 2 * day) return 'hier';
    if (diff < 7 * day) return `il y a ${Math.floor(diff / day)}j`;
    return formatDate(iso);
  }

  function fmtEur(n) {
    if (n == null || isNaN(n)) return '—';
    if (n === 0) return '—';
    return Math.round(n).toLocaleString('fr-FR') + ' €';
  }

  // Workflow types present in the chain — drives the mini timeline rendering.
  function timelineSteps(d) {
    const types = new Set((d.summary?.chain_types || []).map(t => t.toUpperCase()));
    return [
      { type: 'DEVIS',   label: 'Devis',   done: types.has('DEVIS') || types.has('PROPOSITION') },
      { type: 'BPA',     label: 'BPA',     done: types.has('BPA') || types.has('BON') },
      { type: 'FACTURE', label: 'Facture', done: types.has('FACTURE') },
    ];
  }

  function supplierInitials(s) {
    if (!s?.name) return '??';
    const parts = s.name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return s.name.slice(0, 2).toUpperCase();
  }
</script>

{#if viewMode === 'flat'}
  <!-- Flat-list fallback (existing DocumentsPage) — wrapped with a small
       header so the user can switch back to Dossiers. -->
  <div class="view-switch">
    <div class="view-switch__title">Documents — vue à plat</div>
    <div class="view-switch__hint">Filet de sécurité v7.0.0 — pour revenir au flot classique</div>
    <button class="view-switch__btn" on:click={() => viewMode = 'dossiers'}>
      ← Revenir aux Dossiers
    </button>
  </div>
  <DocumentsPage />
{:else}

<!-- ─── DOSSIERS VIEW — 3 columns ─── -->
<div class="dossiers-page">

  <!-- Top bar -->
  <header class="ds-topbar">
    <h1>Documents · <span class="ds-crumb">Dossiers</span></h1>
    <div class="ds-search">
      <span class="ds-search__icon">🔎</span>
      <input
        type="text"
        placeholder="Rechercher un dossier, un prestataire…"
        bind:value={searchQuery}
        on:input={onSearchInput}
      />
    </div>
    <div class="ds-spacer"></div>
    <div class="ds-toggle">
      <button class="active">Dossiers</button>
      <button on:click={() => viewMode = 'flat'}>Documents (à plat)</button>
    </div>
    <button class="ds-btn-primary" on:click={openCreateDialog}>
      + Nouveau dossier
    </button>
  </header>

  <div class="ds-layout">

    <!-- ─── FILTERS ─── -->
    <aside class="ds-filters">
      <div class="ds-filter-section">
        <h3>État du dossier</h3>
        <div class="ds-filter-item" class:active={filterStatus === ''} on:click={() => filterStatus = ''}>
          <span>Tous</span>
          <span class="ds-count">{stats.total}</span>
        </div>
        {#each STATUSES as s}
          <div
            class="ds-filter-item"
            class:active={filterStatus === s.value}
            on:click={() => filterStatus = s.value}
            title={s.hint}
          >
            <span class="ds-filter-icon">
              <span class="ds-filter-dot" style="background:{s.color}"></span>
              {s.label}
            </span>
            <span class="ds-count">{stats.per_status?.[s.value] || 0}</span>
          </div>
        {/each}
      </div>

      <div class="ds-filter-section">
        <h3>Établissement</h3>
        <div class="ds-filter-item" class:active={filterSite === ''} on:click={() => filterSite = ''}>
          <span>Tous</span>
        </div>
        {#each $establishments as e}
          <div class="ds-filter-item" class:active={filterSite === e.code} on:click={() => filterSite = e.code}>
            <span class="ds-filter-icon">🏫 {e.code}</span>
          </div>
        {/each}
      </div>

      <div class="ds-filter-section">
        <h3>Prestataire</h3>
        <div class="ds-filter-item" class:active={!filterSupplier} on:click={() => filterSupplier = null}>
          <span>Tous</span>
        </div>
        {#each allSuppliers.slice(0, 8) as s}
          <div class="ds-filter-item" class:active={filterSupplier === s.id} on:click={() => filterSupplier = s.id}>
            <span class="ds-filter-icon">📦 {s.name}</span>
          </div>
        {/each}
        {#if allSuppliers.length > 8}
          <div class="ds-filter-item ds-filter-item--muted">
            <span>+ {allSuppliers.length - 8} autres</span>
          </div>
        {/if}
      </div>
    </aside>

    <!-- ─── DOSSIER LIST ─── -->
    <main class="ds-list">
      <div class="ds-list-header">
        <h2>
          <strong>{dossiers.length}</strong>
          {dossiers.length > 1 ? 'dossiers' : 'dossier'}
          {#if stats.smart?.a_relancer > 0}
            · <span style="color:var(--warning)">{stats.smart.a_relancer} à relancer</span>
          {/if}
        </h2>
      </div>

      {#if loading}
        <div class="ds-empty">Chargement…</div>
      {:else if dossiers.length === 0}
        <div class="ds-empty">
          {#if searchQuery || filterStatus || filterSupplier || filterSite}
            Aucun dossier ne correspond aux filtres.
          {:else}
            Aucun dossier. Clique sur "+ Nouveau dossier" pour démarrer.
          {/if}
        </div>
      {:else}
        {#each dossiers as d (d.id)}
          {@const status = statusInfo(d.status)}
          {@const steps = timelineSteps(d)}
          <article
            class="ds-card"
            class:selected={selectedDossierId === d.id}
            on:click={() => selectDossier(d.id)}
          >
            <div class="ds-card__top">
              <div class="ds-supplier-avatar" style="background:{d.supplier?.color || '#6B7280'}">
                {d.supplier ? supplierInitials(d.supplier) : '?'}
              </div>
              <div class="ds-card__main">
                <div class="ds-card__title">{d.title}</div>
                <div class="ds-card__meta">
                  {#if d.supplier}<span>{d.supplier.name}</span>{:else}<span class="muted">(sans prestataire)</span>{/if}
                  {#if d.site}
                    <span class="dot">·</span>
                    <EstablishmentBadge code={d.site} size="xs" showLabel={true} />
                  {/if}
                  {#if d.project}
                    <span class="dot">·</span>
                    <span class="ds-card__project">🎯 {d.project.title}</span>
                  {/if}
                </div>
              </div>
              <span class="ds-status-pill" style="background:{status.color}22;color:{status.color}">
                {status.shortLabel}
              </span>
            </div>

            <div class="ds-timeline-mini">
              {#each steps as step, i}
                <span class="ds-tl-dot"
                  class:done={step.done}
                  style:--c={DOC_TYPE_COLORS[step.type] || '#6B7280'}
                ></span>
                {#if i < steps.length - 1}
                  <span class="ds-tl-line" class:done={step.done}></span>
                {/if}
              {/each}
            </div>

            <div class="ds-amounts">
              <div class="ds-amount">
                <span class="ds-amount__label">Devis</span>
                <span class="ds-amount__value" class:muted={!d.summary?.devis_total}>{fmtEur(d.summary?.devis_total)}</span>
              </div>
              <div class="ds-amount">
                <span class="ds-amount__label">Engagé (BPA)</span>
                <span class="ds-amount__value" class:muted={!d.summary?.bpa_total}>{fmtEur(d.summary?.bpa_total)}</span>
              </div>
              <div class="ds-amount">
                <span class="ds-amount__label">Facturé</span>
                <span class="ds-amount__value" class:muted={!d.summary?.facture_total} style:color={d.summary?.facture_total ? 'var(--success)' : ''}>{fmtEur(d.summary?.facture_total)}</span>
              </div>
            </div>

            <div class="ds-card__footer">
              <span>{d.summary?.doc_count || 0} document{(d.summary?.doc_count || 0) > 1 ? 's' : ''}</span>
              <span class="muted">Modifié {formatRelative(d.updated_at)}</span>
            </div>
          </article>
        {/each}
      {/if}
    </main>

    <!-- ─── DETAIL PANEL ─── -->
    <aside class="ds-detail">
      {#if !selectedDossier}
        <div class="ds-detail__empty">
          <span class="ds-detail__empty-icon">📂</span>
          <p>Sélectionne un dossier pour voir son contenu.</p>
        </div>
      {:else}
        {@const status = statusInfo(selectedDossier.status)}

        <header class="ds-detail-header">
          <div class="ds-detail-header__top">
            <h2>{selectedDossier.title}</h2>
            <button class="ds-icon-btn" on:click={openEditDialog} title="Éditer le dossier">✏️</button>
            <button class="ds-icon-btn" on:click={deleteDossier} title="Supprimer le dossier">🗑</button>
          </div>

          <div class="ds-detail-meta">
            {#if selectedDossier.supplier}
              <span class="ds-chip">
                <span class="ds-supplier-avatar ds-supplier-avatar--xs" style="background:{selectedDossier.supplier.color}">
                  {supplierInitials(selectedDossier.supplier)}
                </span>
                {selectedDossier.supplier.name}
              </span>
            {/if}
            {#if selectedDossier.site}
              <span class="ds-chip"><EstablishmentBadge code={selectedDossier.site} size="xs" showLabel={true} /></span>
            {/if}
            {#if selectedDossier.project}
              <span class="ds-chip">🎯 {selectedDossier.project.title}</span>
            {/if}
          </div>

          <div class="ds-status-row">
            <span class="ds-status-label">Statut</span>
            <!-- bind:value ensures the <select> always reflects the model;
                 we re-issue the API call on change explicitly. -->
            <select
              class="ds-status-select"
              style="border-color:{status.color}; color:{status.color}"
              bind:value={selectedDossier.status}
              on:change={(e) => changeStatus(e.target.value)}
            >
              {#each STATUSES as s}
                <option value={s.value}>{s.label}</option>
              {/each}
            </select>
          </div>

          {#if selectedDossier.description}
            <p class="ds-description">{selectedDossier.description}</p>
          {/if}
        </header>

        <!-- Documents block -->
        <section class="ds-detail-section">
          <div class="ds-section-header">
            <h3>Documents <span class="ds-section-count">{selectedDossier.documents?.length || 0}</span></h3>
            <button class="ds-btn-secondary" on:click={openAttachDialog}>+ Rattacher un document</button>
          </div>

          {#if (selectedDossier.documents || []).length === 0}
            <p class="ds-section-empty">Aucun document rattaché.</p>
          {:else}
            {#each selectedDossier.documents as doc}
              {@const dtype = (doc.doc_type || '').toUpperCase()}
              {@const dcolor = DOC_TYPE_COLORS[dtype] || '#6B7280'}
              {@const showAccepted = ['DEVIS', 'BPA', 'BON', 'PROPOSITION'].includes(dtype)}
              <div class="ds-doc-item">
                <div class="ds-doc-badge" style="background:linear-gradient(160deg, {dcolor}, color-mix(in srgb, {dcolor} 70%, black))">
                  {dtype.slice(0, 3) || 'DOC'}
                  {#if doc.is_acompte && dtype === 'FACTURE'}
                    <span class="ds-doc-acompte" title="Acompte">⏱</span>
                  {/if}
                </div>
                <div class="ds-doc-info">
                  <div class="ds-doc-title">{doc.title}</div>
                  <div class="ds-doc-sub">
                    {#if doc.internal_ref}<span class="ds-doc-ref">{doc.internal_ref}</span>{/if}
                    {#if doc.doc_date}<span>{formatDate(doc.doc_date)}</span>{/if}
                  </div>
                  <!-- Inline amount edit. amount = "demandé/déclaré", amount_accepted = "validé après négo" (devis/BPA only). -->
                  <div class="ds-doc-amount-edit">
                    <label class="ds-mini-label">€
                      <input
                        type="number"
                        min="0"
                        step="1"
                        class="ds-amount-input"
                        value={doc.amount || ''}
                        placeholder="0"
                        on:blur={(e) => saveDocAmount(doc.id, 'amount', e.target.value)}
                      />
                    </label>
                    {#if showAccepted}
                      <label class="ds-mini-label">Validé
                        <input
                          type="number"
                          min="0"
                          step="1"
                          class="ds-amount-input"
                          value={doc.amount_accepted || ''}
                          placeholder="0"
                          on:blur={(e) => saveDocAmount(doc.id, 'amount_accepted', e.target.value)}
                        />
                      </label>
                    {/if}
                  </div>
                </div>
                <button class="ds-icon-btn" on:click={() => detachDoc(doc.id)} title="Détacher">✕</button>
              </div>
            {/each}
          {/if}
        </section>

        <!-- Budget block (info-only) -->
        {#if selectedDossier.summary?.devis_total || selectedDossier.summary?.bpa_total || selectedDossier.summary?.facture_total}
          <section class="ds-detail-section">
            <div class="ds-section-header">
              <h3>Budget · pour info</h3>
            </div>
            <div class="ds-budget">
              <div class="ds-budget-row">
                <span>Devis</span>
                <span class="ds-budget-val">{fmtEur(selectedDossier.summary.devis_total)}</span>
              </div>
              <div class="ds-budget-row">
                <span>Engagé (BPA)</span>
                <span class="ds-budget-val">{fmtEur(selectedDossier.summary.bpa_total)}</span>
              </div>
              <div class="ds-budget-row">
                <span>Facturé</span>
                <span class="ds-budget-val" style="color:var(--success)">{fmtEur(selectedDossier.summary.facture_total)}</span>
              </div>
            </div>
          </section>
        {/if}

        <!-- Activity / comments — v7.0.1 will surface the full feed + add UI -->
        {#if (selectedDossier.comments || []).length > 0}
          <section class="ds-detail-section">
            <div class="ds-section-header">
              <h3>Activité récente</h3>
            </div>
            <div class="ds-activity">
              {#each selectedDossier.comments.slice(0, 8) as c}
                <div class="ds-activity-item">
                  <div class="ds-activity-dot ds-activity-dot--{c.kind}">
                    {#if c.kind === 'status'}↻{:else if c.kind === 'doc'}📄{:else if c.kind === 'delivery'}📦{:else}💬{/if}
                  </div>
                  <div class="ds-activity-body">
                    <div class="ds-activity-text">{c.body}</div>
                    <div class="ds-activity-meta">{formatRelative(c.created_at)}</div>
                  </div>
                </div>
              {/each}
            </div>
          </section>
        {/if}
      {/if}
    </aside>

  </div>
</div>

<!-- ─── CREATE / EDIT DIALOG (unified) ─── -->
{#if showDossierDialog}
  <div class="ds-overlay" on:mousedown|self={() => showDossierDialog = false}>
    <div class="ds-dialog">
      <div class="ds-dialog-header">
        <h2>{editingDossierId ? 'Éditer le dossier' : 'Nouveau dossier'}</h2>
        <button class="ds-icon-btn" on:click={() => showDossierDialog = false}>✕</button>
      </div>
      <div class="ds-dialog-body">
        <label class="ds-field">
          <span>Titre *</span>
          <input type="text" bind:value={dossierForm.title} placeholder="Ex : Renouvellement firewall NDK" autofocus />
        </label>
        <label class="ds-field">
          <span>Description</span>
          <textarea bind:value={dossierForm.description} rows="2" placeholder="Optionnel — quelques mots de contexte"></textarea>
        </label>
        <div class="ds-field-row">
          <label class="ds-field">
            <span>Statut</span>
            <select bind:value={dossierForm.status}>
              {#each STATUSES as s}<option value={s.value}>{s.label}</option>{/each}
            </select>
          </label>
          <label class="ds-field">
            <span>Établissement</span>
            <select bind:value={dossierForm.site}>
              <option value="">— Aucun —</option>
              {#each $establishments as e}<option value={e.code}>{e.code} · {e.name}</option>{/each}
            </select>
          </label>
        </div>
        <div class="ds-field-row">
          <label class="ds-field">
            <span>Prestataire</span>
            <select bind:value={dossierForm.supplier_id}>
              <option value={null}>— Aucun —</option>
              {#each allSuppliers as s}<option value={s.id}>{s.name}</option>{/each}
            </select>
          </label>
          <label class="ds-field">
            <span>Projet lié</span>
            <select bind:value={dossierForm.project_id}>
              <option value={null}>— Aucun —</option>
              {#each allProjects as p}<option value={p.id}>{p.title}</option>{/each}
            </select>
          </label>
        </div>
        <label class="ds-field">
          <span>Budget estimé (€)</span>
          <input type="number" min="0" step="100" bind:value={dossierForm.estimated_budget} />
        </label>
        <label class="ds-field">
          <span>Notes internes</span>
          <textarea bind:value={dossierForm.notes} rows="2" placeholder="Optionnel — contact référent, conditions particulières…"></textarea>
        </label>
      </div>
      <div class="ds-dialog-footer">
        <button class="ds-btn-secondary" on:click={() => showDossierDialog = false}>Annuler</button>
        <button class="ds-btn-primary" on:click={saveDossier} disabled={saving || !dossierForm.title.trim()}>
          {saving ? 'En cours…' : editingDossierId ? 'Enregistrer' : 'Créer'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ─── ATTACH DIALOG ─── -->
{#if showAttachDialog}
  <div class="ds-overlay" on:mousedown|self={() => showAttachDialog = false}>
    <div class="ds-dialog" style="max-width:560px">
      <div class="ds-dialog-header">
        <h2>Rattacher un document</h2>
        <button class="ds-icon-btn" on:click={() => showAttachDialog = false}>✕</button>
      </div>
      <div class="ds-dialog-body" style="max-height:60vh; overflow:auto">
        {#if attachLoading}
          <p class="ds-section-empty">Chargement…</p>
        {:else if attachableDocs.length === 0}
          <p class="ds-section-empty">Aucun document disponible. Importe d'abord un document via la vue à plat.</p>
        {:else}
          {#each attachableDocs as d}
            {@const dtype = (d.doc_type || '').toUpperCase()}
            {@const dcolor = DOC_TYPE_COLORS[dtype] || '#6B7280'}
            <div class="ds-doc-item ds-doc-item--clickable" on:click={() => attachDoc(d.id)}>
              <div class="ds-doc-badge" style="background:linear-gradient(160deg, {dcolor}, color-mix(in srgb, {dcolor} 70%, black))">
                {dtype.slice(0, 3) || 'DOC'}
              </div>
              <div class="ds-doc-info">
                <div class="ds-doc-title">{d.title}</div>
                <div class="ds-doc-sub">
                  {#if d.internal_ref}<span class="ds-doc-ref">{d.internal_ref}</span>{/if}
                  {#if d.supplier_name}<span>{d.supplier_name}</span>{/if}
                  {#if d.doc_date}<span>{formatDate(d.doc_date)}</span>{/if}
                </div>
              </div>
              <button class="ds-btn-secondary">Rattacher →</button>
            </div>
          {/each}
        {/if}
      </div>
    </div>
  </div>
{/if}

{/if}

<style>
  /* ═════ Color tokens lokal au module ═════ */
  .dossiers-page {
    --ds-bg: var(--bg-base);
    --ds-card: var(--bg-card);
    --ds-border: var(--border-subtle);
    --ds-border-strong: rgba(255,255,255,0.16);
    --ds-text: var(--text-primary);
    --ds-text-heading: var(--text-heading);
    --ds-text-muted: var(--text-muted);
    --ds-text-secondary: var(--text-secondary);
    --ds-primary: var(--primary);
    --ds-success: var(--success);
    --ds-warning: var(--warning, #F59E0B);

    display: flex;
    flex-direction: column;
    height: calc(100vh - var(--header-height));
    overflow: hidden;
    margin: -1.875rem;
  }

  /* ── View switch banner (flat mode) ── */
  .view-switch {
    background: linear-gradient(90deg, rgba(var(--primary-rgb,136,105,225),0.18), transparent);
    border-left: 3px solid var(--primary);
    padding: 12px 18px;
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 16px;
    border-radius: 8px;
  }
  .view-switch__title {
    font-weight: 600;
    color: var(--text-heading);
    font-size: 14px;
  }
  .view-switch__hint {
    color: var(--text-muted);
    font-size: 12px;
    flex: 1;
  }
  .view-switch__btn {
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  /* ── Top bar ── */
  .ds-topbar {
    height: 56px;
    background: var(--ds-card);
    border-bottom: 1px solid var(--ds-border);
    display: flex;
    align-items: center;
    padding: 0 18px;
    gap: 14px;
    flex-shrink: 0;
  }
  .ds-topbar h1 {
    font-size: 15px;
    font-weight: 600;
    color: var(--ds-text-heading);
    margin: 0;
  }
  .ds-crumb { color: var(--ds-text-muted); font-weight: 400; }
  .ds-search {
    flex: 1;
    max-width: 460px;
    position: relative;
  }
  .ds-search input {
    width: 100%;
    background: var(--bg-input, rgba(255,255,255,0.04));
    border: 1px solid var(--ds-border);
    border-radius: 8px;
    padding: 7px 12px 7px 34px;
    color: var(--ds-text);
    font-size: 13px;
    outline: none;
    font-family: inherit;
  }
  .ds-search input:focus { border-color: var(--ds-primary); }
  .ds-search__icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 11px;
    opacity: 0.5;
  }
  .ds-spacer { flex: 1; }
  .ds-toggle {
    display: flex;
    gap: 2px;
    background: var(--bg-input, rgba(255,255,255,0.04));
    border: 1px solid var(--ds-border);
    border-radius: 8px;
    padding: 3px;
  }
  .ds-toggle button {
    background: transparent;
    border: none;
    color: var(--ds-text-secondary);
    padding: 5px 10px;
    border-radius: 5px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
  }
  .ds-toggle button.active {
    background: var(--ds-card);
    color: var(--ds-text-heading);
    box-shadow: 0 1px 2px rgba(0,0,0,0.3);
  }
  .ds-btn-primary {
    background: var(--ds-primary);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    box-shadow: 0 2px 8px rgba(var(--primary-rgb,136,105,225),0.3);
  }
  .ds-btn-primary:hover:not(:disabled) { filter: brightness(1.1); }
  .ds-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  .ds-btn-secondary {
    background: rgba(255,255,255,0.06);
    border: 1px solid var(--ds-border);
    color: var(--ds-text);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
  }
  .ds-btn-secondary:hover { background: rgba(255,255,255,0.1); }

  /* ── Layout ── */
  .ds-layout {
    flex: 1;
    display: grid;
    grid-template-columns: 240px 1fr 480px;
    overflow: hidden;
  }

  /* ── Filters ── */
  .ds-filters {
    background: var(--ds-card);
    border-right: 1px solid var(--ds-border);
    overflow-y: auto;
    padding: 14px;
  }
  .ds-filter-section { margin-bottom: 18px; }
  .ds-filter-section h3 {
    font-size: 10px;
    font-weight: 700;
    color: var(--ds-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
  }
  .ds-filter-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12.5px;
    color: var(--ds-text-secondary);
    transition: background 0.1s, color 0.1s;
  }
  .ds-filter-item:hover { background: rgba(255,255,255,0.04); color: var(--ds-text); }
  .ds-filter-item.active {
    background: rgba(var(--primary-rgb,136,105,225),0.14);
    color: var(--ds-primary);
    font-weight: 500;
  }
  .ds-filter-item--muted { color: var(--ds-text-muted); font-style: italic; cursor: default; }
  .ds-count {
    font-size: 11px;
    color: var(--ds-text-muted);
    background: rgba(255,255,255,0.04);
    padding: 1px 6px;
    border-radius: 8px;
  }
  .ds-filter-item.active .ds-count {
    background: rgba(var(--primary-rgb,136,105,225),0.2);
    color: var(--ds-primary);
  }
  .ds-filter-icon { display: inline-flex; align-items: center; gap: 7px; }
  .ds-filter-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

  /* ── Deal list ── */
  .ds-list {
    overflow-y: auto;
    background: var(--ds-bg);
    padding: 14px;
  }
  .ds-list-header {
    padding: 0 4px 10px;
  }
  .ds-list-header h2 {
    font-size: 13px;
    color: var(--ds-text-secondary);
    font-weight: 500;
    margin: 0;
  }
  .ds-list-header h2 strong { color: var(--ds-text-heading); }
  .ds-empty {
    text-align: center;
    color: var(--ds-text-muted);
    padding: 32px 16px;
    font-size: 13px;
  }

  .ds-card {
    background: var(--ds-card);
    border: 1px solid var(--ds-border);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .ds-card:hover { border-color: var(--ds-border-strong); }
  .ds-card.selected {
    border-color: var(--ds-primary);
    box-shadow: 0 0 0 1px var(--ds-primary), 0 4px 14px rgba(var(--primary-rgb,136,105,225),0.2);
  }

  .ds-card__top {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    margin-bottom: 10px;
  }
  .ds-supplier-avatar {
    width: 34px;
    height: 34px;
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-weight: 700;
    font-size: 12px;
    flex-shrink: 0;
  }
  .ds-supplier-avatar--xs {
    width: 18px;
    height: 18px;
    font-size: 9px;
    border-radius: 4px;
  }
  .ds-card__main {
    flex: 1;
    min-width: 0;
  }
  .ds-card__title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--ds-text-heading);
    margin-bottom: 3px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ds-card__meta {
    font-size: 11.5px;
    color: var(--ds-text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .ds-card__meta .dot { color: var(--ds-text-muted); opacity: 0.6; }
  .ds-card__meta .muted { color: var(--ds-text-muted); font-style: italic; }
  .ds-card__project { color: var(--ds-text-secondary); }

  .ds-status-pill {
    padding: 3px 9px;
    border-radius: 11px;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.02em;
    flex-shrink: 0;
    white-space: nowrap;
  }

  .ds-timeline-mini {
    display: flex;
    align-items: center;
    gap: 4px;
    margin: 8px 0;
  }
  .ds-tl-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid var(--ds-text-muted);
    background: transparent;
    flex-shrink: 0;
    box-sizing: border-box;
  }
  .ds-tl-dot.done {
    background: var(--c);
    border-color: var(--c);
  }
  .ds-tl-line {
    flex: 1;
    height: 2px;
    background: var(--ds-border);
    border-radius: 1px;
  }
  .ds-tl-line.done { background: var(--ds-text-muted); }

  .ds-amounts {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--ds-border);
  }
  .ds-amount {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .ds-amount__label {
    font-size: 9.5px;
    color: var(--ds-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ds-amount__value {
    font-size: 13px;
    font-weight: 700;
    color: var(--ds-text-heading);
    font-variant-numeric: tabular-nums;
  }
  .ds-amount__value.muted { color: var(--ds-text-muted); }

  .ds-card__footer {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
    font-size: 11px;
    color: var(--ds-text-muted);
  }
  .ds-card__footer .muted { color: var(--ds-text-muted); }

  /* ── Detail panel ── */
  .ds-detail {
    background: var(--ds-card);
    border-left: 1px solid var(--ds-border);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .ds-detail__empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--ds-text-muted);
    text-align: center;
    padding: 40px;
    gap: 12px;
  }
  .ds-detail__empty-icon { font-size: 40px; opacity: 0.4; }

  .ds-detail-header {
    padding: 16px 18px 12px;
    border-bottom: 1px solid var(--ds-border);
  }
  .ds-detail-header__top {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    margin-bottom: 10px;
  }
  .ds-detail-header h2 {
    font-size: 17px;
    color: var(--ds-text-heading);
    font-weight: 600;
    line-height: 1.3;
    margin: 0;
    flex: 1;
  }
  .ds-icon-btn {
    background: transparent;
    border: 1px solid var(--ds-border);
    color: var(--ds-text-secondary);
    padding: 5px 8px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    font-family: inherit;
  }
  .ds-icon-btn:hover { background: rgba(255,255,255,0.06); color: var(--ds-text); }

  .ds-detail-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
  }
  .ds-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255,255,255,0.04);
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 11.5px;
    color: var(--ds-text-secondary);
  }

  .ds-status-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  .ds-status-label {
    font-size: 11px;
    color: var(--ds-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  .ds-status-select {
    background: transparent;
    border: 1.5px solid;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .ds-description {
    font-size: 13px;
    color: var(--ds-text-secondary);
    line-height: 1.5;
    margin: 8px 0 0;
  }

  .ds-detail-section {
    padding: 14px 18px;
    border-bottom: 1px solid var(--ds-border);
  }
  .ds-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }
  .ds-section-header h3 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ds-text-muted);
    margin: 0;
    font-weight: 700;
  }
  .ds-section-count {
    background: rgba(255,255,255,0.06);
    padding: 1px 6px;
    border-radius: 8px;
    font-size: 10px;
    color: var(--ds-text-secondary);
    margin-left: 4px;
  }
  .ds-section-empty {
    color: var(--ds-text-muted);
    font-size: 12.5px;
    margin: 6px 0;
    font-style: italic;
  }

  /* Doc item */
  .ds-doc-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    background: var(--ds-bg);
    border: 1px solid var(--ds-border);
    border-radius: 8px;
    margin-bottom: 6px;
  }
  .ds-doc-item--clickable { cursor: pointer; transition: border-color 0.15s, background 0.15s; }
  .ds-doc-item--clickable:hover { border-color: var(--ds-primary); background: rgba(var(--primary-rgb,136,105,225),0.04); }
  .ds-doc-badge {
    width: 38px;
    height: 44px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    flex-shrink: 0;
    position: relative;
  }
  .ds-doc-acompte {
    position: absolute;
    top: -4px;
    right: -4px;
    background: var(--ds-warning);
    color: #fff;
    border-radius: 50%;
    width: 16px;
    height: 16px;
    font-size: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid var(--ds-card);
  }
  .ds-doc-info { flex: 1; min-width: 0; }
  .ds-doc-title {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--ds-text-heading);
    margin-bottom: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ds-doc-sub {
    font-size: 10.5px;
    color: var(--ds-text-muted);
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .ds-doc-ref {
    font-family: 'JetBrains Mono', 'Cascadia Code', monospace;
    font-size: 10px;
    background: rgba(255,255,255,0.04);
    padding: 1px 5px;
    border-radius: 3px;
  }
  .ds-doc-amount { text-align: right; flex-shrink: 0; }
  .ds-doc-amount__main {
    font-size: 13px;
    font-weight: 700;
    color: var(--ds-text-heading);
    font-variant-numeric: tabular-nums;
  }

  /* Inline amount edit on each doc row — two narrow fields side by side. */
  .ds-doc-amount-edit {
    display: flex;
    gap: 8px;
    margin-top: 4px;
    align-items: center;
  }
  .ds-mini-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 10px;
    color: var(--ds-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ds-amount-input {
    width: 80px;
    background: var(--ds-bg);
    border: 1px solid var(--ds-border);
    border-radius: 4px;
    padding: 3px 7px;
    color: var(--ds-text);
    font-size: 12px;
    font-family: inherit;
    outline: none;
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  .ds-amount-input:focus { border-color: var(--ds-primary); }

  /* Budget block */
  .ds-budget {
    background: var(--ds-bg);
    border: 1px solid var(--ds-border);
    border-radius: 8px;
    padding: 10px 12px;
  }
  .ds-budget-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 12.5px;
    color: var(--ds-text-secondary);
  }
  .ds-budget-val {
    font-weight: 700;
    color: var(--ds-text-heading);
    font-variant-numeric: tabular-nums;
  }

  /* Activity */
  .ds-activity-item {
    display: flex;
    gap: 10px;
    padding: 6px 0;
  }
  .ds-activity-dot {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(255,255,255,0.05);
    border: 1.5px solid var(--ds-border);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    flex-shrink: 0;
  }
  .ds-activity-dot--status { color: var(--ds-primary); }
  .ds-activity-dot--doc    { color: var(--info, #3B82F6); }
  .ds-activity-dot--delivery { color: var(--ds-success); }
  .ds-activity-dot--note   { color: var(--ds-warning); }
  .ds-activity-body { flex: 1; }
  .ds-activity-text {
    font-size: 12px;
    color: var(--ds-text);
    line-height: 1.4;
    white-space: pre-line;
  }
  .ds-activity-meta {
    font-size: 10.5px;
    color: var(--ds-text-muted);
    margin-top: 2px;
  }

  /* ── Dialog ── */
  .ds-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.55);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
  }
  .ds-dialog {
    background: var(--ds-card);
    border: 1px solid var(--ds-border);
    border-radius: 12px;
    width: min(480px, 92vw);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0,0,0,0.45);
  }
  .ds-dialog-header {
    padding: 14px 18px;
    border-bottom: 1px solid var(--ds-border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .ds-dialog-header h2 {
    margin: 0;
    font-size: 15px;
    color: var(--ds-text-heading);
    font-weight: 600;
  }
  .ds-dialog-body {
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
  }
  .ds-dialog-footer {
    padding: 12px 18px;
    border-top: 1px solid var(--ds-border);
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .ds-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .ds-field span {
    font-size: 11px;
    color: var(--ds-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
  }
  .ds-field input,
  .ds-field textarea,
  .ds-field select {
    background: var(--bg-input, rgba(255,255,255,0.04));
    border: 1px solid var(--ds-border);
    border-radius: 6px;
    padding: 7px 10px;
    color: var(--ds-text);
    font-size: 13px;
    font-family: inherit;
    outline: none;
  }
  .ds-field input:focus,
  .ds-field textarea:focus,
  .ds-field select:focus { border-color: var(--ds-primary); }
  .ds-field textarea { resize: vertical; min-height: 56px; }
  .ds-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
</style>
