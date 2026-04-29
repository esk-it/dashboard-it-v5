<script>
  import { onMount, onDestroy } from 'svelte';
  import { api, API_BASE } from '../api/client.js';
  import { success, error as toastError } from '../stores/toast.js';

  const DOC_TYPE_COLORS = {
    DEVIS:     { bg: '#3B82F620', color: '#3B82F6', label: 'Devis',              border: '#3B82F6', icon: '\u{1F4D5}' },
    FACTURE:   { bg: '#0D948820', color: '#0D9488', label: 'Facture',            border: '#0D9488', icon: '\u{1F4D7}' },
    CONTRAT:   { bg: '#8B5CF620', color: '#8B5CF6', label: 'Contrat',            border: '#8B5CF6', icon: '\u{1F4D8}' },
    BON:       { bg: '#F59E0B20', color: '#F59E0B', label: 'Bon pour accord',    border: '#F59E0B', icon: '\u{1F4D9}' },
    RAPPORT:   { bg: '#EC489920', color: '#EC4899', label: 'Rapport',            border: '#EC4899', icon: '\u{1F4DA}' },
    AUTRE:     { bg: '#64748B20', color: '#64748B', label: 'Autre',              border: '#64748B', icon: '\u{1F4C4}' },
  };

  const LINK_TYPES = [
    { value: 'related',    label: 'Lie a' },
    { value: 'depends_on', label: 'Depend de' },
    { value: 'supersedes', label: 'Remplace' },
    { value: 'references', label: 'Reference' },
    { value: 'attachment', label: 'Piece jointe de' },
  ];

  // Workflow ordering: Devis → BPA/Bon → Contrat → Facture → Rapport → Autre.
  // Used to lay out a chain inside an "Ensemble" card so the hierarchy is visible
  // regardless of which side of the link the user clicked from.
  const TYPE_ORDER = {
    DEVIS:    1,
    BON:      2,
    BPA:      2,
    CONTRAT:  3,
    FACTURE:  4,
    RAPPORT:  5,
    AUTRE:    6,
  };

  const FILE_TYPE_ICONS = {
    pdf:   '\u{1F4D5}',
    doc:   '\u{1F4D8}',
    docx:  '\u{1F4D8}',
    xls:   '\u{1F4D7}',
    xlsx:  '\u{1F4D7}',
    png:   '\u{1F5BC}',
    jpg:   '\u{1F5BC}',
    jpeg:  '\u{1F5BC}',
    gif:   '\u{1F5BC}',
    bmp:   '\u{1F5BC}',
    svg:   '\u{1F5BC}',
    txt:   '\u{1F4C4}',
    csv:   '\u{1F4CA}',
    zip:   '\u{1F4E6}',
    rar:   '\u{1F4E6}',
    '7z':  '\u{1F4E6}',
  };

  // ── State ──────────────────────────────────────────────────
  let documents = [];
  let docTypes = [];
  let docTags = [];
  let suppliers = [];
  let loading = true;

  // All edges in the document_links graph — fetched once at load, used to group
  // related docs (Devis → BPA → Facture) into workflow cards.
  let allLinks = [];

  // Logo error tracking for supplier logos in workflow cards
  let supplierLogoErrors = {};

  // Filters
  let searchQuery = '';
  let filterType = '';
  let filterTag = '';
  let filterSupplier = '';
  let searchDebounceTimer;

  // Expand
  let expandedDocId = null;
  // Workflow row expand (when in flat mode, a chain is one folded row)
  let expandedWorkflowKey = null;

  // View mode: 'list' (flat with workflows folded), 'date' (every doc as a row, no grouping),
  // or 'supplier' (cards per supplier). Persist across sessions.
  let viewMode = (() => {
    try {
      const saved = localStorage.getItem('docs.viewMode');
      if (saved === 'list' || saved === 'date' || saved === 'supplier') return saved;
      // Backwards-compat with the old binary toggle
      if (localStorage.getItem('docs.groupBySupplier') === '1') return 'supplier';
      return 'list';
    } catch { return 'list'; }
  })();
  $: { try { localStorage.setItem('docs.viewMode', viewMode); } catch {} }
  // Legacy alias to keep downstream conditionals readable
  $: groupBySupplier = viewMode === 'supplier';

  // Preview panel
  let previewDoc = null;

  // Document links
  let docLinks = {};
  let loadingLinks = {};

  // Link dialog (existing — used internally by the new manager to add a link)
  let showLinkDialog = false;
  let linkSourceDocId = null;
  let linkForm = { target_id: '', link_type: 'related' };

  // Link manager dialog (new) — opened from the 🔗 button on each doc row.
  // Shows current links, lets the user add/remove. We re-fetch links each time it opens.
  let showLinkManager = false;
  let linkManagerDocId = null;
  let linkManagerLinks = [];
  let linkManagerLoading = false;

  async function openLinkManager(docId) {
    linkManagerDocId = docId;
    linkManagerLinks = [];
    linkManagerLoading = true;
    showLinkManager = true;
    try {
      const detail = await api.get(`/api/documents/${docId}`);
      linkManagerLinks = detail.links || [];
    } catch (e) {
      toastError('Erreur lors du chargement des liens');
    }
    linkManagerLoading = false;
  }

  async function removeLinkFromManager(linkId) {
    try {
      await fetch(`${API_BASE}/api/documents/links/${linkId}`, { method: 'DELETE' });
      // Refresh local state + page-level link graph so workflow cards regroup
      const detail = await api.get(`/api/documents/${linkManagerDocId}`);
      linkManagerLinks = detail.links || [];
      const fresh = await api.get('/api/documents/links-graph').catch(() => null);
      if (Array.isArray(fresh)) allLinks = fresh;
    } catch (e) {
      toastError('Erreur lors de la suppression du lien');
    }
  }

  function openAddLinkFromManager() {
    // Reuse the existing link dialog; it'll POST a link and we'll refresh on close.
    linkSourceDocId = linkManagerDocId;
    linkForm = { target_id: '', link_type: 'related' };
    showLinkDialog = true;
  }

  // Click-outside handler — collapses the expanded doc when the user clicks the
  // empty space around the cards. Buttons inside doc-rows already use stopPropagation
  // on their own click handlers, so they won't trigger this.
  function onListBackgroundClick(e) {
    // If the click target is inside any .doc-row, ignore — toggleExpand handles that.
    if (e.target.closest('.doc-row')) return;
    if (e.target.closest('.workflow-row')) return;
    if (e.target.closest('.supplier-card__header')) return;
    if (e.target.closest('.workflow-arrow')) return;
    if (e.target.closest('.supplier-card__section-label')) return;
    expandedDocId = null;
  }

  // Dialog (create/edit)
  let showDialog = false;
  let editingDoc = null;
  let form = defaultForm();

  // Delete confirmation
  let confirmDeleteId = null;

  // Drag & drop
  let isDraggingOver = false;
  let dragCounter = 0;

  // File upload
  let fileInputEl;
  let folderInputEl;
  let uploadingFiles = false;
  let uploadProgress = 0;
  let uploadTotal = 0;
  let showImportDialog = false;
  let pendingFiles = [];
  let importForm = defaultForm();

  // ── Derived ────────────────────────────────────────────────
  // Union of registered suppliers + any legacy free-text supplier strings
  // found on existing documents, so old entries still work but new ones pick
  // from the supplier module.
  $: supplierList = [...new Set([
    ...suppliers.map(s => s.name).filter(Boolean),
    ...documents.map(d => d.supplier_name || d.supplier || '').filter(Boolean),
  ])].sort((a, b) => a.localeCompare(b, 'fr'));

  $: filteredDocs = documents.filter(d => {
    if (filterType && d.doc_type !== filterType) return false;
    if (filterTag && !(d.tags || '').toLowerCase().includes(filterTag.toLowerCase())) return false;
    if (filterSupplier && (d.supplier_name || '') !== filterSupplier) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (d.title || '').toLowerCase().includes(q)
        || (d.supplier_name || d.supplier || '').toLowerCase().includes(q)
        || (d.reference || '').toLowerCase().includes(q)
        || (d.internal_ref || '').toLowerCase().includes(q);
    }
    return true;
  });

  $: totalDocs = documents.length;
  $: typeCounts = documents.reduce((acc, d) => {
    acc[d.doc_type] = (acc[d.doc_type] || 0) + 1;
    return acc;
  }, {});

  // ── Supplier-first grouping ───────────────────────────────
  // Single rendering style for everything: one card per supplier, containing
  //   - chains: connected components of the link graph (size >= 2)
  //   - singletons: docs with no visible neighbours
  // This eliminates the visual jarring between "workflow card" and "plain row".
  $: docGroups = (() => {
    if (!filteredDocs?.length) return [];

    // Adjacency map across all visible docs
    const visibleIds = new Set(filteredDocs.map(d => d.id));
    const adj = new Map();
    for (const id of visibleIds) adj.set(id, new Set());
    for (const e of allLinks) {
      if (visibleIds.has(e.source_id) && visibleIds.has(e.target_id)) {
        adj.get(e.source_id).add(e.target_id);
        adj.get(e.target_id).add(e.source_id);
      }
    }
    const docById = new Map(filteredDocs.map(d => [d.id, d]));

    // Bucket docs by supplier identity first.
    // Use supplier_id when available, fall back to supplier_name/supplier text,
    // and finally a "no-supplier" bucket for orphans.
    const supplierBuckets = new Map(); // key → { supplierId, supplierName, docs: [] }
    function supplierKey(d) {
      if (d.supplier_id != null) return `id:${d.supplier_id}`;
      const name = (d.supplier_name || d.supplier || '').trim();
      return name ? `name:${name.toLowerCase()}` : '__none__';
    }
    for (const d of filteredDocs) {
      const key = supplierKey(d);
      if (!supplierBuckets.has(key)) {
        supplierBuckets.set(key, {
          key,
          supplierId: d.supplier_id ?? null,
          supplierName: (d.supplier_name || d.supplier || '').trim() || (key === '__none__' ? 'Sans prestataire' : ''),
          docs: [],
        });
      }
      supplierBuckets.get(key).docs.push(d);
    }

    // Within each supplier bucket, run BFS to find connected components.
    const result = [];
    for (const bucket of supplierBuckets.values()) {
      const bucketIds = new Set(bucket.docs.map(d => d.id));
      const seen = new Set();
      const chains = [];
      const singletons = [];
      for (const startId of bucketIds) {
        if (seen.has(startId)) continue;
        const queue = [startId];
        const compIds = [];
        while (queue.length) {
          const id = queue.shift();
          if (seen.has(id)) continue;
          seen.add(id);
          compIds.push(id);
          for (const nb of adj.get(id) || []) {
            // only follow neighbours that are in the SAME supplier bucket (chains
            // crossing suppliers are rendered as cross-group chips, see externalLinks)
            if (!seen.has(nb) && bucketIds.has(nb)) queue.push(nb);
          }
        }
        const docs = compIds.map(i => docById.get(i)).filter(Boolean);
        // Order by doc-type hierarchy first, then date as tiebreaker.
        // Standard accounting flow: Devis (proposal) → BPA/Bon (approval) → Contrat (signed)
        // → Facture (invoice). Reports and "Autre" come last.
        docs.sort((a, b) => {
          const ra = TYPE_ORDER[(a.doc_type || '').toUpperCase()] ?? 99;
          const rb = TYPE_ORDER[(b.doc_type || '').toUpperCase()] ?? 99;
          if (ra !== rb) return ra - rb;
          return (a.doc_date || a.created_at || '').localeCompare(b.doc_date || b.created_at || '');
        });
        if (docs.length > 1) chains.push(docs);
        else singletons.push(docs[0]);
      }
      // Singletons sorted by date desc inside the supplier card
      singletons.sort((a, b) => (b.doc_date || b.created_at || '').localeCompare(a.doc_date || a.created_at || ''));
      // Bucket-level "last activity" to sort suppliers most-recent-first
      const lastActivity = bucket.docs.reduce(
        (m, d) => Math.max(m, new Date(d.doc_date || d.created_at || 0).getTime()), 0,
      );
      result.push({ ...bucket, chains, singletons, lastActivity });
    }

    result.sort((a, b) => b.lastActivity - a.lastActivity);
    return result;
  })();

  function supplierInitials(name) {
    if (!name) return '??';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }

  // ── Flat list (Gmail-style) ────────────────────────────────
  // Reuse docGroups (which already buckets by supplier and finds chains) and flatten:
  //   - each chain → one "workflow" item (one folded row, expandable to its docs)
  //   - each singleton → one "doc" item (a regular row)
  // Then mix and sort by latest date so workflows interleave with isolated docs.
  $: flatItems = (() => {
    const items = [];
    for (const bucket of docGroups) {
      for (const chain of bucket.chains) {
        const lastDoc = chain[chain.length - 1];
        const dateMs = chain.reduce(
          (m, d) => Math.max(m, new Date(d.doc_date || d.created_at || 0).getTime()), 0,
        );
        items.push({
          kind: 'workflow',
          key: `wf:${bucket.key}:${chain.map(d => d.id).join('-')}`,
          docs: chain,
          supplierId: bucket.supplierId,
          supplierName: bucket.supplierName,
          lastDoc,
          dateMs,
        });
      }
      for (const doc of bucket.singletons) {
        items.push({
          kind: 'doc',
          key: `doc:${doc.id}`,
          doc,
          dateMs: new Date(doc.doc_date || doc.created_at || 0).getTime(),
        });
      }
    }
    items.sort((a, b) => b.dateMs - a.dateMs);
    return items;
  })();

  // "Par date" mode: every visible doc as its own row, no grouping. Sort by doc_date desc.
  $: dateOrderedDocs = [...filteredDocs].sort((a, b) => {
    const ta = new Date(a.doc_date || a.created_at || 0).getTime();
    const tb = new Date(b.doc_date || b.created_at || 0).getTime();
    return tb - ta;
  });

  function toggleWorkflow(key) {
    expandedWorkflowKey = expandedWorkflowKey === key ? null : key;
  }

  function workflowSummary(chain) {
    // Compact one-line summary: "Devis 16122 ⇨ BPA ⇨ Facture F16347"
    return chain.map(d => d.internal_ref || d.reference || truncateText(d.title || '', 14)).join('\u21D2 ');
  }

  // Cross-supplier link chips: when a doc points to a doc in a *different* supplier card.
  function crossSupplierLinks(doc) {
    const out = [];
    for (const e of allLinks) {
      let other = null;
      if (e.source_id === doc.id) other = e.target_id;
      else if (e.target_id === doc.id) other = e.source_id;
      if (other != null) {
        const refDoc = documents.find(x => x.id === other);
        if (!refDoc) continue;
        // Same supplier → it's already rendered inside the same chain, skip.
        const sameId = doc.supplier_id != null && refDoc.supplier_id != null && doc.supplier_id === refDoc.supplier_id;
        const sameName = !sameId && (doc.supplier_name || doc.supplier || '').trim() && (doc.supplier_name || doc.supplier || '').trim().toLowerCase() === (refDoc.supplier_name || refDoc.supplier || '').trim().toLowerCase();
        if (sameId || sameName) continue;
        out.push(refDoc);
      }
    }
    return out;
  }

  // ── Helpers ────────────────────────────────────────────────
  function defaultForm() {
    return {
      title: '',
      doc_type: 'AUTRE',
      supplier: '',
      doc_date: new Date().toISOString().slice(0, 10),
      reference: '',
      notes: '',
      tags: '',
      file_path: '',
    };
  }

  function getTypeStyle(type) {
    return DOC_TYPE_COLORS[type] || DOC_TYPE_COLORS.AUTRE;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }

  function getFileExtension(filePath) {
    if (!filePath) return '';
    const parts = filePath.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
  }

  function getFileIcon(filePath) {
    const ext = getFileExtension(filePath);
    return FILE_TYPE_ICONS[ext] || '\u{1F4C4}';
  }

  function isImageFile(filePath) {
    const ext = getFileExtension(filePath);
    return ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp'].includes(ext);
  }

  function isPdfFile(filePath) {
    return getFileExtension(filePath) === 'pdf';
  }

  function getDocById(docId) {
    return documents.find(doc => doc.id === docId);
  }

  function getDocTitle(docId) {
    const d = getDocById(docId);
    return d ? d.title : `Document #${docId}`;
  }

  function getDocType(docId) {
    const d = getDocById(docId);
    return d ? d.doc_type : 'AUTRE';
  }

  function getLinkTypeLabel(type) {
    const lt = LINK_TYPES.find(l => l.value === type);
    return lt ? lt.label : type;
  }

  function truncateText(text, maxLen = 30) {
    if (!text || text.length <= maxLen) return text || '';
    return text.slice(0, maxLen) + '\u2026';
  }

  function detectMetadataFromFilename(filename) {
    const result = { title: '', doc_type: 'AUTRE', doc_date: new Date().toISOString().slice(0, 10), reference: '' };

    // Remove extension
    const nameWithoutExt = filename.replace(/\.[^.]+$/, '');
    result.title = nameWithoutExt.replace(/[_-]/g, ' ').trim();

    // Try detect type from name
    const upper = filename.toUpperCase();
    if (upper.includes('DEVIS') || upper.includes('DEV-') || upper.includes('DEV_')) {
      result.doc_type = 'DEVIS';
    } else if (upper.includes('FACTURE') || upper.includes('FACT-') || upper.includes('FACT_') || upper.includes('FAC-')) {
      result.doc_type = 'FACTURE';
    } else if (upper.includes('CONTRAT') || upper.includes('CTR-') || upper.includes('CTR_')) {
      result.doc_type = 'CONTRAT';
    } else if (upper.includes('BON') || upper.includes('BPA-') || upper.includes('BPA_')) {
      result.doc_type = 'BON';
    } else if (upper.includes('RAPPORT') || upper.includes('RPT-') || upper.includes('RPT_')) {
      result.doc_type = 'RAPPORT';
    }

    // Try detect date (YYYY-MM-DD, DD-MM-YYYY, YYYYMMDD)
    const dateMatch = filename.match(/(\d{4})-(\d{2})-(\d{2})/) ||
                      filename.match(/(\d{2})-(\d{2})-(\d{4})/) ||
                      filename.match(/(\d{4})(\d{2})(\d{2})/);
    if (dateMatch) {
      if (dateMatch[1].length === 4) {
        result.doc_date = `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
      } else {
        result.doc_date = `${dateMatch[3]}-${dateMatch[2]}-${dateMatch[1]}`;
      }
    }

    // Try detect reference. Real-world filenames don't always follow
    // "PREFIX-YYYY-NNN"; we score tokens and pick the digit-heaviest one,
    // skipping plain years and pure-letter words.
    const tokens = nameWithoutExt.split(/[\s_]+/).filter(Boolean);
    let bestRef = null;
    let bestScore = -1;
    for (const t of tokens) {
      const digits = (t.match(/\d/g) || []).length;
      if (digits < 3) continue;                              // not enough digits to be a ref
      if (/^20\d{2}$/.test(t)) continue;                     // looks like a year
      if (/^\d{2}$/.test(t)) continue;                       // 2 digits only
      // Prefer tokens that mix letters + digits (more likely a real ref like F16347)
      const hasLetter = /[A-Za-z]/.test(t);
      const score = digits + (hasLetter ? 2 : 0);
      if (score > bestScore) { bestScore = score; bestRef = t; }
    }
    // Stricter pattern as a fallback / preferred form: PREFIX-YYYY-NNN
    const formal = filename.match(/([A-Z]{2,5}[-_]\d{4}[-_]\d{3,5})/i);
    if (formal) result.reference = formal[1];
    else if (bestRef) result.reference = bestRef;

    return result;
  }

  // ── API ────────────────────────────────────────────────────
  async function fetchDocuments() {
    loading = true;
    try {
      // Fetch the doc list AND the link graph in parallel — both feed the workflow grouping.
      const [docs, links] = await Promise.all([
        api.get('/api/documents'),
        api.get('/api/documents/links-graph').catch(() => []),
      ]);
      documents = docs;
      allLinks = Array.isArray(links) ? links : [];
    } catch (e) {
      toastError('Erreur lors du chargement des documents');
    } finally {
      loading = false;
    }
  }

  async function fetchMeta() {
    try {
      const [types, tags] = await Promise.all([
        api.get('/api/documents/types'),
        api.get('/api/documents/tags'),
      ]);
      docTypes = types;
      docTags = tags;
    } catch (_) {}
  }

  async function fetchLinks(docId) {
    if (loadingLinks[docId]) return;
    loadingLinks[docId] = true;
    try {
      const links = await api.get(`/api/documents/${docId}/links`);
      docLinks = { ...docLinks, [docId]: links };
    } catch (_) {
      docLinks = { ...docLinks, [docId]: [] };
    } finally {
      loadingLinks = { ...loadingLinks, [docId]: false };
    }
  }

  async function createLink() {
    if (!linkForm.target_id || !linkSourceDocId) return;
    try {
      await api.post(`/api/documents/${linkSourceDocId}/links`, {
        target_id: parseInt(linkForm.target_id),
        link_type: linkForm.link_type,
      });
      success('Lien cree');
      closeLinkDialog();
      await fetchLinks(linkSourceDocId);
      // Refresh global graph so the supplier cards re-bucket the new connection
      const fresh = await api.get('/api/documents/links-graph').catch(() => null);
      if (Array.isArray(fresh)) allLinks = fresh;
      // Refresh the manager dialog if it was the source
      if (showLinkManager && linkManagerDocId === linkSourceDocId) {
        try {
          const detail = await api.get(`/api/documents/${linkManagerDocId}`);
          linkManagerLinks = detail.links || [];
        } catch {}
      }
    } catch (e) {
      toastError('Erreur lors de la creation du lien');
    }
  }

  async function deleteLink(linkId, docId) {
    try {
      await api.delete(`/api/documents/links/${linkId}`);
      success('Lien supprime');
      await fetchLinks(docId);
    } catch (e) {
      toastError('Erreur lors de la suppression du lien');
    }
  }

  async function saveDocument() {
    if (!form.title.trim()) return;
    try {
      if (editingDoc) {
        const updated = await api.put(`/api/documents/${editingDoc.id}`, form);
        documents = documents.map(d => d.id === updated.id ? updated : d);
        success('Document modifie');
      } else {
        const created = await api.post('/api/documents', form);
        documents = [...documents, created];
        success('Document cree');
      }
      closeDialog();
    } catch (e) {
      toastError('Erreur lors de la sauvegarde');
    }
  }

  async function deleteDocument(id) {
    try {
      await api.delete(`/api/documents/${id}`);
      documents = documents.filter(d => d.id !== id);
      confirmDeleteId = null;
      expandedDocId = null;
      if (previewDoc && previewDoc.id === id) previewDoc = null;
      success('Document supprime');
    } catch (e) {
      toastError('Erreur lors de la suppression');
    }
  }

  // ── Upload API ─────────────────────────────────────────────
  async function uploadFiles(files, metadata) {
    uploadingFiles = true;
    uploadProgress = 0;
    uploadTotal = files.length;

    try {
      if (files.length === 1) {
        const formData = new FormData();
        formData.append('file', files[0]);
        if (metadata.title) formData.append('title', metadata.title);
        if (metadata.doc_type) formData.append('doc_type', metadata.doc_type);
        if (metadata.supplier) formData.append('supplier', metadata.supplier);
        if (metadata.doc_date) formData.append('doc_date', metadata.doc_date);
        if (metadata.reference) formData.append('reference', metadata.reference);
        if (metadata.notes) formData.append('notes', metadata.notes);
        if (metadata.tags) formData.append('tags', metadata.tags);

        const res = await fetch(`${API_BASE}/api/documents/upload`, {
          method: 'POST',
          body: formData,
        });
        if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
        uploadProgress = 1;
        success('Fichier importe avec succes');
      } else {
        const formData = new FormData();
        for (const file of files) {
          formData.append('files', file);
        }
        if (metadata.doc_type) formData.append('doc_type', metadata.doc_type);
        if (metadata.supplier) formData.append('supplier', metadata.supplier);
        if (metadata.tags) formData.append('tags', metadata.tags);

        const res = await fetch(`${API_BASE}/api/documents/upload-folder`, {
          method: 'POST',
          body: formData,
        });
        if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
        uploadProgress = files.length;
        success(`${files.length} fichiers importes avec succes`);
      }

      await fetchDocuments();
      await fetchMeta();
    } catch (e) {
      toastError('Erreur lors de l\'import: ' + e.message);
    } finally {
      uploadingFiles = false;
      uploadProgress = 0;
      uploadTotal = 0;
    }
  }

  // ── Dialog management ──────────────────────────────────────
  function openCreateDialog() {
    editingDoc = null;
    form = defaultForm();
    showDialog = true;
  }

  function openEditDialog(doc) {
    editingDoc = doc;
    form = {
      title: doc.title || '',
      doc_type: doc.doc_type || 'AUTRE',
      supplier: doc.supplier_name || doc.supplier || '',
      doc_date: doc.doc_date || '',
      reference: doc.reference || '',
      notes: doc.notes || '',
      tags: doc.tags || '',
      file_path: doc.file_path || '',
    };
    showDialog = true;
  }

  function closeDialog() {
    showDialog = false;
    editingDoc = null;
  }

  function toggleExpand(id) {
    expandedDocId = expandedDocId === id ? null : id;
    if (expandedDocId === id) {
      fetchLinks(id);
      fetchDocProjects(id);
    }
  }

  async function fetchDocProjects(docId) {
    try {
      const detail = await api.get(`/api/documents/${docId}`);
      // Merge projects into the doc in the list
      const doc = documents.find(d => d.id === docId);
      if (doc && detail.projects) {
        doc.projects = detail.projects;
        documents = documents; // trigger reactivity
      }
    } catch {}
  }

  function openPreview(doc) {
    previewDoc = doc;
  }

  function closePreview() {
    previewDoc = null;
  }

  function openLinkDialog(docId) {
    linkSourceDocId = docId;
    linkForm = { target_id: '', link_type: 'related' };
    showLinkDialog = true;
  }

  function closeLinkDialog() {
    showLinkDialog = false;
    linkSourceDocId = null;
  }

  // ── File import handlers ───────────────────────────────────
  function triggerFileInput() {
    fileInputEl && fileInputEl.click();
  }

  function triggerFolderInput() {
    folderInputEl && folderInputEl.click();
  }

  function onFileSelected(e) {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    openImportDialog(files);
    e.target.value = '';
  }

  function onFolderSelected(e) {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    openImportDialog(files);
    e.target.value = '';
  }

  function openImportDialog(files) {
    pendingFiles = files;
    const firstFile = files[0];
    const detected = detectMetadataFromFilename(firstFile.name);
    importForm = {
      ...defaultForm(),
      title: files.length === 1 ? detected.title : `Import de ${files.length} fichiers`,
      doc_type: detected.doc_type,
      doc_date: detected.doc_date,
      reference: detected.reference,
    };
    showImportDialog = true;
  }

  function closeImportDialog() {
    showImportDialog = false;
    pendingFiles = [];
  }

  async function confirmImport() {
    if (pendingFiles.length === 0) return;
    showImportDialog = false;
    await uploadFiles(pendingFiles, importForm);
    pendingFiles = [];
  }

  // ── Chain navigation ───────────────────────────────────────
  function navigateToLinkedDoc(docId) {
    const doc = getDocById(docId);
    if (!doc) return;
    expandedDocId = docId;
    fetchLinks(docId);
    // Scroll to the document
    setTimeout(() => {
      const el = document.querySelector(`[data-doc-id="${docId}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 50);
  }

  // ── Search debounce ────────────────────────────────────────
  function onSearchInput(e) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      searchQuery = e.target.value;
    }, 250);
  }

  // ── Drag & Drop handlers ──────────────────────────────────
  function onDragEnter(e) {
    e.preventDefault();
    dragCounter++;
    if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
      isDraggingOver = true;
    }
  }

  function onDragOver(e) {
    e.preventDefault();
  }

  function onDragLeave(e) {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
      dragCounter = 0;
      isDraggingOver = false;
    }
  }

  function onDrop(e) {
    e.preventDefault();
    dragCounter = 0;
    isDraggingOver = false;

    const files = Array.from(e.dataTransfer.files || []);
    if (files.length > 0) {
      openImportDialog(files);
    }
  }

  // ── Preview URL builder ────────────────────────────────────
  function getPreviewUrl(doc) {
    return `${API_BASE}/api/documents/${doc.id}/preview`;
  }

  async function fetchSuppliers() {
    try { suppliers = await api.get('/api/suppliers'); } catch { suppliers = []; }
  }

  // ── Lifecycle ──────────────────────────────────────────────
  // If another page asked to focus a specific document (via sessionStorage flag),
  // clear filters and expand/scroll to it after the list has loaded.
  async function handleIncomingFocus() {
    let focusId = null;
    try {
      const raw = sessionStorage.getItem('docs.focusId');
      if (raw) {
        focusId = parseInt(raw, 10);
        sessionStorage.removeItem('docs.focusId');
      }
    } catch {}
    if (!focusId || !documents?.length) return;
    // Make sure the doc is visible: clear filters and search.
    filterType = ''; filterTag = ''; filterSupplier = '';
    searchQuery = '';
    // Wait one tick so reactive lists rebuild
    await new Promise(r => setTimeout(r, 50));
    expandedDocId = focusId;
    // Workflow that contains the doc — auto-open it
    for (const item of flatItems) {
      if (item.kind === 'workflow' && item.docs.some(d => d.id === focusId)) {
        expandedWorkflowKey = item.key;
        break;
      }
    }
    await new Promise(r => setTimeout(r, 80));
    const el = document.querySelector(`[data-doc-id="${focusId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('doc-row--flash');
      setTimeout(() => el.classList.remove('doc-row--flash'), 1500);
    }
  }

  onMount(async () => {
    await fetchDocuments();
    fetchMeta();
    fetchSuppliers();
    // Defer focus handling so reactive computations have settled
    setTimeout(handleIncomingFocus, 100);
  });

  onDestroy(() => {
    clearTimeout(searchDebounceTimer);
  });
</script>

<!-- Hidden file inputs -->
<input
  type="file"
  bind:this={fileInputEl}
  on:change={onFileSelected}
  style="display:none"
  multiple
/>
<input
  type="file"
  bind:this={folderInputEl}
  on:change={onFolderSelected}
  style="display:none"
  webkitdirectory
/>

<div
  class="documents-page"
  on:dragenter={onDragEnter}
  on:dragover={onDragOver}
  on:dragleave={onDragLeave}
  on:drop={onDrop}
>
  <!-- ── Drag & Drop Overlay ──────────────────────────────── -->
  {#if isDraggingOver}
    <div class="drop-overlay">
      <div class="drop-zone">
        <div class="drop-icon-ring">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <div class="drop-title">Glissez vos fichiers ici</div>
        <div class="drop-subtitle">PDF, images, documents Office, archives...</div>
      </div>
    </div>
  {/if}

  <!-- ── Upload Progress ──────────────────────────────────── -->
  {#if uploadingFiles}
    <div class="upload-progress-bar">
      <div class="upload-progress-fill" style="width: {uploadTotal > 0 ? (uploadProgress / uploadTotal) * 100 : 0}%"></div>
      <span class="upload-progress-text">
        Import en cours... {uploadProgress}/{uploadTotal}
      </span>
    </div>
  {/if}

  <!-- ── Stats Bar ──────────────────────────────────────── -->
  <div class="ya-kpi-row">
    <div class="ya-kpi ya-kpi--primary">
      <span class="ya-kpi__value">{totalDocs}</span>
      <span class="ya-kpi__label">Total</span>
    </div>
    {#each Object.entries(typeCounts) as [type, count]}
      <div class="ya-kpi">
        <span class="ya-kpi__value" style="color: {getTypeStyle(type).color}">{count}</span>
        <span class="ya-kpi__label">{getTypeStyle(type).label || type}</span>
      </div>
    {/each}
  </div>

  <!-- ── Action bar ─────────────────────────────────────── -->
  <!-- Single action: Importer un fichier (drag & drop also works). The previous
       "Nouveau" + "Importer un dossier" buttons were redundant for the actual flow. -->
  <div class="docs-toolbar">
    <button class="ya-btn ya-btn--primary docs-toolbar__import" on:click={triggerFileInput}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px; margin-right: 4px">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        Importer
      </button>

    <div class="docs-toolbar__search">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input type="text" placeholder="Rechercher (titre, ref interne ou externe, fournisseur...)" on:input={onSearchInput} />
    </div>

    <select class="filter-select" bind:value={filterType}>
      <option value="">— Tous types —</option>
      {#each docTypes as t}<option value={t}>{getTypeStyle(t).label || t}</option>{/each}
    </select>
    <select class="filter-select" bind:value={filterTag}>
      <option value="">— Tous tags —</option>
      {#each docTags as tag}<option value={tag.name || tag}>{tag.name || tag}</option>{/each}
    </select>
    <select class="filter-select" bind:value={filterSupplier}>
      <option value="">— Tous fournisseurs —</option>
      {#each supplierList as s}<option value={s}>{s}</option>{/each}
    </select>
    <select class="filter-select view-mode-select" bind:value={viewMode} title="Mode d'affichage">
        <option value="list">{'\u2630'} Liste (groupes plies)</option>
        <option value="date">{'\u{1F4C5}'} Par date</option>
        <option value="supplier">{'\u{1F4C2}'} Par prestataire</option>
      </select>
  </div>

  <!-- ── Main Content Layout (list + preview) ────────────── -->
  <div class="content-layout" class:has-preview={previewDoc}>
    <!-- Document List -->
    <div class="doc-list-area">
      {#if loading}
        <div class="loading-msg">
          <div class="loading-spinner"></div>
          Chargement des documents...
        </div>
      {:else if filteredDocs.length === 0}
        <div class="empty-msg">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <div>Aucun document trouve</div>
          <div class="empty-hint">Importez des fichiers ou creez un nouveau document</div>
        </div>
      {:else}
        <!-- Reusable doc row + expanded view, used both in workflow chains and singletons -->
        {#snippet docRow(doc)}
          <div
            class="doc-row"
            class:doc-row-expanded={expandedDocId === doc.id}
            class:doc-row-selected={previewDoc && previewDoc.id === doc.id}
            style="border-left: 3px solid {getTypeStyle(doc.doc_type).border}"
            data-doc-id={doc.id}
          >
            <div class="doc-main" on:click={() => toggleExpand(doc.id)}>
              <span class="doc-file-icon" title={getFileExtension(doc.file_path).toUpperCase() || 'Fichier'}>
                {getFileIcon(doc.file_path)}
              </span>
              <span class="doc-type-badge"
                    style="background: {getTypeStyle(doc.doc_type).bg}; color: {getTypeStyle(doc.doc_type).color}; border: 1px solid {getTypeStyle(doc.doc_type).color}40">
                {getTypeStyle(doc.doc_type).label || doc.doc_type}
              </span>
              <!-- Supplier identity (logo + name) — kept compact so a row stays single-line.
                   Hidden when the row is inside the supplier-card view (already in the header). -->
              {#if !groupBySupplier && (doc.supplier_id || doc.supplier_name || doc.supplier)}
                <span class="doc-supplier-cell">
                  {#if doc.supplier_id && !supplierLogoErrors[doc.supplier_id]}
                    <img class="doc-supplier-cell__logo"
                         src="{API_BASE}/api/suppliers/{doc.supplier_id}/logo" alt=""
                         on:error={() => { supplierLogoErrors[doc.supplier_id] = true; supplierLogoErrors = supplierLogoErrors; }} />
                  {:else}
                    <span class="doc-supplier-cell__initials">{supplierInitials(doc.supplier_name || doc.supplier || '?')}</span>
                  {/if}
                  <span class="doc-supplier-cell__name">{doc.supplier_name || doc.supplier}</span>
                </span>
              {/if}
              <div class="doc-title-group">
                <div class="doc-title-row">
                  {#if doc.internal_ref}<span class="doc-iref">{doc.internal_ref}</span>{/if}
                  <span class="doc-title">{doc.title}</span>
                </div>
                {#if doc.tags}
                  <span class="doc-tags-inline">{doc.tags}</span>
                {/if}
              </div>
              {#if doc.doc_date}<span class="doc-date">{formatDate(doc.doc_date)}</span>{/if}
              {#if doc.file_path}<span class="doc-ext-badge">{getFileExtension(doc.file_path).toUpperCase()}</span>{/if}
              <!-- Cross-supplier link chips (rare): same-supplier links are visualised by the workflow card -->
              {#each crossSupplierLinks(doc) as ext}
                <button class="doc-cross-link" on:click|stopPropagation={() => toggleExpand(ext.id)}
                        title="Lié à : {ext.title}"
                        style="border-color: {getTypeStyle(ext.doc_type).color}55; color: {getTypeStyle(ext.doc_type).color}">
                  → {getTypeStyle(ext.doc_type).label} {truncateText(ext.reference || ext.title, 16)}
                </button>
              {/each}
              <div class="doc-actions">
                {#if doc.file_path}
                  <button class="btn-icon btn-icon-preview" on:click|stopPropagation={() => openPreview(doc)} title="Apercu">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  </button>
                {/if}
                <button class="btn-icon" on:click|stopPropagation={() => openLinkManager(doc.id)} title="Gérer les liens">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                </button>
                <button class="btn-icon" on:click|stopPropagation={() => openEditDialog(doc)} title="Modifier">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="btn-icon btn-icon-danger" on:click|stopPropagation={() => { confirmDeleteId = doc.id; }} title="Supprimer">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </div>

            <!-- Expanded area: tags, projects, notes, file path. Links are managed via the
                 dedicated dialog (button above) since the workflow card already shows them. -->
            {#if expandedDocId === doc.id}
              <div class="doc-expanded">
                {#if doc.tags}
                  <div class="expanded-section">
                    <div class="expanded-label">Tags</div>
                    <div class="tags-list">
                      {#each doc.tags.split(',').map(t => t.trim()).filter(Boolean) as tag}
                        <span class="tag-chip">{tag}</span>
                      {/each}
                    </div>
                  </div>
                {/if}
                {#if doc.projects?.length > 0}
                  <div class="expanded-section">
                    <div class="expanded-label">Projets liés</div>
                    <div class="tags-list">
                      {#each doc.projects as proj}
                        <span class="tag-chip" style="background:{proj.color}20;color:{proj.color};border-color:{proj.color}40">Projet: {proj.title}</span>
                      {/each}
                    </div>
                  </div>
                {/if}
                {#if doc.notes}
                  <div class="expanded-section">
                    <div class="expanded-label">Notes</div>
                    <div class="notes-display">{doc.notes}</div>
                  </div>
                {/if}
                {#if doc.file_path}
                  <div class="expanded-section">
                    <div class="expanded-label">Fichier</div>
                    <div class="file-path">{getFileIcon(doc.file_path)} {doc.file_path}</div>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/snippet}

        <!-- Click anywhere outside a doc card → collapse expand -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="doc-list-clickable" on:click={onListBackgroundClick}>
        {#if viewMode === 'list'}
          <!-- Flat list mode: workflow rows mirror the same grid as singles for visual consistency. -->
          {#each flatItems as item (item.key)}
            {#if item.kind === 'workflow'}
              {@const isOpen = expandedWorkflowKey === item.key}
              <div class="doc-row doc-row--workflow" class:doc-row-expanded={isOpen}
                   style="border-left: 3px solid var(--primary, #8869e1)">
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div class="doc-main doc-main--workflow" on:click={() => toggleWorkflow(item.key)}>
                  <span class="doc-file-icon" title="Workflow">{'\u{1F517}'}</span>
                  <span class="doc-type-badge doc-type-badge--workflow"
                        title="Ensemble de {item.docs.length} documents li{'\u00e9'}s">
                    Ensemble {item.docs.length}
                  </span>
                  {#if item.supplierId && !supplierLogoErrors[item.supplierId]}
                    <span class="doc-supplier-cell">
                      <img class="doc-supplier-cell__logo"
                           src="{API_BASE}/api/suppliers/{item.supplierId}/logo" alt=""
                           on:error={() => { supplierLogoErrors[item.supplierId] = true; supplierLogoErrors = supplierLogoErrors; }} />
                      <span class="doc-supplier-cell__name">{item.supplierName}</span>
                    </span>
                  {:else if item.supplierName}
                    <span class="doc-supplier-cell">
                      <span class="doc-supplier-cell__initials">{supplierInitials(item.supplierName)}</span>
                      <span class="doc-supplier-cell__name">{item.supplierName}</span>
                    </span>
                  {/if}
                  <div class="doc-title-group">
                    <div class="doc-title-row">
                      {#each item.docs as d}
                        {#if d.internal_ref}<span class="doc-iref">{d.internal_ref}</span>{/if}
                      {/each}
                      <span class="doc-title">
                        {item.docs[0].title}
                        {#if item.docs.length > 1}<span class="workflow-row__more">et {item.docs.length - 1} autre{item.docs.length > 2 ? 's' : ''}</span>{/if}
                      </span>
                    </div>
                  </div>
                  <span class="doc-date">{formatDate(item.lastDoc.doc_date)}</span>
                  <span class="workflow-row__chevron">{isOpen ? '▼' : '▶'}</span>
                </div>
                {#if isOpen}
                  <div class="workflow-row__body">
                    {#each item.docs as doc, idx (doc.id)}
                      {#if idx > 0}<div class="workflow-arrow">{'\u2193'}</div>{/if}
                      {@render docRow(doc)}
                    {/each}
                  </div>
                {/if}
              </div>
            {:else}
              {@render docRow(item.doc)}
            {/if}
          {/each}
        {:else if viewMode === 'date'}
          <!-- Pure date mode: every doc is its own row, no folding. -->
          {#each dateOrderedDocs as doc (doc.id)}
            {@render docRow(doc)}
          {/each}
        {:else}
        {#each docGroups as bucket (bucket.key)}
          <div class="supplier-card">
            <div class="supplier-card__header">
              <div class="supplier-card__supplier">
                {#if bucket.supplierId && !supplierLogoErrors[bucket.supplierId]}
                  <img class="supplier-card__logo"
                       src="{API_BASE}/api/suppliers/{bucket.supplierId}/logo" alt=""
                       on:error={() => { supplierLogoErrors[bucket.supplierId] = true; supplierLogoErrors = supplierLogoErrors; }} />
                {:else}
                  <span class="supplier-card__initials">{supplierInitials(bucket.supplierName || '?')}</span>
                {/if}
                <span class="supplier-card__supplier-name">{bucket.supplierName || 'Sans prestataire'}</span>
              </div>
              <span class="supplier-card__count">{bucket.docs.length} document{bucket.docs.length > 1 ? 's' : ''}</span>
            </div>

            {#each bucket.chains as chain, ci (ci)}
              <div class="supplier-card__section">
                {#if bucket.chains.length > 1 || bucket.singletons.length > 0}
                  <div class="supplier-card__section-label">Workflow</div>
                {/if}
                {#each chain as doc, idx (doc.id)}
                  {#if idx > 0}<div class="workflow-arrow">{'\u2193'}</div>{/if}
                  {@render docRow(doc)}
                {/each}
              </div>
            {/each}

            {#if bucket.singletons.length > 0}
              <div class="supplier-card__section">
                {#if bucket.chains.length > 0}
                  <div class="supplier-card__section-label">Documents seuls</div>
                {/if}
                {#each bucket.singletons as doc (doc.id)}
                  {@render docRow(doc)}
                {/each}
              </div>
            {/if}
          </div>
        {/each}
        {/if}
        </div>
      {/if}
    </div>

    <!-- ── Preview Panel (Slide-in) ──────────────────────── -->
    {#if previewDoc}
      <div class="preview-panel">
        <div class="preview-header">
          <div class="preview-header-info">
            <h3 class="preview-title">{previewDoc.title}</h3>
            {#if previewDoc.supplier_name || previewDoc.supplier}
              <span class="preview-supplier">{previewDoc.supplier_name || previewDoc.supplier}</span>
            {/if}
          </div>
          <div class="preview-header-actions">
            {#if previewDoc.file_path}
              <a
                class="btn-secondary btn-small"
                href={getPreviewUrl(previewDoc)}
                target="_blank"
                rel="noopener"
              >Ouvrir</a>
            {/if}
            <button class="modal-close" on:click={closePreview}>✕</button>
          </div>
        </div>

        <div class="preview-content">
          {#if isPdfFile(previewDoc.file_path)}
            <div class="preview-frame-wrap">
              <iframe
                src={getPreviewUrl(previewDoc)}
                class="preview-frame"
                title="Apercu PDF"
              ></iframe>
            </div>
          {:else if isImageFile(previewDoc.file_path)}
            <div class="preview-image-wrap">
              <img
                src={getPreviewUrl(previewDoc)}
                alt={previewDoc.title}
                class="preview-image"
                on:error={(e) => { e.target.style.display = 'none'; }}
              />
            </div>
          {:else}
            <div class="preview-info-card">
              <div class="preview-info-icon">{getFileIcon(previewDoc.file_path)}</div>
              <div class="preview-info-details">
                <div class="preview-info-row">
                  <span class="preview-info-label">Type</span>
                  <span class="preview-info-value">
                    {getFileExtension(previewDoc.file_path).toUpperCase() || 'Inconnu'}
                  </span>
                </div>
                <div class="preview-info-row">
                  <span class="preview-info-label">Categorie</span>
                  <span class="preview-info-value" style="color: {getTypeStyle(previewDoc.doc_type).color}">
                    {getTypeStyle(previewDoc.doc_type).label}
                  </span>
                </div>
                {#if previewDoc.reference}
                  <div class="preview-info-row">
                    <span class="preview-info-label">Reference</span>
                    <span class="preview-info-value">#{previewDoc.reference}</span>
                  </div>
                {/if}
                {#if previewDoc.doc_date}
                  <div class="preview-info-row">
                    <span class="preview-info-label">Date</span>
                    <span class="preview-info-value">{formatDate(previewDoc.doc_date)}</span>
                  </div>
                {/if}
                <div class="preview-info-row">
                  <span class="preview-info-label">Chemin</span>
                  <span class="preview-info-value preview-info-path">{previewDoc.file_path}</span>
                </div>
                {#if previewDoc.notes}
                  <div class="preview-info-row">
                    <span class="preview-info-label">Notes</span>
                    <span class="preview-info-value">{previewDoc.notes}</span>
                  </div>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
</div>

<!-- ── Delete Confirmation ──────────────────────────────── -->
{#if confirmDeleteId}
  <div class="modal-overlay" on:click={() => confirmDeleteId = null}>
    <div class="modal-box modal-small" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Confirmer la suppression</h2>
        <button class="modal-close" on:click={() => confirmDeleteId = null}>✕</button>
      </div>
      <div class="modal-body">
        <p style="color: var(--text-secondary); font-size: 14px;">
          Etes-vous sur de vouloir supprimer ce document ? Cette action est irreversible.
        </p>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" on:click={() => confirmDeleteId = null}>Annuler</button>
        <button class="btn-danger" on:click={() => deleteDocument(confirmDeleteId)}>Supprimer</button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Document Create/Edit Dialog ────────────────────────── -->
{#if showDialog}
  <div class="modal-overlay" on:click={closeDialog}>
    <div class="modal-box" on:click|stopPropagation>
      <div class="modal-header">
        <h2>{editingDoc ? 'Modifier le document' : 'Nouveau document'}</h2>
        <button class="modal-close" on:click={closeDialog}>✕</button>
      </div>
      <div class="modal-body">
        <label class="form-label">
          Titre *
          <input type="text" class="form-input" bind:value={form.title} placeholder="Titre du document" />
        </label>

        <!-- Doc type as pill selector -->
        <div class="form-label">
          Type
          <div class="type-pill-selector">
            {#each Object.entries(DOC_TYPE_COLORS) as [key, val]}
              <button
                class="type-pill"
                class:type-pill-active={form.doc_type === key}
                style="--pill-color: {val.color}; --pill-bg: {val.bg}"
                on:click={() => { form.doc_type = key; }}
              >
                <span class="type-pill-dot" style="background: {val.color}"></span>
                {val.label}
              </button>
            {/each}
          </div>
        </div>

        <div class="form-row">
          <label class="form-label form-half">
            Fournisseur
            <input type="text" class="form-input" bind:value={form.supplier} placeholder="Nom du fournisseur" list="supplier-list" />
            <datalist id="supplier-list">
              {#each supplierList as s}
                <option value={s} />
              {/each}
            </datalist>
          </label>
          <label class="form-label form-half">
            Date
            <input type="date" class="form-input" bind:value={form.doc_date} />
          </label>
        </div>

        <div class="form-row">
          <label class="form-label form-half">
            Reference
            <input type="text" class="form-input" bind:value={form.reference} placeholder="Ex: DEV-2026-001" />
          </label>
          <label class="form-label form-half">
            Tags
            <input type="text" class="form-input" bind:value={form.tags} placeholder="tag1, tag2, ..." />
          </label>
        </div>

        <label class="form-label">
          Chemin du fichier
          <input type="text" class="form-input" bind:value={form.file_path} placeholder="Optionnel (rempli auto lors de l'import)" />
        </label>

        <label class="form-label">
          Notes
          <textarea class="form-input form-textarea" bind:value={form.notes} rows="3" placeholder="Notes optionnelles..."></textarea>
        </label>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" on:click={closeDialog}>Annuler</button>
        <button class="btn-primary" on:click={saveDocument} disabled={!form.title.trim()}>
          {editingDoc ? 'Modifier' : 'Creer'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Import Dialog (after file selection) ───────────────── -->
{#if showImportDialog}
  <div class="modal-overlay" on:click={closeImportDialog}>
    <div class="modal-box" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Importer {pendingFiles.length > 1 ? `${pendingFiles.length} fichiers` : 'un fichier'}</h2>
        <button class="modal-close" on:click={closeImportDialog}>✕</button>
      </div>
      <div class="modal-body">
        <!-- File list preview -->
        <div class="import-file-list">
          {#each pendingFiles.slice(0, 5) as f}
            <div class="import-file-item">
              <span class="import-file-icon">{getFileIcon(f.name)}</span>
              <span class="import-file-name">{f.name}</span>
              <span class="import-file-size">{(f.size / 1024).toFixed(0)} Ko</span>
            </div>
          {/each}
          {#if pendingFiles.length > 5}
            <div class="import-file-more">...et {pendingFiles.length - 5} autres fichiers</div>
          {/if}
        </div>

        {#if pendingFiles.length === 1}
          <label class="form-label">
            Titre
            <input type="text" class="form-input" bind:value={importForm.title} />
          </label>
        {/if}

        <!-- Type pill selector -->
        <div class="form-label">
          Type
          <div class="type-pill-selector">
            {#each Object.entries(DOC_TYPE_COLORS) as [key, val]}
              <button
                class="type-pill"
                class:type-pill-active={importForm.doc_type === key}
                style="--pill-color: {val.color}; --pill-bg: {val.bg}"
                on:click={() => { importForm.doc_type = key; }}
              >
                <span class="type-pill-dot" style="background: {val.color}"></span>
                {val.label}
              </button>
            {/each}
          </div>
        </div>

        <div class="form-row">
          <label class="form-label form-half">
            Fournisseur
            <input type="text" class="form-input" bind:value={importForm.supplier} placeholder="Optionnel" list="supplier-list-import" />
            <datalist id="supplier-list-import">
              {#each supplierList as s}
                <option value={s} />
              {/each}
            </datalist>
          </label>
          <label class="form-label form-half">
            Date
            <input type="date" class="form-input" bind:value={importForm.doc_date} />
          </label>
        </div>

        {#if pendingFiles.length === 1}
          <label class="form-label">
            Reference
            <input type="text" class="form-input" bind:value={importForm.reference} placeholder="Auto-detectee si possible" />
          </label>
        {/if}

        <label class="form-label">
          Tags
          <input type="text" class="form-input" bind:value={importForm.tags} placeholder="tag1, tag2, ..." />
        </label>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" on:click={closeImportDialog}>Annuler</button>
        <button class="btn-primary" on:click={confirmImport}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align: -2px; margin-right: 4px">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          Importer
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Add Link Dialog ──────────────────────────────────── -->
{#if showLinkDialog}
  <!-- Sits on top of the link manager when both are open. -->
  <div class="modal-overlay modal-overlay--top" on:click={closeLinkDialog}>
    <div class="modal-box modal-small" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Ajouter un lien</h2>
        <button class="modal-close" on:click={closeLinkDialog}>✕</button>
      </div>
      <div class="modal-body">
        <label class="form-label">
          Type de lien
          <select class="form-input" bind:value={linkForm.link_type}>
            {#each LINK_TYPES as lt}
              <option value={lt.value}>{lt.label}</option>
            {/each}
          </select>
        </label>

        <label class="form-label">
          Document cible
          <select class="form-input" bind:value={linkForm.target_id}>
            <option value="">— Sélectionner un document —</option>
            {#each documents.filter(d => d.id !== linkSourceDocId) as d}
              <option value={d.id}>{d.title} ({getTypeStyle(d.doc_type).label})</option>
            {/each}
          </select>
        </label>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" on:click={closeLinkDialog}>Annuler</button>
        <button class="btn-primary" on:click={createLink} disabled={!linkForm.target_id}>
          Creer le lien
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Link Manager (per-doc) ─────────────────────────────────────── -->
{#if showLinkManager}
  {@const managedDoc = documents.find(d => d.id === linkManagerDocId)}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-overlay" on:click={() => { showLinkManager = false; }}>
    <div class="modal-box" on:click|stopPropagation style="max-width:520px">
      <div class="modal-header">
        <h2>Liens du document</h2>
        <button class="modal-close" on:click={() => { showLinkManager = false; }}>{'\u2715'}</button>
      </div>
      <div class="modal-body">
        {#if managedDoc}
          <div class="link-manager__doc">
            <span class="doc-type-badge"
                  style="background: {getTypeStyle(managedDoc.doc_type).bg}; color: {getTypeStyle(managedDoc.doc_type).color}; border: 1px solid {getTypeStyle(managedDoc.doc_type).color}40">
              {getTypeStyle(managedDoc.doc_type).label || managedDoc.doc_type}
            </span>
            <span class="link-manager__title">{managedDoc.title}</span>
          </div>
        {/if}

        <div class="link-manager__section-label">Liens existants</div>
        {#if linkManagerLoading}
          <p class="empty-text" style="padding:0.5rem 0">Chargement…</p>
        {:else if linkManagerLinks.length === 0}
          <p class="empty-text" style="padding:0.5rem 0">Aucun lien pour ce document.</p>
        {:else}
          <div class="link-manager__list">
            {#each linkManagerLinks as link}
              {@const otherId = link.source_id === linkManagerDocId ? link.target_id : link.source_id}
              {@const otherDoc = documents.find(d => d.id === otherId)}
              <div class="link-manager__item">
                <span class="link-manager__type-tag">{getLinkTypeLabel(link.link_type)}</span>
                {#if otherDoc}
                  <span class="doc-type-badge"
                        style="background: {getTypeStyle(otherDoc.doc_type).bg}; color: {getTypeStyle(otherDoc.doc_type).color}; border: 1px solid {getTypeStyle(otherDoc.doc_type).color}40">
                    {getTypeStyle(otherDoc.doc_type).label || otherDoc.doc_type}
                  </span>
                  <span class="link-manager__other-title">{otherDoc.title}</span>
                {:else}
                  <span class="link-manager__other-title">Document #{otherId}</span>
                {/if}
                <button class="btn-icon btn-icon-danger" on:click={() => removeLinkFromManager(link.id)} title="Retirer ce lien">{'\u2715'}</button>
              </div>
            {/each}
          </div>
        {/if}

        <div style="margin-top:1rem">
          <button class="btn-primary" on:click={openAddLinkFromManager}>+ Lier à un autre document</button>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-ghost" on:click={() => { showLinkManager = false; }}>Fermer</button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* ── Page ──────────────────────────────────────────────── */
  .documents-page {
    animation: fadeIn 0.35s ease-out;
    position: relative;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  @keyframes slideInFromRight {
    from { opacity: 0; transform: translateX(30px); }
    to   { opacity: 1; transform: translateX(0); }
  }

  @keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 40px rgba(var(--accent-rgb), 0.2); }
    50%      { box-shadow: 0 0 60px rgba(var(--accent-rgb), 0.35); }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @keyframes expandIn {
    from { opacity: 0; max-height: 0; }
    to   { opacity: 1; max-height: 600px; }
  }

  /* ── Drag & Drop Overlay ────────────────────────────────── */
  .drop-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(8px);
    z-index: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.2s ease-out;
  }

  .drop-zone {
    border: 3px dashed var(--accent);
    border-radius: 0.625rem;
    padding: 60px 80px;
    text-align: center;
    background: rgba(var(--accent-rgb), 0.06);
    box-shadow: 0 0 40px rgba(var(--accent-rgb), 0.2);
    animation: pulse-glow 2s ease-in-out infinite;
  }

  .drop-icon-ring {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    border: 2px solid var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px;
    background: rgba(var(--accent-rgb), 0.1);
  }

  .drop-title {
    font-size: 1.375rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 6px;
  }

  .drop-subtitle {
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  /* ── Upload Progress ────────────────────────────────────── */
  .upload-progress-bar {
    position: relative;
    height: 32px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 0.625rem;
    margin-bottom: 14px;
    overflow: hidden;
  }

  .upload-progress-fill {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, rgba(var(--accent-rgb), 0.3), rgba(var(--accent-rgb), 0.5));
    transition: width 0.4s ease;
    border-radius: 0.625rem;
  }

  .upload-progress-text {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  /* ── Stats bar (uses global ya-kpi-row) ───────────────── */

  /* ── Action bar ────────────────────────────────────────── */
  .action-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }

  .action-left, .action-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-primary {
    background: var(--accent);
    border: none;
    border-radius: 0.625rem;
    color: #fff;
    font-size: 0.8125rem;
    font-weight: 600;
    padding: 7px 16px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    box-shadow: 0 2px 12px rgba(var(--accent-rgb), 0.3);
    display: inline-flex;
    align-items: center;
    text-decoration: none;
  }

  .btn-primary:hover {
    filter: brightness(1.15);
    box-shadow: 0 4px 20px rgba(var(--accent-rgb), 0.4);
  }

  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    color: var(--text-secondary);
    font-size: 0.8125rem;
    font-weight: 500;
    padding: 7px 14px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
    display: inline-flex;
    align-items: center;
    text-decoration: none;
  }

  .btn-secondary:hover {
    border-color: var(--accent);
    color: var(--text-primary);
    background: rgba(var(--accent-rgb), 0.06);
  }

  .btn-small {
    font-size: 0.75rem;
    padding: 4px 12px;
  }

  .filter-select {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    color: var(--text-primary);
    font-size: 0.8125rem;
    padding: 6px 10px;
    font-family: inherit;
    cursor: pointer;
    outline: none;
  }

  .filter-select:focus {
    border-color: var(--accent);
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-icon-svg {
    position: absolute;
    left: 10px;
    pointer-events: none;
  }

  .search-input {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    color: var(--text-primary);
    font-size: 0.8125rem;
    padding: 6px 10px 6px 32px;
    width: 200px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s, width 0.2s;
  }

  .search-input:focus {
    border-color: var(--accent);
    width: 260px;
  }

  /* ── Content Layout (list + preview) ─────────────────────── */
  .content-layout {
    display: flex;
    gap: 16px;
    min-height: 0;
  }

  .doc-list-area {
    flex: 1;
    min-width: 0;
    overflow-y: auto;
    max-height: calc(100vh - 240px);
    padding-right: 4px;
  }

  /* Supplier identity inside a doc row (compact, kept on a single line) */
  .doc-supplier-cell {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 2px 8px 2px 4px;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border-subtle, rgba(255,255,255,0.08));
    border-radius: 999px;
    flex-shrink: 0;
  }
  .doc-supplier-cell__logo {
    width: 18px; height: 18px; border-radius: 4px; object-fit: contain;
    background: rgba(255,255,255,0.05);
  }
  .doc-supplier-cell__initials {
    width: 18px; height: 18px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(136,105,225,0.15); color: var(--primary, #8869e1);
    font-size: 9px; font-weight: 700;
  }
  .doc-supplier-cell__name {
    font-size: 11px; font-weight: 600;
    color: var(--text-secondary, #C0C8D6); white-space: nowrap;
    max-width: 140px; overflow: hidden; text-overflow: ellipsis;
  }
  /* Brief highlight when arriving via cross-page navigation (e.g. from Suppliers) */
  .doc-row--flash { animation: doc-flash 1.5s ease-out; }
  @keyframes doc-flash {
    0%   { background: rgba(136,105,225,0.25); box-shadow: 0 0 0 2px var(--primary, #8869e1); }
    100% { background: var(--bg-card); box-shadow: none; }
  }

  /* Inline tags shown under the title — small chip-style for readability at scale */
  .doc-tags-inline {
    display: inline-flex; flex-wrap: wrap; gap: 4px;
    font-size: 10px; color: var(--text-muted, #94A3B8);
    margin-top: 2px;
  }

  /* Internal reference — auto-generated, primary identifier */
  .doc-iref {
    display: inline-block;
    font-family: 'Consolas', monospace;
    font-size: 11px; font-weight: 700;
    color: var(--primary, #8869e1);
    background: rgba(136,105,225,0.1);
    border: 1px solid rgba(136,105,225,0.25);
    padding: 1px 6px; border-radius: 4px;
    margin-right: 6px; white-space: nowrap;
  }
  .doc-title-row { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }

  /* Workflow row visual consistency: same grid as singles, purple variants */
  .doc-row--workflow .doc-main { cursor: pointer; }
  .doc-type-badge--workflow {
    background: rgba(136,105,225,0.12) !important;
    color: var(--primary, #8869e1) !important;
    border: 1px solid rgba(136,105,225,0.4) !important;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .doc-title--workflow {
    color: var(--text-secondary, #C0C8D6) !important;
    font-family: 'Consolas', monospace;
    font-size: 12px;
  }
  .workflow-row__more {
    color: var(--text-muted, #94A3B8); font-size: 11px;
    font-style: italic; margin-left: 4px;
  }
  .workflow-row__chevron {
    color: var(--text-muted, #94A3B8); font-size: 10px;
    width: 14px; flex-shrink: 0; text-align: center;
  }

  /* Custom toolbar: Importer | Search (grow) | filters spread to the right */
  .docs-toolbar {
    display: flex; align-items: center; gap: 0.625rem;
    flex-wrap: wrap; margin-bottom: 1rem;
  }
  .docs-toolbar__import { flex-shrink: 0; }
  .docs-toolbar__search {
    flex: 1 1 280px; min-width: 240px;
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-input, rgba(255,255,255,0.03));
    border: 1px solid var(--border-subtle, rgba(255,255,255,0.08));
    border-radius: 0.625rem;
  }
  .docs-toolbar__search:focus-within {
    border-color: var(--primary, #8869e1);
    box-shadow: 0 0 0 0.25rem rgba(136,105,225,0.15);
  }
  .docs-toolbar__search input {
    flex: 1 1 auto; min-width: 0;
    background: transparent; border: none; outline: none;
    color: var(--text-primary, #E6EAF2);
    font-size: 0.8125rem; font-family: inherit;
  }

  /* View-mode select sized for full labels */
  .view-mode-select { min-width: 170px; }

  /* View toggle button in the toolbar */
  .view-toggle {
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--bg-card, rgba(255,255,255,0.04));
    border: 1px solid var(--border-card, rgba(255,255,255,0.1));
    color: var(--text, #E6EAF2);
    padding: 6px 10px; border-radius: 6px; cursor: pointer;
    font-size: 12px; font-weight: 600; white-space: nowrap;
  }
  .view-toggle:hover { background: rgba(136,105,225,0.12); border-color: var(--primary, #8869e1); }

  /* ── Flat-mode workflow row (folded one-line summary) ───── */
  .workflow-row {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-left: 3px solid var(--primary, #8869e1);
    border-radius: 0.5rem;
    margin-bottom: 6px;
    overflow: hidden;
    transition: border-color 0.2s, box-shadow 0.25s;
  }
  .workflow-row:hover { border-color: var(--border-hover); }
  .workflow-row--open { box-shadow: 0 0 18px rgba(136,105,225,0.12); }
  .workflow-row__head {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 12px; cursor: pointer; user-select: none;
  }
  .workflow-row__chevron { color: var(--text-muted, #94A3B8); font-size: 10px; width: 14px; flex-shrink: 0; }
  .workflow-row__icon { font-size: 14px; flex-shrink: 0; }
  .workflow-row__logo {
    width: 22px; height: 22px; border-radius: 4px; object-fit: contain;
    background: rgba(255,255,255,0.05); flex-shrink: 0;
  }
  .workflow-row__initials {
    width: 22px; height: 22px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(136,105,225,0.15); color: var(--primary, #8869e1);
    font-size: 10px; font-weight: 700; flex-shrink: 0;
  }
  .workflow-row__supplier { font-weight: 600; font-size: 13px; color: var(--text, #E6EAF2); flex-shrink: 0; }
  .workflow-row__sep { color: var(--text-muted, #94A3B8); flex-shrink: 0; }
  .workflow-row__summary {
    flex: 1; min-width: 0; font-size: 12px; color: var(--text-secondary, #C0C8D6);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .workflow-row__count {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    color: var(--primary, #8869e1);
    background: rgba(136,105,225,0.12); padding: 2px 8px; border-radius: 1rem;
    flex-shrink: 0;
  }
  .workflow-row__date {
    font-size: 11px; color: var(--text-muted, #94A3B8);
    font-family: 'Consolas', monospace; flex-shrink: 0;
  }
  .workflow-row__body {
    padding: 8px 10px 10px; background: var(--bg-base, #0F1115);
    border-top: 1px dashed rgba(255,255,255,0.08);
  }

  /* ── Supplier card (one card per supplier) ────────────────── */
  .doc-list-clickable { display: block; min-height: 60px; }
  .supplier-card {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.75rem;
    margin-bottom: 12px;
    padding: 12px 14px 8px;
    transition: border-color 0.2s, box-shadow 0.25s;
  }
  .supplier-card:hover {
    border-color: var(--border-hover);
    box-shadow: 0 0 16px rgba(var(--accent-rgb), 0.08), 0 4px 12px rgba(0, 0, 0, 0.15);
  }
  .supplier-card__header {
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px; padding-bottom: 10px;
    border-bottom: 1px dashed rgba(255,255,255,0.08);
    margin-bottom: 10px;
  }
  .supplier-card__supplier { display: flex; align-items: center; gap: 10px; }
  .supplier-card__logo {
    width: 32px; height: 32px; border-radius: 6px; object-fit: contain;
    background: rgba(255,255,255,0.05); padding: 2px;
  }
  .supplier-card__initials {
    width: 32px; height: 32px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    background: rgba(136,105,225,0.15); color: var(--primary, #8869e1);
    font-size: 12px; font-weight: 700;
  }
  .supplier-card__supplier-name {
    font-weight: 600; font-size: 14px; color: var(--text, #E6EAF2);
  }
  .supplier-card__count {
    font-size: 11px; font-weight: 600;
    color: var(--text-muted, #94A3B8); text-transform: uppercase; letter-spacing: 0.04em;
    background: rgba(255,255,255,0.04); padding: 3px 8px; border-radius: 1rem;
    border: 1px solid rgba(255,255,255,0.08);
  }
  .supplier-card__section { margin-bottom: 8px; }
  .supplier-card__section:last-child { margin-bottom: 0; }
  .supplier-card__section-label {
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--text-muted, #94A3B8);
    margin: 4px 4px 6px;
  }
  .workflow-arrow {
    text-align: center; color: var(--text-muted, #94A3B8);
    font-size: 14px; padding: 2px 0; user-select: none;
  }

  /* Cross-supplier link chip in a doc row */
  .doc-cross-link {
    background: rgba(255,255,255,0.04);
    border: 1px solid; border-radius: 999px;
    padding: 2px 8px; font-size: 10px; font-weight: 600;
    cursor: pointer; white-space: nowrap;
  }
  .doc-cross-link:hover { background: rgba(255,255,255,0.08); }

  /* Link manager dialog */
  .link-manager__doc {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 10px; background: rgba(255,255,255,0.04);
    border-radius: 6px; margin-bottom: 12px;
  }
  .link-manager__title { font-weight: 600; color: var(--text, #E6EAF2); }
  .link-manager__section-label {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    color: var(--text-muted, #94A3B8); margin-bottom: 6px;
  }
  .link-manager__list { display: flex; flex-direction: column; gap: 6px; }
  .link-manager__item {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 10px; background: var(--bg-base, #0F1115);
    border: 1px solid var(--border-subtle, rgba(255,255,255,0.08));
    border-radius: 6px;
  }
  .link-manager__type-tag {
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    color: var(--text-muted, #94A3B8);
    background: rgba(255,255,255,0.04);
    padding: 2px 6px; border-radius: 4px; white-space: nowrap;
  }
  .link-manager__other-title {
    flex: 1; color: var(--text, #E6EAF2); font-size: 13px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  /* ── Document rows ──────────────────────────────────────── */
  .doc-row {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    margin-bottom: 6px;
    overflow: hidden;
    transition: border-color 0.2s, box-shadow 0.25s;
  }

  .doc-row:hover {
    border-color: var(--border-hover);
    box-shadow: 0 0 16px rgba(var(--accent-rgb), 0.1), 0 4px 12px rgba(0, 0, 0, 0.2);
  }

  .doc-row-expanded {
    box-shadow: 0 0 20px rgba(var(--accent-rgb), 0.1), 0 4px 16px rgba(0, 0, 0, 0.25);
  }

  .doc-row-selected {
    border-color: var(--accent) !important;
    box-shadow: 0 0 20px rgba(var(--accent-rgb), 0.15);
  }

  .doc-main {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    cursor: pointer;
    min-height: 44px;
  }

  .doc-file-icon {
    font-size: 1rem;
    flex-shrink: 0;
    width: 24px;
    text-align: center;
  }

  .doc-type-badge {
    font-size: 0.6875rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 0.625rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .doc-title-group {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .doc-title {
    font-size: 0.875rem;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .doc-supplier-prominent {
    font-size: 0.75rem;
    color: var(--accent);
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .doc-date {
    font-size: 0.6875rem;
    color: var(--text-muted);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .doc-ref {
    font-size: 0.6875rem;
    color: var(--text-muted);
    background: var(--bg-card);
    padding: 2px 8px;
    border-radius: 0.625rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .doc-ext-badge {
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    background: var(--bg-card);
    padding: 2px 6px;
    border-radius: 0.625rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .doc-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
    opacity: 0.6;
    transition: opacity 0.15s;
  }

  .doc-main:hover .doc-actions,
  .doc-row-expanded .doc-actions {
    opacity: 1;
  }

  .btn-icon {
    background: none;
    border: none;
    cursor: pointer;
    padding: 5px;
    border-radius: 0.625rem;
    transition: background 0.15s, color 0.15s;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .btn-icon:hover {
    background: var(--bg-card);
  }

  .btn-icon-preview:hover {
    background: rgba(var(--accent-rgb), 0.15);
    color: var(--accent);
  }

  .btn-icon-danger:hover {
    background: rgba(239, 68, 68, 0.15);
    color: #EF4444;
  }

  /* ── Expanded area ──────────────────────────────────────── */
  .doc-expanded {
    border-top: 1px solid var(--border-subtle);
    padding: 14px;
    background: var(--bg-card);
    animation: expandIn 0.25s ease-out;
    overflow: hidden;
  }

  .expanded-section {
    margin-bottom: 14px;
  }

  .expanded-section:last-child {
    margin-bottom: 0;
  }

  .expanded-label {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted);
    margin-bottom: 6px;
  }

  .notes-display {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    padding: 6px 10px;
    border: 1px dashed var(--border-subtle);
    border-radius: 0.625rem;
    min-height: 36px;
    white-space: pre-wrap;
  }

  .file-path {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    padding: 6px 10px;
    background: var(--bg-card);
    border-radius: 0.625rem;
    font-family: 'Consolas', monospace;
    word-break: break-all;
  }

  .tags-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .tag-chip {
    font-size: 0.6875rem;
    background: rgba(var(--accent-rgb), 0.15);
    color: var(--accent);
    padding: 2px 10px;
    border-radius: 0.625rem;
    border: 1px solid rgba(var(--accent-rgb), 0.3);
  }

  /* ── Chain Bar ──────────────────────────────────────────── */
  .chain-bar-section {
    margin-bottom: 16px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .chain-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 8px 0;
  }

  .chain-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 12px;
    border-radius: 0.625rem;
    font-size: 0.75rem;
    font-weight: 600;
    font-family: inherit;
    white-space: nowrap;
    transition: all 0.15s;
    border: none;
    cursor: default;
  }

  .chain-pill-current {
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
  }

  .chain-pill-linked {
    background: transparent;
    border: 1.5px solid;
    cursor: pointer;
  }

  .chain-pill-linked:hover {
    transform: translateY(-1px);
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.2);
  }

  .chain-pill-icon {
    font-size: 0.8125rem;
  }

  .chain-pill-type {
    font-size: 0.625rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    opacity: 0.85;
  }

  .chain-pill-title {
    font-size: 0.75rem;
    font-weight: 500;
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .chain-arrow {
    color: var(--text-muted);
    font-size: 1rem;
    font-weight: 300;
    user-select: none;
  }

  .chain-pill-wrapper {
    position: relative;
    display: inline-flex;
    align-items: center;
  }

  .chain-pill-remove {
    position: absolute;
    top: -6px;
    right: -6px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #EF4444;
    color: #fff;
    border: 2px solid var(--bg-card);
    font-size: 0.75rem;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s, transform 0.15s;
    transform: scale(0.8);
  }

  .chain-pill-wrapper:hover .chain-pill-remove {
    opacity: 1;
    transform: scale(1);
  }

  .chain-add-btn {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px dashed var(--border-subtle);
    background: transparent;
    color: var(--text-muted);
    font-size: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .chain-add-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(var(--accent-rgb), 0.08);
  }

  .chain-loading {
    color: var(--text-muted);
    font-size: 0.875rem;
    animation: fadeIn 0.3s;
  }

  /* ── Preview Panel ──────────────────────────────────────── */
  .content-layout.has-preview .doc-list-area {
    flex: 1 1 55%;
  }

  .preview-panel {
    flex: 0 0 440px;
    background: var(--bg-card);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    max-height: calc(100vh - 240px);
    animation: slideInFromRight 0.3s ease-out;
  }

  .preview-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--border-subtle);
    flex-shrink: 0;
    gap: 12px;
  }

  .preview-header-info {
    min-width: 0;
    flex: 1;
  }

  .preview-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .preview-title {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .preview-supplier {
    font-size: 0.75rem;
    color: var(--accent);
    font-weight: 500;
  }

  .preview-content {
    flex: 1;
    overflow: auto;
    padding: 12px;
  }

  .preview-frame-wrap {
    width: 100%;
    height: 100%;
    min-height: 500px;
  }

  .preview-frame {
    width: 100%;
    height: 100%;
    min-height: 500px;
    border: none;
    border-radius: 0.625rem;
    background: var(--bg-card);
  }

  .preview-image-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px;
  }

  .preview-image {
    max-width: 100%;
    max-height: 500px;
    border-radius: 0.625rem;
    object-fit: contain;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  }

  .preview-info-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    padding: 20px;
  }

  .preview-info-icon {
    font-size: 3.5rem;
  }

  .preview-info-details {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .preview-info-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 10px;
    background: var(--bg-card);
    border-radius: 0.625rem;
    border: 1px solid var(--border-subtle);
  }

  .preview-info-label {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .preview-info-value {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-align: right;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .preview-info-path {
    font-family: 'Consolas', monospace;
    font-size: 0.6875rem;
  }

  /* ── Loading / Empty ────────────────────────────────────── */
  .loading-msg {
    text-align: center;
    padding: 60px 40px;
    color: var(--text-muted);
    font-size: 0.875rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  .loading-spinner {
    width: 28px;
    height: 28px;
    border: 3px solid var(--border-subtle);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  .empty-msg {
    text-align: center;
    padding: 60px 40px;
    color: var(--text-muted);
    font-size: 0.875rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .empty-icon {
    opacity: 0.4;
    margin-bottom: 8px;
  }

  .empty-hint {
    font-size: 0.75rem;
    color: var(--text-muted);
    opacity: 0.7;
  }

  /* ── Modal ──────────────────────────────────────────────── */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(4px);
    animation: fadeIn 0.15s ease-out;
  }
  /* Used when a second dialog needs to sit ABOVE another modal (e.g., link picker over link manager) */
  .modal-overlay--top { z-index: 1100;
  }

  .modal-box {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    width: 560px;
    max-width: 95vw;
    max-height: 90vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  }

  .modal-small {
    width: 420px;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 24px 0;
  }

  .modal-header h2 {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }

  .modal-close {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 1.125rem;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 0.625rem;
    transition: background 0.15s;
  }

  .modal-close:hover {
    background: var(--bg-card);
    color: var(--text-primary);
  }

  .modal-body {
    padding: 18px 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .modal-footer {
    padding: 0 24px 18px;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    color: var(--text-secondary);
    font-size: 0.8125rem;
    padding: 6px 14px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }

  .btn-ghost:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
    color: var(--text-primary);
  }

  .btn-danger {
    background: #EF4444;
    border: none;
    border-radius: 0.625rem;
    color: #fff;
    font-size: 0.8125rem;
    font-weight: 600;
    padding: 7px 16px;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }

  .btn-danger:hover {
    filter: brightness(1.15);
  }

  /* ── Form ───────────────────────────────────────────────── */
  .form-label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .form-input {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    color: var(--text-primary);
    font-size: 0.8125rem;
    padding: 8px 10px;
    font-family: inherit;
    outline: none;
    transition: border-color 0.15s, background 0.15s;
  }

  .form-input:focus {
    border-color: var(--accent);
    background: var(--bg-card);
  }

  .form-textarea {
    resize: vertical;
  }

  .form-row {
    display: flex;
    gap: 12px;
  }

  .form-half {
    flex: 1;
  }

  /* ── Type Pill Selector ─────────────────────────────────── */
  .type-pill-selector {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 2px;
  }

  .type-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 14px;
    border-radius: 0.625rem;
    border: 1.5px solid var(--border-card);
    background: transparent;
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    font-family: inherit;
  }

  .type-pill:hover {
    border-color: var(--pill-color);
    color: var(--pill-color);
  }

  .type-pill-active {
    border-color: var(--pill-color) !important;
    background: var(--pill-bg) !important;
    color: var(--pill-color) !important;
    font-weight: 600;
  }

  .type-pill-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* ── Import File List ───────────────────────────────────── */
  .import-file-list {
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 0.625rem;
    padding: 10px;
    max-height: 160px;
    overflow-y: auto;
  }

  .import-file-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 6px;
    border-radius: 0.625rem;
    transition: background 0.1s;
  }

  .import-file-item:hover {
    background: var(--bg-card);
  }

  .import-file-icon {
    font-size: 0.875rem;
    flex-shrink: 0;
  }

  .import-file-name {
    flex: 1;
    font-size: 0.8125rem;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .import-file-size {
    font-size: 0.6875rem;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .import-file-more {
    text-align: center;
    font-size: 0.75rem;
    color: var(--text-muted);
    padding: 6px;
    font-style: italic;
  }
</style>
