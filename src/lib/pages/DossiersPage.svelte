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

  // ── State ─────────────────────────────────────────────────
  // v7.0.8 — flat view (DocumentsPage) supprimée : la vue Dossiers couvre
  // maintenant tous les besoins (import, édition, suppression, preview…).

  let dossiers = [];
  let selectedDossierId = null;
  let selectedDossier = null;
  let loading = true;
  let stats = { total: 0, per_status: {}, smart: {} };

  // Filters + sort
  let filterStatus = '';
  let filterSupplier = null;
  let filterSite = '';
  let filterPeriod = 'all';
  let sortBy = 'recent';
  let searchQuery = '';
  let searchTimer;

  const SORT_OPTIONS = [
    { value: 'recent',     label: 'Modifié récemment' },
    { value: 'recent_doc', label: 'Document le plus récent' },
    { value: 'oldest_doc', label: 'Document le plus ancien' },
    { value: 'title',      label: 'Alphabétique (A→Z)' },
  ];

  // Period filter — computed dynamically so the year list reflects "now".
  $: PERIODS = (() => {
    const year = new Date().getFullYear();
    return [
      { value: 'all',       label: 'Toutes périodes' },
      { value: '30d',       label: '30 derniers jours' },
      { value: '90d',       label: '90 derniers jours' },
      { value: 'this_year', label: `Cette année (${year})` },
      { value: String(year - 1), label: String(year - 1) },
      { value: String(year - 2), label: String(year - 2) },
    ];
  })();

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

  // Custom status dropdown state (replaces native <select> which had
  // rendering quirks in light theme).
  let statusMenuOpen = false;

  // Quick-edit supplier inline in the detail header (no dialog needed).
  let supplierMenuOpen = false;

  // Import dialog : creates a new document and auto-attaches it to the
  // currently-selected dossier in one shot.
  let showImportDialog = false;
  let importing = false;
  let importForm = blankImportForm();
  let importFile = null;
  let importFileInput;

  function blankImportForm() {
    return {
      doc_type: 'DEVIS',
      title: '',
      doc_date: '',
      reference: '',
      notes: '',
      is_acompte: false,
    };
  }

  // Preview modal — iframe pointing at /api/documents/{id}/preview
  let previewDoc = null;

  // v7.7.0 — vue cards / compacte (table dense). Persistée localement.
  let viewMode = localStorage.getItem('dossiers.viewMode') || 'cards';
  $: try { localStorage.setItem('dossiers.viewMode', viewMode); } catch {}

  // v7.7.0 — badge « À relancer » : next_action_date dépassée sur un
  // dossier encore actif.
  const _todayIso = new Date().toISOString().slice(0, 10);
  function relanceDays(d) {
    if (!d.next_action_date || d.status === 'livre' || d.status === 'archive') return null;
    if (d.next_action_date > _todayIso) return null;
    const days = Math.floor((new Date(_todayIso) - new Date(d.next_action_date)) / 86400000);
    return days;
  }

  // v7.7.0 — écart facture vs engagé (>5 % => signalé en rouge sur la card).
  function factureEcart(d) {
    const bpa = d.summary?.bpa_total || 0;
    const fact = d.summary?.facture_total || 0;
    if (bpa > 0 && fact > bpa * 1.05) {
      return Math.round(((fact - bpa) / bpa) * 100);
    }
    return null;
  }

  // Doc edit dialog (replaces what was only doable in the old flat view).
  let editingDoc = null;  // null = closed; doc object when open
  let editDocForm = {
    title: '', doc_type: 'DEVIS', doc_date: '', reference: '',
    notes: '', supplier_id: null, is_acompte: false,
  };
  let savingDoc = false;

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
      if (filterPeriod && filterPeriod !== 'all') params.set('period', filterPeriod);
      if (sortBy && sortBy !== 'recent') params.set('sort', sortBy);
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

  // Reactive: reload when filters/sort change. Search is debounced.
  $: filterStatus, filterSupplier, filterSite, filterPeriod, sortBy, loadDossiers();

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
    // Type-safe coercion : null OR number for IDs, raw value for strings.
    let cleanValue = value;
    if (field === 'supplier_id' || field === 'project_id') {
      cleanValue = value == null || value === '' ? null : Number(value);
    }
    const payload = { [field]: cleanValue };
    console.log('[updateField] PUT payload =', payload);
    try {
      const result = await api.put(`/api/dossiers/${selectedDossier.id}`, payload);
      console.log('[updateField] response =', result);
      // Diagnostic : if backend returns a different value than what we sent
      // for an ID field, surface it loudly so we don't silently lose data.
      if ((field === 'supplier_id' || field === 'project_id') && result[field] !== cleanValue) {
        toastError(`[BUG] envoyé ${field}=${cleanValue}, reçu ${result[field]} — vérifie les logs`);
      }
      selectedDossier = result;
      await loadDossiers();
    } catch (e) {
      toastError(`Échec mise à jour ${field} : ${e.message || e}`);
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
      // Show only docs not already in this dossier AND not orphans on disk.
      // Backend has no filter for either yet, so we drop them client-side.
      const attachedIds = new Set((selectedDossier?.documents || []).map(d => d.id));
      attachableDocs = (allDocs || []).filter(d => !attachedIds.has(d.id) && !d.file_missing);
    } catch {
      attachableDocs = [];
    } finally {
      attachLoading = false;
    }
  }

  async function cleanupOrphans() {
    if (!confirm("Nettoyer les documents orphelins ?\n\nCela supprime les entrées en base dont le fichier n'existe plus sur le disque. Aucun fichier réel n'est supprimé (ils sont déjà absents). Action irréversible côté base.")) return;
    try {
      const result = await api.post('/api/documents/cleanup-orphans');
      if (result.removed > 0) {
        success(`${result.removed} document${result.removed > 1 ? 's' : ''} orphelin${result.removed > 1 ? 's' : ''} nettoyé${result.removed > 1 ? 's' : ''}`);
        // Refresh the Rattacher dialog list if it's open.
        if (showAttachDialog) await openAttachDialog();
      } else {
        success('Aucun orphelin à nettoyer — tout est propre');
      }
    } catch (e) {
      toastError(`Erreur nettoyage : ${e.message || e}`);
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

  // ── Document import (creates + attaches to current dossier) ──────
  function openImportDialog() {
    if (!selectedDossier) return;
    importForm = blankImportForm();
    importFile = null;
    showImportDialog = true;
  }

  // Smart auto-rename : when the user picks a file (and hasn't manually
  // typed a title), suggest a title like "Devis Ageona - 15/04/2026".
  // Triggered from the file picker + whenever the type/date changes.
  function buildAutoTitle() {
    if (!selectedDossier) return '';
    const typeLabels = {
      DEVIS: 'Devis',
      PROPOSITION: 'Proposition',
      BPA: 'BPA',
      BON: 'Bon',
      CONTRAT: 'Contrat',
      FACTURE: 'Facture',
      RAPPORT: 'Rapport',
      AUTRE: 'Document',
    };
    const typeLabel = typeLabels[importForm.doc_type] || 'Document';
    const supplierName = selectedDossier.supplier?.name || '';
    const date = importForm.doc_date ? formatDate(importForm.doc_date) : '';
    const parts = [typeLabel];
    if (supplierName) parts.push(supplierName);
    let title = parts.join(' ');
    if (date) title += ` - ${date}`;
    return title;
  }

  function onImportFilePicked(e) {
    const f = e.target?.files?.[0];
    if (!f) return;
    importFile = f;
    // Try to auto-detect the doc_type from the filename + auto-fill title.
    const lower = f.name.toLowerCase();
    if (/(devis|estimate|quote)/i.test(lower)) importForm.doc_type = 'DEVIS';
    else if (/(bpa|bon[\s_-]?pour[\s_-]?accord)/i.test(lower)) importForm.doc_type = 'BPA';
    else if (/(facture|invoice|fv\d+|fac\d+)/i.test(lower)) importForm.doc_type = 'FACTURE';
    else if (/(contrat|contract)/i.test(lower)) importForm.doc_type = 'CONTRAT';
    else if (/(rapport|report)/i.test(lower)) importForm.doc_type = 'RAPPORT';

    // Try to extract a date from the filename (YYYY-MM-DD or DD-MM-YYYY).
    let m = lower.match(/(\d{4})[-_](\d{2})[-_](\d{2})/);
    if (m) importForm.doc_date = `${m[1]}-${m[2]}-${m[3]}`;
    else {
      m = lower.match(/(\d{2})[-_](\d{2})[-_](\d{4})/);
      if (m) importForm.doc_date = `${m[3]}-${m[2]}-${m[1]}`;
    }

    // Generate the title if the user hasn't typed one.
    if (!importForm.title.trim()) {
      importForm.title = buildAutoTitle();
    }
  }

  // Re-suggest the title whenever the user changes type/date and hasn't
  // manually overridden it. Simple heuristic : if the current title was
  // generated by us, regenerate it ; otherwise leave it alone.
  let _lastAutoTitle = '';
  $: if (showImportDialog) {
    const suggested = buildAutoTitle();
    if (!importForm.title.trim() || importForm.title === _lastAutoTitle) {
      importForm.title = suggested;
      _lastAutoTitle = suggested;
    }
  }

  async function submitImport() {
    if (!selectedDossier || !importFile || !importForm.title.trim()) return;
    importing = true;
    try {
      const fd = new FormData();
      fd.append('file', importFile);
      fd.append('title', importForm.title);
      fd.append('doc_type', importForm.doc_type);
      // v7.0.8 : envoie supplier_id directement (deterministe). Fallback
      // sur le nom uniquement si le dossier n'a pas d'ID de presta resolu.
      if (selectedDossier.supplier_id) {
        fd.append('supplier_id', String(selectedDossier.supplier_id));
      } else if (selectedDossier.supplier?.name) {
        fd.append('supplier', selectedDossier.supplier.name);
      }
      fd.append('doc_date', importForm.doc_date || '');
      fd.append('reference', importForm.reference || '');
      fd.append('notes', importForm.notes || '');
      fd.append('is_acompte', importForm.is_acompte ? '1' : '0');

      const res = await fetch(`${API_BASE}/api/documents/upload`, {
        method: 'POST',
        body: fd,
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(`HTTP ${res.status}: ${err}`);
      }
      const newDoc = await res.json();

      // Now attach it to the current dossier.
      await api.post(`/api/dossiers/${selectedDossier.id}/attach`, {
        document_id: newDoc.id,
      });

      // Refresh the dossier to show the new doc.
      selectedDossier = await api.get(`/api/dossiers/${selectedDossier.id}`);
      await loadDossiers();
      showImportDialog = false;
      importForm = blankImportForm();
      importFile = null;
      success('Document importé et rattaché');
    } catch (e) {
      toastError(`Erreur import : ${e.message || e}`);
    } finally {
      importing = false;
    }
  }

  // ── Document preview (eye icon) ──────────────────────────
  function openPreview(doc) {
    previewDoc = doc;
  }
  function closePreview() {
    previewDoc = null;
  }

  // ── Document edit (✏️) — replaces what was doable only in the flat view.
  function openEditDoc(doc) {
    editingDoc = doc;
    editDocForm = {
      title: doc.title || '',
      doc_type: (doc.doc_type || 'AUTRE').toUpperCase(),
      doc_date: doc.doc_date || '',
      reference: doc.reference || '',
      notes: doc.notes || '',
      supplier_id: doc.supplier_id || selectedDossier?.supplier_id || null,
      is_acompte: !!doc.is_acompte,
    };
  }

  async function saveDocEdit() {
    if (!editingDoc || !editDocForm.title.trim()) return;
    savingDoc = true;
    try {
      const payload = {
        title: editDocForm.title,
        doc_type: editDocForm.doc_type,
        doc_date: editDocForm.doc_date || null,
        reference: editDocForm.reference || '',
        notes: editDocForm.notes || '',
        supplier_id: editDocForm.supplier_id ? Number(editDocForm.supplier_id) : null,
        is_acompte: editDocForm.is_acompte,
        // Keep existing tags untouched. Tags weren't exposed in the dossier
        // view yet; if a doc had tags from the old flat view they survive.
        tags: editingDoc.tags || '',
      };
      await api.put(`/api/documents/${editingDoc.id}`, payload);
      // Refresh the current dossier so the doc list reflects the edit.
      selectedDossier = await api.get(`/api/dossiers/${selectedDossier.id}`);
      await loadDossiers();
      editingDoc = null;
      success('Document modifié');
    } catch (e) {
      toastError(`Erreur : ${e.message || e}`);
    } finally {
      savingDoc = false;
    }
  }

  // ── Document hard-delete (🗑) — supprime DEFINITIVEMENT le doc (DB + fichier).
  async function hardDeleteDoc(doc) {
    if (!confirm(
      `SUPPRIMER DÉFINITIVEMENT "${doc.title}" ?\n\n` +
      `Le document sera retiré de la base ET son fichier physique sera marqué pour suppression.\n` +
      `Cette action est IRRÉVERSIBLE.\n\n` +
      `(Pour simplement détacher du dossier sans supprimer, utilise plutôt ✕)`
    )) return;
    try {
      await api.delete(`/api/documents/${doc.id}`);
      // Reload the dossier (the doc disappears) + the dossier list (counts update).
      selectedDossier = await api.get(`/api/dossiers/${selectedDossier.id}`);
      await loadDossiers();
      success('Document supprimé définitivement');
    } catch (e) {
      toastError(`Erreur suppression : ${e.message || e}`);
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

  // URL of a supplier's logo. Returns null when the supplier has no uploaded
  // logo; callers fall back to the colored initials avatar in that case.
  function supplierLogoUrl(s) {
    if (!s || !s.id || !s.has_logo) return null;
    return `${API_BASE}/api/suppliers/${s.id}/logo`;
  }
</script>

<!-- ─── DOSSIERS VIEW — 3 columns (vue unique depuis v7.0.8) ─── -->
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
    <label class="ds-sort">
      <span class="ds-sort-label">Trier</span>
      <select bind:value={sortBy}>
        {#each SORT_OPTIONS as opt}<option value={opt.value}>{opt.label}</option>{/each}
      </select>
    </label>
    <div class="ds-view-toggle">
      <button class:active={viewMode === 'cards'} on:click={() => viewMode = 'cards'} title="Vue cards">▤</button>
      <button class:active={viewMode === 'compact'} on:click={() => viewMode = 'compact'} title="Vue compacte">☰</button>
    </div>
    <button class="ds-btn-primary" on:click={openCreateDialog}>
      + Nouveau dossier
    </button>
  </header>

  <!-- ─── v7.7.0 — PIPELINE BAR ───
       L'état d'avancement de tous les dossiers, toujours visible.
       Chaque segment est cliquable et filtre la liste (re-clic = reset).
       Remplace l'ancien groupe de filtres « État du dossier ». -->
  <div class="ds-pipeline-wrap">
    <div class="ds-pipeline">
      {#each STATUSES as s}
        <div
          class="ds-pl-seg"
          class:active={filterStatus === s.value}
          style="--seg-color:{s.color}"
          on:click={() => filterStatus = (filterStatus === s.value ? '' : s.value)}
          title={s.hint}
        >
          <div class="ds-pl-count">{stats.per_status?.[s.value] || 0}</div>
          <div class="ds-pl-label">{s.shortLabel}</div>
        </div>
      {/each}
    </div>
    <div class="ds-pl-kpis">
      <div class="ds-plk">
        <div class="ds-plk-v">{fmtEur(stats.finance?.engaged_ytd)}</div>
        <div class="ds-plk-k">Engagé {stats.finance?.year || ''}</div>
      </div>
      <div class="ds-plk">
        <div class="ds-plk-v ds-plk-v--green">{fmtEur(stats.finance?.factured_ytd)}</div>
        <div class="ds-plk-k">Facturé</div>
      </div>
    </div>
  </div>

  <div class="ds-layout">

    <!-- ─── FILTERS (l'état a déménagé dans la pipeline bar) ─── -->
    <aside class="ds-filters">
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

      <div class="ds-filter-section">
        <h3>Période</h3>
        {#each PERIODS as p}
          <div class="ds-filter-item" class:active={filterPeriod === p.value} on:click={() => filterPeriod = p.value}>
            <span class="ds-filter-icon">📅 {p.label}</span>
          </div>
        {/each}
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
      {:else if viewMode === 'compact'}
        <!-- ─── v7.7.0 — VUE COMPACTE (table dense) ─── -->
        <table class="ds-ctable">
          <thead>
            <tr>
              <th>Statut</th>
              <th>Dossier</th>
              <th>Étab</th>
              <th class="r">Devis</th>
              <th class="r">BPA</th>
              <th class="r">Facturé</th>
              <th class="r">Docs</th>
              <th class="r">Date</th>
            </tr>
          </thead>
          <tbody>
            {#each dossiers as d (d.id)}
              {@const status = statusInfo(d.status)}
              {@const ecart = factureEcart(d)}
              <tr class:selected={selectedDossierId === d.id} on:click={() => selectDossier(d.id)}>
                <td><span class="ds-status-pill" style="background:{status.color}22;color:{status.color}">{status.shortLabel}</span></td>
                <td class="t-title">{relanceDays(d) !== null ? '⏰ ' : ''}{d.title}</td>
                <td>{d.site || '—'}</td>
                <td class="r t-amt" class:t-dim={!d.summary?.devis_total}>{fmtEur(d.summary?.devis_total)}</td>
                <td class="r t-amt" class:t-dim={!d.summary?.bpa_total}>{fmtEur(d.summary?.bpa_total)}</td>
                <td class="r t-amt" class:t-dim={!d.summary?.facture_total} style:color={ecart !== null ? 'var(--danger)' : ''}>{fmtEur(d.summary?.facture_total)}</td>
                <td class="r">{d.summary?.doc_count || 0}</td>
                <td class="r">{d.last_doc_date ? formatDate(d.last_doc_date) : formatRelative(d.updated_at)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {:else}
        {#each dossiers as d (d.id)}
          {@const status = statusInfo(d.status)}
          {@const rDays = relanceDays(d)}
          {@const ecart = factureEcart(d)}
          <article
            class="ds-card"
            class:selected={selectedDossierId === d.id}
            style="--st-color:{status.color}"
            on:click={() => selectDossier(d.id)}
          >
            <div class="ds-card__top">
              {#if d.supplier && supplierLogoUrl(d.supplier)}
                <img class="ds-supplier-avatar ds-supplier-avatar--img" src={supplierLogoUrl(d.supplier)} alt={d.supplier.name} />
              {:else}
                <div class="ds-supplier-avatar" style="background:{d.supplier?.color || '#6B7280'}">
                  {d.supplier ? supplierInitials(d.supplier) : '?'}
                </div>
              {/if}
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
                  <span class="dot">·</span>
                  <span>{d.summary?.doc_count || 0} doc{(d.summary?.doc_count || 0) > 1 ? 's' : ''}</span>
                </div>
              </div>
              {#if rDays !== null}
                <span class="ds-relance-pill" title={d.next_action_label || 'Action prévue dépassée'}>
                  ⏰ À relancer{rDays > 0 ? ` · ${rDays} j` : ''}
                </span>
              {/if}
              <span class="ds-status-pill" style="background:{status.color}22;color:{status.color}">
                {status.shortLabel}
              </span>
            </div>

            <!-- v7.7.0 — stepper fusionné : étapes + montants en une ligne -->
            <div class="ds-steps">
              <div class="ds-step" class:done={d.summary?.devis_total > 0}>
                <div class="ds-step-head">
                  <span class="ds-step-dot">{d.summary?.devis_total > 0 ? '✓' : ''}</span>
                  <span class="ds-step-label">Devis</span>
                </div>
                <div class="ds-step-amt">{fmtEur(d.summary?.devis_total)}</div>
              </div>
              <div class="ds-step-conn" class:done={d.summary?.bpa_total > 0}></div>
              <div class="ds-step" class:done={d.summary?.bpa_total > 0}>
                <div class="ds-step-head">
                  <span class="ds-step-dot">{d.summary?.bpa_total > 0 ? '✓' : ''}</span>
                  <span class="ds-step-label">BPA</span>
                </div>
                <div class="ds-step-amt">{fmtEur(d.summary?.bpa_total)}</div>
              </div>
              <div class="ds-step-conn" class:done={d.summary?.facture_total > 0}></div>
              <div class="ds-step" class:done={d.summary?.facture_total > 0}>
                <div class="ds-step-head">
                  <span class="ds-step-dot">{d.summary?.facture_total > 0 ? '✓' : ''}</span>
                  <span class="ds-step-label">Facture</span>
                </div>
                <div class="ds-step-amt" style:color={ecart !== null ? 'var(--danger)' : ''}>
                  {fmtEur(d.summary?.facture_total)}{#if ecart !== null}<small class="ds-ecart">+{ecart} %</small>{/if}
                </div>
              </div>
              <div class="ds-step-date">
                {#if d.last_doc_date}
                  <span title={`Document le plus récent : ${formatDate(d.last_doc_date)}`}>📅 {formatDate(d.last_doc_date)}</span>
                {:else}
                  <span title={`Modifié ${formatDate(d.updated_at)}`}>{formatRelative(d.updated_at)}</span>
                {/if}
              </div>
            </div>
          </article>
        {/each}
      {/if}
    </main>

    <!-- ─── DETAIL PANEL ─── -->
    <aside class="ds-detail">
      {#if !selectedDossier}
        <!-- ─── v7.7.0 — TABLEAU DE BORD (état de repos) ───
             Remplace le « Sélectionne un dossier » vide. -->
        <div class="ds-dash">
          <div class="ds-dash-card">
            <div class="ds-dash-title">Vue d'ensemble {stats.finance?.year || ''}</div>
            <div class="ds-dash-stats">
              <div class="ds-ds">
                <div class="ds-ds-v">{fmtEur(stats.finance?.engaged_ytd)}</div>
                <div class="ds-ds-k">Engagé (BPA)</div>
              </div>
              <div class="ds-ds">
                <div class="ds-ds-v ds-ds-v--green">{fmtEur(stats.finance?.factured_ytd)}</div>
                <div class="ds-ds-k">Facturé</div>
              </div>
              <div class="ds-ds ds-ds--full">
                <div class="ds-ds-v ds-ds-v--amber">{fmtEur(Math.max((stats.finance?.engaged_ytd || 0) - (stats.finance?.factured_ytd || 0), 0))}</div>
                <div class="ds-ds-k">En attente de facturation</div>
              </div>
            </div>
          </div>

          {#if stats.top_suppliers?.length}
            {@const maxEngaged = stats.top_suppliers[0]?.engaged || 1}
            <div class="ds-dash-card">
              <div class="ds-dash-title">Top prestataires (engagé)</div>
              {#each stats.top_suppliers as tp}
                <div class="ds-tp-row" on:click={() => filterSupplier = tp.id}>
                  <span class="ds-tp-name">{tp.name}</span>
                  <span class="ds-tp-bar-wrap"><span class="ds-tp-bar" style="width:{Math.max(Math.round((tp.engaged / maxEngaged) * 100), 3)}%"></span></span>
                  <span class="ds-tp-amt">{fmtEur(tp.engaged)}</span>
                </div>
              {/each}
            </div>
          {/if}

          {#if stats.relance_list?.length}
            <div class="ds-dash-card">
              <div class="ds-dash-title">⏰ À relancer ({stats.relance_list.length})</div>
              {#each stats.relance_list as rl}
                <div class="ds-rl-item" on:click={() => selectDossier(rl.id)}>
                  <div class="ds-rl-body">
                    <div class="ds-rl-t">{rl.title}</div>
                    <div class="ds-rl-s">{rl.reason} — {rl.days} j</div>
                  </div>
                  <span class="ds-rl-arrow">→</span>
                </div>
              {/each}
            </div>
          {/if}

          <p class="ds-dash-hint">Clique sur un dossier pour voir son détail.</p>
        </div>
      {:else}
        {@const status = statusInfo(selectedDossier.status)}

        <header class="ds-detail-header">
          <div class="ds-detail-header__top">
            <h2>{selectedDossier.title}</h2>
            <button class="ds-icon-btn" on:click={openEditDialog} title="Éditer le dossier">✏️</button>
            <button class="ds-icon-btn" on:click={deleteDossier} title="Supprimer le dossier">🗑</button>
          </div>

          <!-- Quick-edit row : the user can change supplier and status WITHOUT
               opening the edit dialog. Each change is a single-field PATCH
               that returns the fresh dossier. Designed to avoid the v7.0.x
               supplier-save bug entirely : no shared form state. -->
          <div class="ds-quick-edits">
            <!-- STATUS — custom dropdown (no native <select>, fully theme-aware) -->
            <div class="ds-quick-field">
              <span class="ds-quick-label">Statut</span>
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div class="ds-quick-pill" on:click={() => statusMenuOpen = !statusMenuOpen}>
                <span class="ds-quick-dot" style="background:{status.color}"></span>
                <span class="ds-quick-text">{status.label}</span>
                <span class="ds-quick-caret">▾</span>
              </div>
              {#if statusMenuOpen}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div class="ds-quick-backdrop" on:click={() => statusMenuOpen = false}></div>
                <div class="ds-quick-menu">
                  {#each STATUSES as s}
                    <div
                      class="ds-quick-menu-item"
                      class:active={selectedDossier.status === s.value}
                      on:click={() => { statusMenuOpen = false; changeStatus(s.value); }}
                    >
                      <span class="ds-quick-dot" style="background:{s.color}"></span>
                      <span>{s.label}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>

            <!-- SUPPLIER — same custom-dropdown pattern, PATCH on selection. -->
            <div class="ds-quick-field">
              <span class="ds-quick-label">Prestataire</span>
              <!-- svelte-ignore a11y_click_events_have_key_events -->
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div class="ds-quick-pill" on:click={() => supplierMenuOpen = !supplierMenuOpen}
                   class:ds-quick-pill--empty={!selectedDossier.supplier}>
                {#if selectedDossier.supplier}
                  {#if supplierLogoUrl(selectedDossier.supplier)}
                    <img class="ds-supplier-avatar ds-supplier-avatar--xs ds-supplier-avatar--img" src={supplierLogoUrl(selectedDossier.supplier)} alt={selectedDossier.supplier.name} />
                  {:else}
                    <span class="ds-supplier-avatar ds-supplier-avatar--xs" style="background:{selectedDossier.supplier.color}">
                      {supplierInitials(selectedDossier.supplier)}
                    </span>
                  {/if}
                  <span class="ds-quick-text">{selectedDossier.supplier.name}</span>
                {:else}
                  <span class="ds-quick-text" style="color:var(--warning, #F59E0B)">⚠ Aucun — cliquer</span>
                {/if}
                <span class="ds-quick-caret">▾</span>
              </div>
              {#if supplierMenuOpen}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div class="ds-quick-backdrop" on:click={() => supplierMenuOpen = false}></div>
                <div class="ds-quick-menu ds-quick-menu--scroll">
                  <div
                    class="ds-quick-menu-item"
                    class:active={!selectedDossier.supplier_id}
                    on:click={() => { supplierMenuOpen = false; updateField('supplier_id', null); }}
                  >
                    <span class="ds-quick-dot" style="background:#94A3B8"></span>
                    <span>— Aucun —</span>
                  </div>
                  {#each allSuppliers as s}
                    {@const hasLogo = !!s.logo_path}
                    <div
                      class="ds-quick-menu-item"
                      class:active={selectedDossier.supplier_id === s.id}
                      on:click={() => { supplierMenuOpen = false; updateField('supplier_id', s.id); }}
                    >
                      {#if hasLogo}
                        <img class="ds-supplier-avatar ds-supplier-avatar--xs ds-supplier-avatar--img" src={`${API_BASE}/api/suppliers/${s.id}/logo`} alt={s.name} />
                      {:else}
                        <span class="ds-supplier-avatar ds-supplier-avatar--xs" style="background:{s.color || '#6C63FF'}">
                          {supplierInitials({name: s.name})}
                        </span>
                      {/if}
                      <span>{s.name}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>

          <!-- Secondary meta (site, projet) — read-only chips, edited via the full dialog -->
          <div class="ds-detail-meta">
            {#if selectedDossier.site}
              <span class="ds-chip"><EstablishmentBadge code={selectedDossier.site} size="xs" showLabel={true} /></span>
            {/if}
            {#if selectedDossier.project}
              <span class="ds-chip">🎯 {selectedDossier.project.title}</span>
            {/if}
          </div>

          {#if selectedDossier.description}
            <p class="ds-description">{selectedDossier.description}</p>
          {/if}
        </header>

        <!-- Documents block -->
        <section class="ds-detail-section">
          <div class="ds-section-header">
            <h3>Documents <span class="ds-section-count">{selectedDossier.documents?.length || 0}</span></h3>
            <div style="display:flex; gap:6px">
              <button class="ds-btn-secondary" on:click={openImportDialog}>+ Importer</button>
              <button class="ds-btn-secondary" on:click={openAttachDialog}>+ Rattacher</button>
            </div>
          </div>

          {#if (selectedDossier.documents || []).length === 0}
            <p class="ds-section-empty">Aucun document rattaché.</p>
          {:else}
            {#each selectedDossier.documents as doc}
              {@const dtype = (doc.doc_type || '').toUpperCase()}
              {@const dcolor = DOC_TYPE_COLORS[dtype] || '#6B7280'}
              <!-- "Validé" only makes sense for DEVIS : un devis propose un prix
                   qui peut être négocié. Le BPA EST déjà la validation, et la
                   facture est l'état final → un seul champ Montant suffit. -->
              {@const showAccepted = dtype === 'DEVIS' || dtype === 'PROPOSITION'}
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
                  <!-- Inline amount edit. amount = montant écrit sur le doc.
                       amount_accepted = montant final négocié (DEVIS uniquement). -->
                  <div class="ds-doc-amount-edit">
                    <label class="ds-mini-label" title={dtype === 'DEVIS' ? 'Montant proposé par le presta sur le devis' : 'Montant inscrit sur le document'}>
                      Montant €
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
                      <label class="ds-mini-label" title="Montant final après négociation. Laisse vide si le devis est accepté tel quel.">
                        Négocié €
                        <input
                          type="number"
                          min="0"
                          step="1"
                          class="ds-amount-input"
                          value={doc.amount_accepted || ''}
                          placeholder="—"
                          on:blur={(e) => saveDocAmount(doc.id, 'amount_accepted', e.target.value)}
                        />
                      </label>
                    {/if}
                  </div>
                </div>
                <div class="ds-doc-actions">
                  <button class="ds-icon-btn" on:click={() => openPreview(doc)} title="Aperçu">👁</button>
                  <button class="ds-icon-btn" on:click={() => openEditDoc(doc)} title="Éditer ce document">✏️</button>
                  <button class="ds-icon-btn" on:click={() => detachDoc(doc.id)} title="Détacher du dossier (le document n'est pas supprimé)">✕</button>
                  <button class="ds-icon-btn ds-icon-btn--danger" on:click={() => hardDeleteDoc(doc)} title="Supprimer définitivement (irréversible)">🗑</button>
                </div>
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
            <!-- Manual value + on:change instead of bind:value : Svelte's auto
                 type-coercion was randomly dropping the supplier_id on save
                 when the initial value was null and the user picked a number. -->
            <select
              value={dossierForm.supplier_id == null ? '' : String(dossierForm.supplier_id)}
              on:change={(e) => dossierForm.supplier_id = e.target.value === '' ? null : parseInt(e.target.value, 10)}
            >
              <option value="">— Aucun —</option>
              {#each allSuppliers as s}<option value={String(s.id)}>{s.name}</option>{/each}
            </select>
          </label>
          <label class="ds-field">
            <span>Projet lié</span>
            <select
              value={dossierForm.project_id == null ? '' : String(dossierForm.project_id)}
              on:change={(e) => dossierForm.project_id = e.target.value === '' ? null : parseInt(e.target.value, 10)}
            >
              <option value="">— Aucun —</option>
              {#each allProjects as p}<option value={String(p.id)}>{p.title}</option>{/each}
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
        <button class="ds-btn-secondary" on:click={cleanupOrphans} title="Supprimer de la base les documents dont le fichier a été supprimé du disque" style="margin-left:auto; margin-right:8px">🧹 Nettoyer les orphelins</button>
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

<!-- ─── IMPORT DIALOG (file upload + auto-attach to current dossier) ─── -->
{#if showImportDialog}
  <div class="ds-overlay" on:mousedown|self={() => showImportDialog = false}>
    <div class="ds-dialog">
      <div class="ds-dialog-header">
        <h2>Importer un document</h2>
        <button class="ds-icon-btn" on:click={() => showImportDialog = false}>✕</button>
      </div>
      <div class="ds-dialog-body">
        <label class="ds-field">
          <span>Fichier *</span>
          <input
            type="file"
            accept="application/pdf,image/png,image/jpeg,image/webp"
            bind:this={importFileInput}
            on:change={onImportFilePicked}
            class="ds-file-input"
          />
          {#if importFile}
            <span class="ds-file-name">📎 {importFile.name} ({Math.round(importFile.size / 1024)} Ko)</span>
          {/if}
        </label>

        <div class="ds-field-row">
          <label class="ds-field">
            <span>Type *</span>
            <select bind:value={importForm.doc_type}>
              <option value="DEVIS">Devis</option>
              <option value="PROPOSITION">Proposition</option>
              <option value="BPA">BPA / Bon pour accord</option>
              <option value="BON">Bon de commande</option>
              <option value="CONTRAT">Contrat</option>
              <option value="FACTURE">Facture</option>
              <option value="RAPPORT">Rapport</option>
              <option value="AUTRE">Autre</option>
            </select>
          </label>
          <label class="ds-field">
            <span>Date du document</span>
            <input type="date" bind:value={importForm.doc_date} />
          </label>
        </div>

        <label class="ds-field">
          <span>Titre (renommage auto)</span>
          <input type="text" bind:value={importForm.title} placeholder="Sera généré auto si vide" />
          <small style="font-size:11px; color:var(--text-muted)">Format suggéré : <code>[Type] [Prestataire] - [Date]</code>. Modifie librement.</small>
        </label>

        <label class="ds-field">
          <span>Référence externe (optionnel)</span>
          <input type="text" bind:value={importForm.reference} placeholder="N° devis du presta, etc." />
        </label>

        {#if importForm.doc_type === 'FACTURE'}
          <label style="display:flex; align-items:center; gap:8px; font-size:13px; color:var(--text-secondary)">
            <input type="checkbox" bind:checked={importForm.is_acompte} />
            Cette facture est un acompte
          </label>
        {/if}
      </div>
      <div class="ds-dialog-footer">
        <button class="ds-btn-secondary" on:click={() => showImportDialog = false}>Annuler</button>
        <button class="ds-btn-primary" on:click={submitImport} disabled={importing || !importFile || !importForm.title.trim()}>
          {importing ? 'Import en cours…' : 'Importer + rattacher'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ─── EDIT DOC DIALOG — modifier titre/type/date/réf/notes/presta/acompte ─── -->
{#if editingDoc}
  <div class="ds-overlay" on:mousedown|self={() => editingDoc = null}>
    <div class="ds-dialog">
      <div class="ds-dialog-header">
        <h2>Éditer le document</h2>
        <button class="ds-icon-btn" on:click={() => editingDoc = null}>✕</button>
      </div>
      <div class="ds-dialog-body">
        <label class="ds-field">
          <span>Titre *</span>
          <input type="text" bind:value={editDocForm.title} placeholder="Titre du document" />
        </label>

        <div class="ds-field-row">
          <label class="ds-field">
            <span>Type</span>
            <select bind:value={editDocForm.doc_type}>
              <option value="DEVIS">Devis</option>
              <option value="PROPOSITION">Proposition</option>
              <option value="BPA">BPA / Bon pour accord</option>
              <option value="BON">Bon de commande</option>
              <option value="CONTRAT">Contrat</option>
              <option value="FACTURE">Facture</option>
              <option value="RAPPORT">Rapport</option>
              <option value="AUTRE">Autre</option>
            </select>
          </label>
          <label class="ds-field">
            <span>Date du document</span>
            <input type="date" bind:value={editDocForm.doc_date} />
          </label>
        </div>

        <label class="ds-field">
          <span>Référence externe</span>
          <input type="text" bind:value={editDocForm.reference} placeholder="N° devis du presta, etc." />
        </label>

        <label class="ds-field">
          <span>Prestataire</span>
          <select
            value={editDocForm.supplier_id == null ? '' : String(editDocForm.supplier_id)}
            on:change={(e) => editDocForm.supplier_id = e.target.value === '' ? null : parseInt(e.target.value, 10)}
          >
            <option value="">— Aucun —</option>
            {#each allSuppliers as s}<option value={String(s.id)}>{s.name}</option>{/each}
          </select>
        </label>

        <label class="ds-field">
          <span>Notes</span>
          <textarea rows="2" bind:value={editDocForm.notes} placeholder="Optionnel"></textarea>
        </label>

        {#if editDocForm.doc_type === 'FACTURE'}
          <label style="display:flex; align-items:center; gap:8px; font-size:13px; color:var(--text-secondary)">
            <input type="checkbox" bind:checked={editDocForm.is_acompte} />
            Cette facture est un acompte
          </label>
        {/if}
      </div>
      <div class="ds-dialog-footer">
        <button class="ds-btn-secondary" on:click={() => editingDoc = null}>Annuler</button>
        <button class="ds-btn-primary" on:click={saveDocEdit} disabled={savingDoc || !editDocForm.title.trim()}>
          {savingDoc ? 'Enregistrement…' : 'Enregistrer'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ─── PREVIEW MODAL (PDF / image dans une iframe) ─── -->
{#if previewDoc}
  <div class="ds-overlay" on:mousedown|self={closePreview}>
    <div class="ds-preview-modal">
      <div class="ds-preview-header">
        <div class="ds-preview-title">
          <strong>{previewDoc.title}</strong>
          {#if previewDoc.internal_ref}
            <span class="ds-doc-ref" style="margin-left:8px">{previewDoc.internal_ref}</span>
          {/if}
        </div>
        <a class="ds-btn-secondary" href={`${API_BASE}/api/documents/${previewDoc.id}/preview`} target="_blank" rel="noopener">Ouvrir dans un onglet</a>
        <button class="ds-icon-btn" on:click={closePreview}>✕</button>
      </div>
      <iframe
        class="ds-preview-iframe"
        src={`${API_BASE}/api/documents/${previewDoc.id}/preview`}
        title={previewDoc.title}
      ></iframe>
    </div>
  </div>
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

  /* Sort dropdown in the topbar — compact, theme-aware native <select>. */
  .ds-sort {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .ds-sort-label {
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 10px;
  }
  .ds-sort select {
    background: var(--bg-input, rgba(0,0,0,0.04));
    border: 1px solid var(--ds-border);
    color: var(--text-heading);
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
    font-weight: 500;
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
  /* Image variant — when a logo is uploaded, render it directly instead of
     the colored initials avatar. White-ish backing so dark logos stay
     readable on any theme. */
  .ds-supplier-avatar--img {
    background: rgba(255, 255, 255, 0.9);
    object-fit: contain;
    padding: 2px;
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
  .ds-icon-btn--danger:hover {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.5);
    color: #EF4444;
  }

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
    background: var(--bg-input, rgba(0,0,0,0.04));
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 11.5px;
    color: var(--ds-text-secondary);
  }
  /* Placeholder chip when a field isn't filled — yellow accent, cliquable. */
  .ds-chip--empty {
    background: color-mix(in srgb, var(--warning, #F59E0B) 18%, transparent);
    color: var(--warning, #F59E0B);
    cursor: pointer;
    font-weight: 500;
  }
  .ds-chip--empty:hover { filter: brightness(1.1); }

  .ds-status-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }
  .ds-status-label {
    font-size: 11px;
    /* Was `--ds-text-muted` which renders nearly invisible in light theme.
       Bump to `--text-secondary` so the label stays readable on both themes. */
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 700;
  }
  /* ── Quick-edit row (custom dropdowns) ─────────────────────
     Replace native <select> entirely: too many cross-browser/theme quirks.
     Each "pill" is a clickable element with a colored dot + label; clicking
     it expands a custom menu below. Pure CSS + Svelte conditional. */
  .ds-quick-edits {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .ds-quick-field {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .ds-quick-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
  }
  .ds-quick-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    background: var(--bg-card);
    border: 1px solid var(--ds-border-strong);
    border-radius: 6px;
    cursor: pointer;
    user-select: none;
    transition: border-color 0.15s, background 0.15s;
    /* Force opaque rendering of text so light theme is never washed out. */
    color: var(--text-heading);
    font-size: 13px;
    font-weight: 600;
  }
  .ds-quick-pill:hover {
    border-color: var(--ds-primary);
  }
  .ds-quick-pill--empty {
    border-color: color-mix(in srgb, var(--warning, #F59E0B) 60%, transparent);
    background: color-mix(in srgb, var(--warning, #F59E0B) 8%, var(--bg-card));
  }
  .ds-quick-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .ds-quick-text {
    color: var(--text-heading);
  }
  .ds-quick-caret {
    color: var(--text-muted);
    font-size: 10px;
    margin-left: 2px;
  }
  /* Backdrop catches clicks outside the menu to close it. */
  .ds-quick-backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    background: transparent;
  }
  .ds-quick-menu {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    min-width: 240px;
    background: var(--bg-card);
    border: 1px solid var(--ds-border-strong);
    border-radius: 8px;
    padding: 4px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.35);
    z-index: 60;
  }
  .ds-quick-menu--scroll {
    max-height: 320px;
    overflow-y: auto;
  }
  .ds-quick-menu-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 10px;
    border-radius: 5px;
    cursor: pointer;
    color: var(--text-heading);
    font-size: 13px;
    transition: background 0.1s;
  }
  .ds-quick-menu-item:hover {
    background: var(--bg-hover, rgba(127,127,127,0.1));
  }
  .ds-quick-menu-item.active {
    background: color-mix(in srgb, var(--primary, #8869e1) 18%, transparent);
    font-weight: 600;
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
    /* Stronger backdrop so the dialog stands out clearly on both themes. */
    background: rgba(15, 20, 35, 0.72);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
  }
  .ds-dialog {
    /* Force a fully opaque background — explicit fallback for the rare case
       where `--bg-card` resolves to a semi-transparent token. */
    background: var(--bg-card, #ffffff);
    border: 1px solid var(--ds-border-strong);
    border-radius: 12px;
    width: min(480px, 92vw);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 70px rgba(0,0,0,0.55), 0 4px 12px rgba(0,0,0,0.3);
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

  /* Import dialog file input */
  .ds-file-input {
    color: var(--text-secondary);
  }
  .ds-file-input::file-selector-button {
    background: rgba(var(--accent-rgb, 136, 105, 225), 0.15);
    border: 1px solid var(--accent, var(--primary));
    color: var(--accent, var(--primary));
    padding: 5px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    margin-right: 10px;
  }
  .ds-file-input::file-selector-button:hover {
    background: rgba(var(--accent-rgb, 136, 105, 225), 0.25);
  }
  .ds-file-name {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 4px;
  }

  /* Doc action buttons (eye + detach) clustered to the right of each row */
  .ds-doc-actions {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  /* ── Preview modal (PDF iframe) ── */
  .ds-preview-modal {
    background: var(--bg-card, #fff);
    border: 1px solid var(--ds-border-strong);
    border-radius: 12px;
    width: min(960px, 95vw);
    height: min(85vh, 900px);
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.55);
  }
  .ds-preview-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--ds-border);
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .ds-preview-title {
    flex: 1;
    min-width: 0;
    font-size: 14px;
    color: var(--text-heading);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ds-preview-iframe {
    flex: 1;
    width: 100%;
    border: none;
    background: rgba(0, 0, 0, 0.04);
    border-radius: 0 0 12px 12px;
  }

  /* ═══════════════════════════════════════════════════════════
     v7.7.0 — Refonte visuelle (pipeline / stepper / dashboard /
     vue compacte). Validée via docs/dossiers-redesign-v2-mockup.html
     ═══════════════════════════════════════════════════════════ */

  /* ── Toggle vue cards / compacte (topbar) ── */
  .ds-view-toggle {
    display: flex; gap: 2px;
    background: var(--bg-input);
    border: 1px solid var(--border-card);
    border-radius: 8px; padding: 3px;
  }
  .ds-view-toggle button {
    background: transparent; border: none;
    color: var(--text-muted); font-size: 14px;
    padding: 5px 12px; border-radius: 6px; cursor: pointer;
    line-height: 1;
  }
  .ds-view-toggle button.active {
    background: var(--accent); color: #fff;
  }

  /* ── Pipeline bar ── */
  .ds-pipeline-wrap {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    padding: 12px 16px;
    display: flex; align-items: center; gap: 16px;
    margin-bottom: 14px;
  }
  .ds-pipeline { display: flex; flex: 1; }
  .ds-pl-seg {
    flex: 1;
    position: relative;
    padding: 8px 8px 8px 20px;
    cursor: pointer;
    background: var(--bg-input);
    clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%, 12px 50%);
    margin-left: -7px;
    text-align: center;
    transition: filter 0.12s;
    user-select: none;
  }
  .ds-pl-seg:first-child {
    clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%);
    margin-left: 0;
    border-radius: 8px 0 0 8px;
    padding-left: 12px;
  }
  .ds-pl-seg:hover { filter: brightness(0.95); }
  .ds-pl-seg::before {
    content: '';
    position: absolute; top: 7px; right: 18px;
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--seg-color);
  }
  .ds-pl-count {
    font-size: 18px; font-weight: 800;
    color: var(--text-heading);
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }
  .ds-pl-label {
    font-size: 9.5px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted);
  }
  .ds-pl-seg.active { background: var(--seg-color); }
  .ds-pl-seg.active .ds-pl-count { color: #fff; }
  .ds-pl-seg.active .ds-pl-label { color: rgba(255,255,255,0.85); }
  .ds-pl-seg.active::before { background: rgba(255,255,255,0.6); }

  .ds-pl-kpis {
    display: flex; gap: 20px;
    border-left: 1px solid var(--border-card);
    padding-left: 18px;
  }
  .ds-plk { text-align: right; }
  .ds-plk-v {
    font-size: 16px; font-weight: 800;
    color: var(--text-heading);
    font-variant-numeric: tabular-nums;
  }
  .ds-plk-v--green { color: var(--success); }
  .ds-plk-k {
    font-size: 9.5px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted);
  }

  /* ── Card : bordure statut + badge relance ── */
  .ds-card { border-left: 3px solid var(--st-color, var(--border-card)); }
  .ds-relance-pill {
    font-size: 10.5px; font-weight: 700;
    padding: 3px 10px; border-radius: 999px;
    background: rgba(234, 88, 12, 0.14); color: #C2410C;
    white-space: nowrap; flex-shrink: 0;
    animation: ds-pulse 2.5s ease-in-out infinite;
  }
  @keyframes ds-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }

  /* ── Stepper fusionné ── */
  .ds-steps {
    display: flex; align-items: flex-start;
    padding-top: 2px;
  }
  .ds-step { min-width: 96px; }
  .ds-step-head {
    display: flex; align-items: center; gap: 6px;
    margin-bottom: 2px;
  }
  .ds-step-dot {
    width: 15px; height: 15px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 9px; font-weight: 800;
    background: transparent;
    border: 2px dashed var(--border-card);
    color: #fff;
    flex-shrink: 0;
    box-sizing: border-box;
  }
  .ds-step.done .ds-step-dot {
    background: var(--accent);
    border: none;
  }
  .ds-step-label {
    font-size: 9px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--text-muted);
  }
  .ds-step.done .ds-step-label { color: var(--text-heading); }
  .ds-step-amt {
    font-size: 14.5px; font-weight: 750;
    color: var(--text-heading);
    padding-left: 21px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .ds-step:not(.done) .ds-step-amt {
    color: var(--text-muted); opacity: 0.55; font-weight: 500;
  }
  .ds-ecart {
    font-size: 10px; font-weight: 700;
    color: var(--danger); margin-left: 4px;
  }
  .ds-step-conn {
    flex: 1; height: 2px;
    margin: 7px 8px 0;
    background: var(--border-card);
    border-radius: 2px;
    min-width: 16px;
  }
  .ds-step-conn.done { background: var(--accent); opacity: 0.35; }
  .ds-step-date {
    margin-left: auto;
    align-self: flex-end;
    font-size: 11px; color: var(--text-muted);
    white-space: nowrap;
    padding-left: 10px;
  }

  /* ── Vue compacte (table) ── */
  .ds-ctable {
    width: 100%;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    border-collapse: separate; border-spacing: 0;
    overflow: hidden;
    font-size: 12.5px;
  }
  .ds-ctable th {
    text-align: left; padding: 9px 12px;
    font-size: 9.5px; font-weight: 700;
    letter-spacing: 0.6px; text-transform: uppercase;
    color: var(--text-muted);
    background: var(--bg-input);
    border-bottom: 1px solid var(--border-card);
  }
  .ds-ctable th.r, .ds-ctable td.r { text-align: right; }
  .ds-ctable td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-card);
    color: var(--text-primary);
    white-space: nowrap;
  }
  .ds-ctable tbody tr { cursor: pointer; }
  .ds-ctable tbody tr:hover td { background: var(--bg-hover); }
  .ds-ctable tbody tr.selected td { background: rgba(var(--accent-rgb), 0.08); }
  .ds-ctable tbody tr:last-child td { border-bottom: none; }
  .ds-ctable .t-title {
    font-weight: 650; color: var(--text-heading);
    max-width: 300px; overflow: hidden; text-overflow: ellipsis;
  }
  .ds-ctable .t-amt {
    font-weight: 700; color: var(--text-heading);
    font-variant-numeric: tabular-nums;
  }
  .ds-ctable .t-dim { color: var(--text-muted); opacity: 0.5; font-weight: 400; }

  /* ── Tableau de bord (panneau droit au repos) ── */
  .ds-dash {
    display: flex; flex-direction: column; gap: 12px;
    padding: 4px 2px;
  }
  .ds-dash-card {
    background: var(--bg-input);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    padding: 14px 16px;
  }
  .ds-dash-title {
    font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.6px;
    color: var(--text-muted);
    margin-bottom: 11px;
  }
  .ds-dash-stats {
    display: grid; grid-template-columns: 1fr 1fr; gap: 9px;
  }
  .ds-ds {
    background: var(--bg-card);
    border-radius: 9px;
    padding: 10px 12px;
  }
  .ds-ds--full { grid-column: 1 / -1; }
  .ds-ds-v {
    font-size: 17px; font-weight: 800;
    color: var(--text-heading); line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }
  .ds-ds-v--green { color: var(--success); }
  .ds-ds-v--amber { color: var(--warning); }
  .ds-ds-k {
    font-size: 9.5px; font-weight: 650;
    text-transform: uppercase; letter-spacing: 0.4px;
    color: var(--text-muted); margin-top: 2px;
  }

  .ds-tp-row {
    display: flex; align-items: center; gap: 9px;
    margin-bottom: 8px; cursor: pointer;
  }
  .ds-tp-row:last-child { margin-bottom: 0; }
  .ds-tp-row:hover .ds-tp-name { color: var(--accent); }
  .ds-tp-name {
    font-size: 12px; font-weight: 600;
    color: var(--text-heading);
    width: 76px; flex-shrink: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .ds-tp-bar-wrap {
    flex: 1; height: 6px;
    background: var(--bg-card);
    border-radius: 4px; overflow: hidden;
  }
  .ds-tp-bar {
    display: block; height: 100%;
    background: var(--accent);
    border-radius: 4px; opacity: 0.75;
  }
  .ds-tp-amt {
    font-size: 11.5px; font-weight: 700;
    color: var(--text-heading);
    width: 64px; text-align: right; flex-shrink: 0;
    font-variant-numeric: tabular-nums;
  }

  .ds-rl-item {
    display: flex; align-items: center; gap: 9px;
    padding: 8px 10px; border-radius: 8px;
    background: rgba(234, 88, 12, 0.07);
    border: 1px solid rgba(234, 88, 12, 0.25);
    cursor: pointer; margin-bottom: 7px;
  }
  .ds-rl-item:last-child { margin-bottom: 0; }
  .ds-rl-item:hover { border-color: rgba(234, 88, 12, 0.55); }
  .ds-rl-body { flex: 1; min-width: 0; }
  .ds-rl-t {
    font-size: 12px; font-weight: 650;
    color: var(--text-heading);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .ds-rl-s { font-size: 10.5px; color: #C2410C; }
  .ds-rl-arrow { color: #C2410C; font-weight: 800; flex-shrink: 0; }

  .ds-dash-hint {
    text-align: center;
    font-size: 11px; color: var(--text-muted);
    margin: 2px 0 0;
  }
</style>
