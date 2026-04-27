<script>
  import { onMount } from 'svelte';
  import { api, API_BASE } from '../api/client.js';

  // Track which supplier logos failed to load so we can fall back to initials
  let supplierLogoErrors = {};
  function supplierInitials(name) {
    if (!name) return '??';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }
  import { success, error as toastError } from '../stores/toast.js';

  // ── State ──
  let projects = [];
  let loading = true;
  let selectedProject = null;
  let detailLoading = false;

  // Dialog
  let showDialog = false;
  let editingProject = null;
  let form = { title: '', description: '', status: 'not_started', color: '#3B82F6', start_date: '', end_date: '', budget: 0, budget_spent: 0 };
  let saving = false;

  // Task dialog (shared between create and edit)
  let showTaskDialog = false;
  let editingTaskId = null; // null = create; number = edit
  let taskForm = { title: '', priority: 2, start_date: '', due_date: '', notes: '', site: '', is_milestone: false };

  // Note
  let noteText = '';

  // Budget panel
  let showBudgetPanel = false;

  // Gantt zoom: 'auto' lets the data pick the span; 'day'/'week'/'month' force a window centered on today
  let ganttZoom = 'auto';
  const GANTT_ZOOMS = [
    { value: 'auto',  label: 'Auto'     },
    { value: 'day',   label: 'Jour'     },
    { value: 'week',  label: 'Semaine'  },
    { value: 'month', label: 'Mois'     },
  ];

  // Budget computed values
  // Classification: factures → Facturé (argent dû) ; devis/BPA/proposition acceptés → Engagé (argent promis)
  // Doc types in DB are uppercase: DEVIS / FACTURE / CONTRAT / BON (Bon pour accord = BPA) / RAPPORT / AUTRE
  function isFacture(doc) {
    const t = (doc.doc_type || '').toLowerCase();
    return t === 'facture';
  }
  function isEngageable(doc) {
    const t = (doc.doc_type || '').toLowerCase();
    return t === 'devis' || t === 'bon' || t === 'bpa' || t === 'proposition';
  }
  function docValue(doc) {
    // Validated amount if set (after negotiation), fallback to initial
    return doc.amount_accepted > 0 ? doc.amount_accepted : (doc.amount || 0);
  }

  $: budgetDocs = (selectedProject?.documents || []).filter(d => d.amount > 0 || d.amount_accepted > 0);
  // Factures = real money owed (count all, regardless of status)
  $: budgetFactureDocs = budgetDocs.filter(isFacture);
  $: budgetFacture = budgetFactureDocs.reduce((s, d) => s + docValue(d), 0);
  // Engagé = accepted quotes/BPA/proposals (money committed)
  $: budgetEngageDocs = budgetDocs.filter(d => isEngageable(d) && d.status === 'accepte');
  $: budgetEngage = budgetEngageDocs.reduce((s, d) => s + docValue(d), 0);
  // Pending quotes (informational)
  $: budgetAttenteDocs = budgetDocs.filter(d => isEngageable(d) && (d.status === 'en attente' || !d.status));
  $: budgetAttente = budgetAttenteDocs.reduce((s, d) => s + docValue(d), 0);
  // Refused (informational, not counted)
  $: budgetNbRefuse = budgetDocs.filter(d => d.status === 'refuse').length;
  // Consumed budget = max(Engagé, Facturé) to avoid double-counting a quote + its invoice
  $: budgetConsomme = Math.max(budgetEngage, budgetFacture);
  $: budgetPrevu = selectedProject?.budget || 0;
  $: budgetResteAEngager = Math.max(0, budgetPrevu - budgetEngage);
  $: budgetResteAFacturer = Math.max(0, budgetEngage - budgetFacture);

  // Edit document amounts
  let editingDocLink = null;
  let editDocForm = { amount: 0, amount_accepted: 0, status: '' };

  function openEditDocLink(doc) {
    editingDocLink = doc;
    editDocForm = { amount: doc.amount || 0, amount_accepted: doc.amount_accepted || 0, status: doc.status || '' };
  }

  async function saveEditDocLink() {
    if (!editingDocLink) return;
    try {
      await api.put(`/api/projects/${selectedProject.id}/documents/${editingDocLink.id}`, editDocForm);
      editingDocLink = null;
      await openProject(selectedProject);
      success('Montant mis a jour');
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  // Link dialogs
  let showLinkDocDialog = false;
  let showLinkSupDialog = false;
  let allDocuments = [];
  let allSuppliers = [];

  // Confirm delete
  let confirmDeleteId = null;

  const STATUSES = [
    { value: 'not_started', label: 'Pas demarre', color: '#94A3B8' },
    { value: 'in_progress', label: 'En cours', color: '#3B82F6' },
    { value: 'paused', label: 'En pause', color: '#F59E0B' },
    { value: 'completed', label: 'Termine', color: '#22C55E' },
  ];

  // Keep in sync with TasksPage.SITES
  const SITES = [
    { value: '', label: '— Aucun —' },
    { value: 'NDK', label: '\u{1F3EB} NDK' },
    { value: 'NDE', label: '\u{1F3EB} NDE' },
    { value: 'SU', label: '\u{1F3EB} SU' },
    { value: 'Global', label: '\u{1F310} Global' },
  ];

  const COLORS = ['#3B82F6', '#8B5CF6', '#22C55E', '#F59E0B', '#EF4444', '#EC4899', '#06B6D4', '#8869e1'];

  function statusInfo(s) { return STATUSES.find(st => st.value === s) || STATUSES[0]; }

  // ── Load ──
  async function fetchProjects() {
    loading = true;
    try {
      projects = await api.get('/api/projects');
    } catch { projects = []; }
    loading = false;
  }

  async function openProject(p) {
    detailLoading = true;
    selectedProject = p;
    try {
      selectedProject = await api.get(`/api/projects/${p.id}`);
    } catch (e) { toastError('Erreur: ' + e.message); }
    detailLoading = false;
  }

  function backToList() {
    selectedProject = null;
    fetchProjects();
  }

  // ── CRUD ──
  function openNewDialog() {
    editingProject = null;
    form = { title: '', description: '', status: 'not_started', color: '#3B82F6', start_date: '', end_date: '', budget: 0, budget_spent: 0 };
    showDialog = true;
  }

  function openEditDialog() {
    if (!selectedProject) return;
    editingProject = selectedProject;
    form = {
      title: selectedProject.title, description: selectedProject.description,
      status: selectedProject.status, color: selectedProject.color,
      start_date: selectedProject.start_date, end_date: selectedProject.end_date,
      budget: selectedProject.budget || 0, budget_spent: selectedProject.budget_spent || 0,
    };
    showDialog = true;
  }

  async function saveProject() {
    saving = true;
    try {
      if (editingProject) {
        await api.put(`/api/projects/${editingProject.id}`, form);
        success('Projet modifie');
        await openProject({ id: editingProject.id });
      } else {
        const result = await api.post('/api/projects', form);
        success('Projet cree');
        await fetchProjects();
      }
      showDialog = false;
    } catch (e) { toastError('Erreur: ' + e.message); }
    saving = false;
  }

  async function deleteProject(id) {
    try {
      await api.delete(`/api/projects/${id}`);
      success('Projet supprime');
      confirmDeleteId = null;
      if (selectedProject?.id === id) backToList();
      else await fetchProjects();
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  // Duplicate: ask for a title and create a clone (tasks reset, document links pending)
  let duplicating = false;
  async function duplicateProject() {
    if (!selectedProject || duplicating) return;
    const suggested = `${selectedProject.title} (copie)`;
    const title = window.prompt('Titre du projet dupliqué :', suggested);
    if (title === null) return; // user cancelled
    duplicating = true;
    try {
      const res = await api.post(`/api/projects/${selectedProject.id}/duplicate`, { title: title.trim() || suggested });
      success('Projet duplique');
      await openProject({ id: res.id });
    } catch (e) { toastError('Erreur: ' + e.message); }
    duplicating = false;
  }

  // ── Tasks ──
  function openNewTaskDialog() {
    editingTaskId = null;
    taskForm = { title: '', priority: 2, start_date: '', due_date: '', notes: '', site: '', is_milestone: false };
    showTaskDialog = true;
  }

  function openEditTaskDialog(task) {
    editingTaskId = task.id;
    taskForm = {
      title: task.title || '',
      priority: task.priority ?? 2,
      start_date: task.start_date || '',
      due_date: task.due_date || '',
      notes: task.notes || '',
      site: task.site || '',
      is_milestone: !!task.is_milestone,
    };
    showTaskDialog = true;
  }

  async function saveTask() {
    if (!taskForm.title.trim()) return;
    try {
      if (editingTaskId) {
        // Update existing: PUT /api/tasks/{id} — needs category/recurrence (send empty to keep)
        const existing = (selectedProject.tasks || []).find(t => t.id === editingTaskId) || {};
        await api.put(`/api/tasks/${editingTaskId}`, {
          title: taskForm.title,
          category: existing.category || '',
          priority: taskForm.priority,
          due_date: taskForm.due_date || null,
          start_date: taskForm.start_date || null,
          notes: taskForm.notes,
          site: taskForm.site,
          recurrence: existing.recurrence || '',
          is_milestone: taskForm.is_milestone,
        });
        success('Tache modifiee');
      } else {
        await api.post(`/api/projects/${selectedProject.id}/tasks`, taskForm);
        success('Tache ajoutee');
      }
      showTaskDialog = false;
      editingTaskId = null;
      await openProject(selectedProject);
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  async function toggleTask(task) {
    // Warn (but don't block) if the task has unresolved dependencies and is being marked done
    if (!task.done && task.blocked) {
      const pending = (task.dependencies || []).filter(d => !d.done).map(d => d.title).join(', ');
      const ok = window.confirm(`Cette tache est bloquee par des dependances non terminees :\n\n${pending}\n\nMarquer quand meme comme terminee ?`);
      if (!ok) return;
    }
    try {
      await api.patch(`/api/tasks/${task.id}/done`);
      await openProject(selectedProject);
    } catch (e) { console.error('Toggle task failed:', e); }
  }

  async function deleteTask(taskId) {
    // Fully delete the task (also removes it from the global Tasks module).
    // Unlinking kept the task around with project_id=NULL, which created orphan tasks
    // the user never wanted.
    try {
      await api.delete(`/api/tasks/${taskId}`);
      await openProject(selectedProject);
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  // ── Task dependencies ──
  let depsTask = null;      // the task currently being edited (parent)
  let depsPickId = null;    // the task to add as dependency

  function openDepsDialog(task) {
    depsTask = task;
    depsPickId = null;
  }

  async function addDependency() {
    if (!depsTask || !depsPickId) return;
    try {
      await api.post(`/api/projects/${selectedProject.id}/tasks/${depsTask.id}/dependencies`, { depends_on_task_id: parseInt(depsPickId) });
      await openProject(selectedProject);
      // re-point to the refreshed task instance so dialog keeps showing current deps
      depsTask = selectedProject.tasks.find(t => t.id === depsTask.id) || null;
      depsPickId = null;
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  async function removeDependency(depId) {
    if (!depsTask) return;
    try {
      await api.delete(`/api/projects/${selectedProject.id}/tasks/${depsTask.id}/dependencies/${depId}`);
      await openProject(selectedProject);
      depsTask = selectedProject.tasks.find(t => t.id === depsTask.id) || null;
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  // Highlight a task in the list when clicking its dependency chip — saves
  // hunting through long lists to figure out what "Tâche A" is.
  function jumpToTask(taskId) {
    const el = document.getElementById(`task-item-${taskId}`);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('task-item--flash');
    setTimeout(() => el.classList.remove('task-item--flash'), 1500);
  }

  // ── PDF export ─────────────────────────────────────────────
  // One-shot project report: header, budget, Gantt screenshot, tasks, suppliers,
  // documents, journal. Useful for sharing a project status or archiving.
  let ganttCardEl;
  let exportingPdf = false;

  async function exportProjectPdf() {
    if (!selectedProject || exportingPdf) return;
    exportingPdf = true;
    try {
      const { default: jsPDF } = await import('jspdf');
      // jspdf-autotable v5 changed to a function-style API (autoTable(doc, opts))
      // instead of doc.autoTable(opts). Import the function directly.
      const autoTableMod = await import('jspdf-autotable');
      const autoTable = autoTableMod.default || autoTableMod.autoTable;
      const doc = new jsPDF();

      const p = selectedProject;
      const today = new Date().toLocaleDateString('fr-FR');

      // Header
      doc.setFontSize(18);
      doc.text(p.title, 14, 18);
      doc.setFontSize(9);
      doc.setTextColor(100);
      doc.text(`Exporte le ${today} \u2014 Statut : ${statusInfo(p.status).label}`, 14, 25);
      if (p.start_date || p.end_date) {
        doc.text(`Periode : ${p.start_date ? formatDate(p.start_date) : '...'} \u2192 ${p.end_date ? formatDate(p.end_date) : '...'}`, 14, 31);
      }
      doc.setTextColor(0);
      let y = 38;

      // Description
      if (p.description) {
        doc.setFontSize(10);
        const desc = doc.splitTextToSize(p.description, 180);
        doc.text(desc, 14, y);
        y += desc.length * 5 + 4;
      }

      // Budget summary
      if (budgetPrevu > 0 || budgetEngage > 0 || budgetFacture > 0) {
        doc.setFontSize(12); doc.setTextColor(60);
        doc.text('Budget', 14, y); y += 6;
        doc.setFontSize(9); doc.setTextColor(0);
        const lines = [];
        if (budgetPrevu > 0) lines.push(`Prevu : ${budgetPrevu.toLocaleString('fr-FR')} EUR`);
        lines.push(`Engage : ${budgetEngage.toLocaleString('fr-FR')} EUR`);
        lines.push(`Facture : ${budgetFacture.toLocaleString('fr-FR')} EUR`);
        if (budgetPrevu > 0) {
          const pct = Math.round(budgetConsomme / budgetPrevu * 100);
          lines.push(`Consomme : ${budgetConsomme.toLocaleString('fr-FR')} EUR (${pct}%${budgetConsomme > budgetPrevu ? ' \u2014 DEPASSEMENT' : ''})`);
        }
        for (const l of lines) { doc.text(l, 14, y); y += 5; }
        y += 3;
      }

      // Gantt as image (best effort — skip silently if html2canvas fails)
      if (ganttCardEl) {
        try {
          const { default: html2canvas } = await import('html2canvas');
          const canvas = await html2canvas(ganttCardEl, { scale: 1.5, backgroundColor: '#ffffff' });
          const imgData = canvas.toDataURL('image/png');
          const pageW = doc.internal.pageSize.getWidth() - 28;
          const ratio = canvas.height / canvas.width;
          const imgH = pageW * ratio;
          if (y + imgH > 270) { doc.addPage(); y = 18; }
          doc.setFontSize(12); doc.setTextColor(60);
          doc.text('Diagramme de Gantt', 14, y); y += 6;
          doc.setTextColor(0);
          doc.addImage(imgData, 'PNG', 14, y, pageW, imgH);
          y += imgH + 6;
        } catch (e) {
          console.warn('Gantt capture failed:', e);
        }
      }

      // Tasks table
      if (p.tasks && p.tasks.length > 0) {
        if (y > 240) { doc.addPage(); y = 18; }
        doc.setFontSize(12); doc.setTextColor(60);
        doc.text(`Taches (${p.tasks.length})`, 14, y); y += 4;
        doc.setTextColor(0);
        const head = [['#', 'Titre', 'Debut', 'Echeance', 'Priorite', 'Statut']];
        const body = p.tasks.map((t, i) => [
          String(i + 1),
          (t.is_milestone ? '\u25C6 ' : '') + t.title,
          t.start_date ? formatDate(t.start_date) : '\u2014',
          t.due_date ? formatDate(t.due_date) : '\u2014',
          t.priority === 3 ? 'Haute' : t.priority === 1 ? 'Basse' : 'Normale',
          t.done ? 'Terminee' : (t.blocked ? 'Bloquee' : 'A faire'),
        ]);
        autoTable(doc, { head, body, startY: y, styles: { fontSize: 8, cellPadding: 2 }, headStyles: { fillColor: [136, 105, 225] } });
        y = doc.lastAutoTable.finalY + 6;
      }

      // Suppliers
      if (p.suppliers && p.suppliers.length > 0) {
        if (y > 250) { doc.addPage(); y = 18; }
        doc.setFontSize(12); doc.setTextColor(60);
        doc.text(`Prestataires (${p.suppliers.length})`, 14, y); y += 4;
        doc.setTextColor(0);
        const head = [['Nom', 'Contact', 'Telephone', 'Email']];
        const body = p.suppliers.map(s => [s.name, s.contact || '', s.phone || '', s.email || '']);
        autoTable(doc, { head, body, startY: y, styles: { fontSize: 8, cellPadding: 2 }, headStyles: { fillColor: [58, 155, 148] } });
        y = doc.lastAutoTable.finalY + 6;
      }

      // Documents
      if (p.documents && p.documents.length > 0) {
        if (y > 250) { doc.addPage(); y = 18; }
        doc.setFontSize(12); doc.setTextColor(60);
        doc.text(`Documents (${p.documents.length})`, 14, y); y += 4;
        doc.setTextColor(0);
        const head = [['Titre', 'Type', 'Montant', 'Valide', 'Statut']];
        const body = p.documents.map(d => [
          d.title,
          d.doc_type || '',
          (d.amount || 0).toLocaleString('fr-FR') + ' EUR',
          d.amount_accepted > 0 ? d.amount_accepted.toLocaleString('fr-FR') + ' EUR' : '\u2014',
          d.status || '\u2014',
        ]);
        autoTable(doc, { head, body, startY: y, styles: { fontSize: 8, cellPadding: 2 }, headStyles: { fillColor: [245, 158, 11] } });
        y = doc.lastAutoTable.finalY + 6;
      }

      // Notes (journal)
      if (p.notes && p.notes.length > 0) {
        if (y > 240) { doc.addPage(); y = 18; }
        doc.setFontSize(12); doc.setTextColor(60);
        doc.text(`Journal (${p.notes.length})`, 14, y); y += 6;
        doc.setFontSize(9); doc.setTextColor(0);
        for (const n of p.notes) {
          if (y > 270) { doc.addPage(); y = 18; }
          doc.setTextColor(120);
          doc.text(formatDate(n.created_at), 14, y);
          doc.setTextColor(0);
          const lines = doc.splitTextToSize(n.content, 170);
          doc.text(lines, 35, y);
          y += Math.max(5, lines.length * 4) + 2;
        }
      }

      // Save via Tauri dialog when available, fall back to browser download
      const filename = `projet_${(p.title || 'export').replace(/[^a-z0-9]+/gi, '_').toLowerCase()}_${new Date().toISOString().slice(0,10)}.pdf`;
      try {
        const { save } = await import('@tauri-apps/plugin-dialog');
        const { documentDir, join } = await import('@tauri-apps/api/path');
        const docsDir = await documentDir();
        const path = await save({
          defaultPath: await join(docsDir, filename),
          filters: [{ name: 'PDF', extensions: ['pdf'] }],
        });
        if (path) {
          const { writeFile } = await import('@tauri-apps/plugin-fs');
          await writeFile(path, new Uint8Array(doc.output('arraybuffer')));
          success(`PDF enregistre : ${path.split(/[\\/]/).pop()}`);
        }
      } catch {
        doc.save(filename);
        success('PDF exporte');
      }
    } catch (e) {
      console.error('PDF export failed:', e);
      toastError('Erreur export PDF : ' + (e.message || ''));
    }
    exportingPdf = false;
  }

  // ── Documents ──
  let docLinkForm = { document_id: null, amount: 0, amount_accepted: 0, status: '' };
  let showDocAmountDialog = false;

  async function fetchAllDocuments() {
    try { allDocuments = await api.get('/api/documents'); } catch { allDocuments = []; }
  }

  function selectDocToLink(docId) {
    docLinkForm = { document_id: docId, amount: 0, amount_accepted: 0, status: '' };
    showLinkDocDialog = false;
    showDocAmountDialog = true;
  }

  async function confirmLinkDocument() {
    try {
      await api.post(`/api/projects/${selectedProject.id}/documents`, docLinkForm);
      showDocAmountDialog = false;
      await openProject(selectedProject);
      success('Document lie');
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  async function updateDocLink(doc) {
    try {
      await api.put(`/api/projects/${selectedProject.id}/documents/${doc.id}`, {
        amount: doc.amount, amount_accepted: doc.amount_accepted, status: doc.status,
      });
      success('Montant mis a jour');
    } catch (e) { toastError('Erreur: ' + (e.message || '')); }
  }

  async function unlinkDocument(docId) {
    try {
      await api.delete(`/api/projects/${selectedProject.id}/documents/${docId}`);
      await openProject(selectedProject);
    } catch (e) { toastError('Erreur: ' + (e.message || '')); }
  }

  // ── Suppliers ──
  async function fetchAllSuppliers() {
    try { allSuppliers = await api.get('/api/suppliers'); } catch { allSuppliers = []; }
  }

  async function linkSupplier(supId) {
    try {
      await api.post(`/api/projects/${selectedProject.id}/suppliers`, { supplier_id: parseInt(supId) });
      showLinkSupDialog = false;
      await openProject(selectedProject);
      success('Prestataire lie');
    } catch (e) { toastError('Erreur liaison prestataire: ' + e.message); }
  }

  async function unlinkSupplier(supId) {
    try {
      await api.delete(`/api/projects/${selectedProject.id}/suppliers/${supId}`);
      await openProject(selectedProject);
    } catch (e) { toastError('Erreur: ' + (e.message || '')); }
  }

  // ── Notes ──
  async function addNote() {
    if (!noteText.trim()) return;
    try {
      await api.post(`/api/projects/${selectedProject.id}/notes`, { content: noteText });
      noteText = '';
      await openProject(selectedProject);
    } catch (e) { toastError('Erreur: ' + (e.message || '')); }
  }

  async function deleteNote(noteId) {
    try {
      await api.delete(`/api/projects/${selectedProject.id}/notes/${noteId}`);
      await openProject(selectedProject);
    } catch (e) { toastError('Erreur: ' + (e.message || '')); }
  }

  // ── Gantt helpers ──
  // Parse a date-ish string to a LOCAL midnight timestamp, so that
  // "2026-04-23" and "2026-04-23T14:30:00" both resolve to the same day boundary.
  // Mixing UTC-parsed "YYYY-MM-DD" with local-parsed ISO timestamps causes the
  // bar to shift by ~12h from the "today" line on timezones like CEST.
  function dayMs(s) {
    if (!s) return null;
    const ymd = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    if (ymd) return new Date(+ymd[1], +ymd[2] - 1, +ymd[3]).getTime();
    const d = new Date(s);
    if (isNaN(d)) return null;
    return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  }

  function taskStartMs(task) {
    // Priority: explicit start_date > due_date - 3 days > created_at
    if (task.start_date) return dayMs(task.start_date);
    if (task.due_date) return dayMs(task.due_date) - 3 * 86400000;
    if (task.created_at) return dayMs(task.created_at);
    return null;
  }

  function taskEndMs(task) {
    if (task.due_date) return dayMs(task.due_date);
    const startRef = task.start_date || task.created_at;
    return startRef ? dayMs(startRef) + 3 * 86400000 : null;
  }

  function ganttData(project, zoom = 'auto') {
    if (!project?.tasks?.length) return { tasks: [], months: [], weeks: [], startMs: 0, totalMs: 1, hiddenCount: 0 };
    // Only show tasks that have a real schedule (start or due). Falling back to created_at
    // would invent a position for dateless tasks — this is what made duplicated projects
    // look weird on the Gantt.
    const tasks = project.tasks.filter(t => t.start_date || t.due_date);
    const hiddenCount = project.tasks.length - tasks.length;
    if (!tasks.length) return { tasks: [], months: [], weeks: [], startMs: 0, totalMs: 1, hiddenCount };

    let pStart, pEnd;
    if (zoom !== 'auto') {
      // Fixed window centered on today
      const d = new Date();
      const today = new Date(d.getFullYear(), d.getMonth(), d.getDate());
      const spans = {
        day:   { before: 3,  after: 11 },   // 2 weeks, day-level readable
        week:  { before: 14, after: 42 },   // ~2 months
        month: { before: 30, after: 150 },  // ~6 months
      };
      const span = spans[zoom] || spans.week;
      pStart = new Date(today); pStart.setDate(pStart.getDate() - span.before);
      pEnd = new Date(today);   pEnd.setDate(pEnd.getDate() + span.after);
    } else {
      // Determine project timeline from data (all values already local-midnight normalized)
      const allDates = [];
      tasks.forEach(t => {
        const s = taskStartMs(t);
        const e = taskEndMs(t);
        if (s !== null) allDates.push(new Date(s));
        if (e !== null) allDates.push(new Date(e));
      });
      const projStart = dayMs(project.start_date);
      const projEnd = dayMs(project.end_date);
      if (projStart !== null) allDates.push(new Date(projStart));
      if (projEnd !== null) allDates.push(new Date(projEnd));

      pStart = new Date(Math.min(...allDates));
      pEnd = new Date(Math.max(...allDates));
      pStart.setDate(pStart.getDate() - 7);
      pEnd.setDate(pEnd.getDate() + 14);
    }
    const startMs = pStart.getTime();
    const totalMs = pEnd.getTime() - startMs;

    // Generate month labels
    const months = [];
    const cur = new Date(pStart);
    cur.setDate(1);
    while (cur <= pEnd) {
      const pos = ((cur.getTime() - startMs) / totalMs) * 100;
      months.push({
        label: cur.toLocaleDateString('fr-FR', { month: 'short', year: '2-digit' }),
        pos: Math.max(0, pos),
      });
      cur.setMonth(cur.getMonth() + 1);
    }

    // Generate week markers
    const weeks = [];
    const wCur = new Date(pStart);
    wCur.setDate(wCur.getDate() - wCur.getDay() + 1); // Start on Monday
    while (wCur <= pEnd) {
      const pos = ((wCur.getTime() - startMs) / totalMs) * 100;
      if (pos >= 0 && pos <= 100) {
        weeks.push({ pos });
      }
      wCur.setDate(wCur.getDate() + 7);
    }

    // Day ticks: one label per few days depending on timeline length. Keeps the header readable.
    const days = [];
    const spanDays = Math.max(1, totalMs / 86400000);
    const stepDays = spanDays <= 21 ? 1 : spanDays <= 60 ? 3 : spanDays <= 120 ? 7 : 14;
    const dCur = new Date(pStart);
    dCur.setHours(0, 0, 0, 0);
    while (dCur <= pEnd) {
      const pos = ((dCur.getTime() - startMs) / totalMs) * 100;
      if (pos >= 0 && pos <= 100) {
        days.push({ pos, label: dCur.getDate() });
      }
      dCur.setDate(dCur.getDate() + stepDays);
    }

    return { tasks, months, weeks, days, startMs, totalMs, hiddenCount };
  }

  function ganttBarStyle(task, startMs, totalMs) {
    const taskStart = taskStartMs(task);
    const taskEnd = taskEndMs(task);
    if (taskStart === null || taskEnd === null) return '';
    const left = Math.max(0, ((taskStart - startMs) / totalMs) * 100);
    const right = Math.min(100, ((taskEnd - startMs) / totalMs) * 100);
    const width = Math.max(2, right - left);
    return `left:${left}%;width:${width}%`;
  }

  // Status-based color so a glance at the Gantt tells the user what needs attention.
  // Keyed by taskStatus(): done=green, late=red, soon=orange, in-progress=blue, todo=gray.
  function taskStatus(task) {
    if (task.done) return 'done';
    const today = (() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); })();
    const start = taskStartMs(task);
    const end = taskEndMs(task);
    if (end !== null && end < today) return 'late';              // due date passed, not done
    if (start !== null && start > today) return 'todo';          // scheduled for the future
    // In or approaching the task window
    if (end !== null && end - today <= 3 * 86400000) return 'soon'; // due within 3 days
    return 'in-progress';
  }

  const STATUS_COLORS = {
    done: '#22C55E',
    late: '#EF4444',
    soon: '#F59E0B',
    'in-progress': '#3B82F6',
    todo: '#94A3B8',
  };

  // Progress is *only* meaningful when there's real completion data:
  //   - task marked done  → 100%
  //   - task has a checklist → share of items checked
  //   - otherwise → null (don't show a percentage at all; time-based guessing was misleading)
  function taskProgress(task) {
    if (task.done) return 100;
    const total = task.checklist_total || 0;
    if (total > 0) return Math.round(((task.checklist_done || 0) / total) * 100);
    return null;
  }

  function ganttBarDates(task) {
    const s = task.start_date || (task.due_date ? null : task.created_at);
    const e = task.due_date;
    const parts = [];
    if (s) parts.push(new Date(s).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }));
    if (e) parts.push(new Date(e).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }));
    return parts.join(' → ');
  }

  function todayPos(startMs, totalMs) {
    // Align to local midnight so a task with start_date=today lines up exactly with the "Aujourd'hui" line
    const d = new Date();
    const today = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    return Math.max(0, Math.min(100, ((today - startMs) / totalMs) * 100));
  }

  // ── Gantt dependency arrows (GanttProject-style elbow lines) ──
  // Match CSS: .gantt-task-name { width:180px } and row height ≈ 31px (0.25rem padding top+bottom + 22px bar + 1px border)
  const GANTT_NAME_W = 180;
  const GANTT_ROW_H = 31;
  let ganttBodyWidth = 0;

  // Reactive so the template can use them as plain expressions (Svelte 5 restricts {@const} placement).
  $: gd = selectedProject ? ganttData(selectedProject, ganttZoom) : { tasks: [], months: [], weeks: [], startMs: 0, totalMs: 1, hiddenCount: 0 };
  $: arrows = computeArrows(gd.tasks, ganttBodyWidth, gd.startMs, gd.totalMs);

  // ── Drag-to-edit on Gantt ──
  // Press a bar to move it (shift both start_date and due_date by the same number of days),
  // or grab the right edge (last 8px) to resize the due_date.
  let dragState = null; // { taskId, mode: 'move'|'resize', startX, origStart, origEnd, deltaDays }

  function pixelsPerDay(bodyWidth, totalMs) {
    if (!bodyWidth || !totalMs) return 0;
    const barAreaPx = bodyWidth - GANTT_NAME_W;
    return barAreaPx / (totalMs / 86400000);
  }

  function isoFromMs(ms) {
    const d = new Date(ms);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  function onGanttBarDown(e, task) {
    if (e.button !== 0) return;
    if (!task.start_date && !task.due_date) return;
    const bar = e.currentTarget;
    const rect = bar.getBoundingClientRect();
    const localX = e.clientX - rect.left;
    const isResize = task.due_date && (rect.width - localX) <= 8;
    // Milestones / tasks without due_date: only allow move
    const mode = isResize ? 'resize' : 'move';

    dragState = {
      taskId: task.id,
      mode,
      startX: e.clientX,
      origStartMs: taskStartMs(task),
      origEndMs: taskEndMs(task),
      origStart: task.start_date,
      origDue: task.due_date,
      deltaDays: 0,
    };
    e.preventDefault();
    window.addEventListener('mousemove', onGanttDragMove);
    window.addEventListener('mouseup', onGanttDragUp);
    document.body.style.cursor = mode === 'resize' ? 'ew-resize' : 'grabbing';
  }

  function onGanttDragMove(e) {
    if (!dragState) return;
    const ppd = pixelsPerDay(ganttBodyWidth, gd.totalMs);
    if (!ppd) return;
    const dx = e.clientX - dragState.startX;
    dragState.deltaDays = Math.round(dx / ppd);
  }

  async function onGanttDragUp() {
    window.removeEventListener('mousemove', onGanttDragMove);
    window.removeEventListener('mouseup', onGanttDragUp);
    document.body.style.cursor = '';
    const ds = dragState;
    dragState = null;
    if (!ds || ds.deltaDays === 0) return;

    const task = (selectedProject.tasks || []).find(t => t.id === ds.taskId);
    if (!task) return;

    let newStart = ds.origStart;
    let newDue = ds.origDue;
    const shiftMs = ds.deltaDays * 86400000;
    if (ds.mode === 'move') {
      if (ds.origStart) newStart = isoFromMs(dayMs(ds.origStart) + shiftMs);
      if (ds.origDue) newDue = isoFromMs(dayMs(ds.origDue) + shiftMs);
    } else {
      // resize: only the due_date moves
      if (ds.origDue) {
        const newDueMs = dayMs(ds.origDue) + shiftMs;
        const minMs = ds.origStart ? dayMs(ds.origStart) : null;
        if (minMs !== null && newDueMs < minMs) {
          // Don't let the due_date drop before the start_date
          return;
        }
        newDue = isoFromMs(newDueMs);
      }
    }

    try {
      await api.put(`/api/tasks/${task.id}`, {
        title: task.title,
        category: task.category || '',
        priority: task.priority,
        due_date: newDue || null,
        start_date: newStart || null,
        notes: task.notes || '',
        site: task.site || '',
        recurrence: task.recurrence || '',
        is_milestone: !!task.is_milestone,
      });
      await openProject(selectedProject);
    } catch (e) {
      toastError('Erreur: ' + (e.message || ''));
    }
  }

  // Visual offset applied while dragging (in % of bar-area width).
  // Reactive — updates as deltaDays changes during drag.
  $: dragOffsetPct = (() => {
    if (!dragState || !ganttBodyWidth || !gd.totalMs) return 0;
    const ppd = pixelsPerDay(ganttBodyWidth, gd.totalMs);
    const dxPx = dragState.deltaDays * ppd;
    const barAreaPx = ganttBodyWidth - GANTT_NAME_W;
    return (dxPx / barAreaPx) * 100;
  })();

  function computeArrows(tasks, bodyWidth, startMs, totalMs) {
    if (!bodyWidth || bodyWidth <= GANTT_NAME_W + 20 || !tasks?.length) return [];
    const barAreaW = bodyWidth - GANTT_NAME_W;
    const rowIdxById = new Map(tasks.map((t, i) => [t.id, i]));
    const arrows = [];
    const elbow = 8; // px overshoot out of the source bar before turning

    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i];
      const deps = task.dependencies || [];
      if (!deps.length) continue;
      const targetStart = taskStartMs(task);
      if (targetStart === null) continue;
      const tLeftPct = Math.max(0, Math.min(100, ((targetStart - startMs) / totalMs) * 100));
      const targetX = GANTT_NAME_W + (tLeftPct / 100) * barAreaW;
      const targetY = i * GANTT_ROW_H + GANTT_ROW_H / 2;

      for (const dep of deps) {
        const depIdx = rowIdxById.get(dep.id);
        if (depIdx === undefined) continue;
        const depTask = tasks[depIdx];
        const depEnd = taskEndMs(depTask);
        if (depEnd === null) continue;
        const dRightPct = Math.max(0, Math.min(100, ((depEnd - startMs) / totalMs) * 100));
        const srcX = GANTT_NAME_W + (dRightPct / 100) * barAreaW;
        const srcY = depIdx * GANTT_ROW_H + GANTT_ROW_H / 2;

        // Elbow path: out from source → vertical to target row → into target bar (arrow)
        const midX = Math.max(srcX + elbow, targetX - elbow);
        const d = `M ${srcX} ${srcY} L ${midX} ${srcY} L ${midX} ${targetY} L ${targetX - 1} ${targetY}`;
        const resolved = dep.done;
        arrows.push({ d, resolved });
      }
    }
    return arrows;
  }

  function formatDate(d) {
    if (!d) return '';
    try { return new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return d; }
  }

  onMount(fetchProjects);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->

{#if !selectedProject}
  <!-- ═══ LIST VIEW ═══ -->
  <div class="page-header">
    <h1>Projets</h1>
    <button class="ya-btn ya-btn--primary" on:click={openNewDialog}>+ Nouveau projet</button>
  </div>

  <!-- KPIs -->
  <div class="ya-kpi-row">
    <div class="ya-kpi ya-kpi--primary">
      <span class="ya-kpi__value">{projects.length}</span>
      <span class="ya-kpi__label">Total</span>
    </div>
    <div class="ya-kpi ya-kpi--info">
      <span class="ya-kpi__value">{projects.filter(p => p.status === 'in_progress').length}</span>
      <span class="ya-kpi__label">En cours</span>
    </div>
    <div class="ya-kpi ya-kpi--success">
      <span class="ya-kpi__value">{projects.filter(p => p.status === 'completed').length}</span>
      <span class="ya-kpi__label">Termines</span>
    </div>
    <div class="ya-kpi ya-kpi--warning">
      <span class="ya-kpi__value">{projects.reduce((s, p) => s + p.total_tasks, 0)}</span>
      <span class="ya-kpi__label">Taches liees</span>
    </div>
  </div>

  {#if loading}
    <div class="loading">Chargement...</div>
  {:else if projects.length === 0}
    <div class="empty-state">
      <span style="font-size:3rem">🎯</span>
      <h3>Aucun projet</h3>
      <p>Creez votre premier projet pour organiser vos taches, documents et prestataires.</p>
      <button class="ya-btn ya-btn--primary" on:click={openNewDialog}>+ Creer un projet</button>
    </div>
  {:else}
    <div class="projects-grid">
      {#each projects as p (p.id)}
        {@const bPct = p.budget > 0 ? Math.min(100, Math.round((p.budget_consumed || 0) / p.budget * 100)) : 0}
        {@const bOver = p.budget > 0 && (p.budget_consumed || 0) > p.budget}
        {@const hasBudgetInfo = p.budget > 0 || (p.budget_consumed || 0) > 0 || (p.budget_engaged || 0) > 0 || (p.budget_invoiced || 0) > 0}
        <div class="project-card" style="border-left-color:{p.color}" on:click={() => openProject(p)}>
          <div class="project-card__header">
            <h3>{p.title}</h3>
            <span class="status-badge" style="background:{statusInfo(p.status).color}20;color:{statusInfo(p.status).color}">{statusInfo(p.status).label}</span>
          </div>
          {#if p.description}<p class="project-card__desc">{p.description}</p>{/if}
          <div class="project-card__meta">
            {#if p.start_date}<span>{formatDate(p.start_date)} → {formatDate(p.end_date)}</span>{/if}
            <span>{p.total_tasks} tache{p.total_tasks > 1 ? 's' : ''}</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:{p.progress}%;background:{p.color}"></div></div>
          <div class="project-card__footer">
            <span>{p.done_tasks}/{p.total_tasks} terminees</span>
            <span style="font-weight:700;color:{p.color}">{p.progress}%</span>
          </div>
          {#if hasBudgetInfo}
            <div class="card-budget" class:card-budget--over={bOver}>
              {#if p.budget > 0}
                <div class="card-budget__label">
                  <span>Budget</span>
                  <span class="card-budget__val">{(p.budget_consumed || 0).toLocaleString('fr-FR')} / {p.budget.toLocaleString('fr-FR')} EUR</span>
                </div>
                <div class="card-budget__bar">
                  <div class="card-budget__fill" style="width:{bPct}%;background:{bOver ? '#EF4444' : bPct > 80 ? '#F59E0B' : '#22C55E'}"></div>
                </div>
              {:else}
                <!-- No planned budget: just show what's been spent so far -->
                <div class="card-budget__label">
                  <span>Depenses</span>
                  <span class="card-budget__val">{(p.budget_consumed || 0).toLocaleString('fr-FR')} EUR</span>
                </div>
                <div class="card-budget__split">
                  <span>Engage : {(p.budget_engaged || 0).toLocaleString('fr-FR')}</span>
                  <span>Facture : {(p.budget_invoiced || 0).toLocaleString('fr-FR')}</span>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

{:else}
  <!-- ═══ DETAIL VIEW ═══ -->
  <div class="detail-header">
    <button class="ya-btn ya-btn--ghost" on:click={backToList}>← Retour</button>
    <div style="display:flex;gap:0.5rem">
      <button class="ya-btn ya-btn--ghost" on:click={exportProjectPdf} disabled={exportingPdf} title="Exporter le projet en PDF">
        {exportingPdf ? '...' : '📄 PDF'}
      </button>
      <button class="ya-btn ya-btn--ghost" on:click={duplicateProject} disabled={duplicating} title="Créer un nouveau projet à partir de celui-ci">
        {duplicating ? '...' : 'Dupliquer'}
      </button>
      <button class="ya-btn ya-btn--ghost" on:click={openEditDialog}>Modifier</button>
      <button class="ya-btn ya-btn--danger" on:click={() => confirmDeleteId = selectedProject.id}>Supprimer</button>
    </div>
  </div>

  {#if detailLoading}
    <div class="loading">Chargement...</div>
  {:else}
    <!-- Project header card -->
    <div class="project-header-card" style="border-left-color:{selectedProject.color}">
      <div class="project-header-card__info">
        <h2>{selectedProject.title}</h2>
        {#if selectedProject.description}<p>{selectedProject.description}</p>{/if}
        <div class="project-header-card__meta">
          {#if selectedProject.start_date}<span>{formatDate(selectedProject.start_date)} → {formatDate(selectedProject.end_date)}</span>{/if}
          <span class="status-badge" style="background:{statusInfo(selectedProject.status).color}20;color:{statusInfo(selectedProject.status).color}">{statusInfo(selectedProject.status).label}</span>
        </div>
      </div>
      <div class="project-header-card__progress">
        <div class="progress-big-num" style="color:{selectedProject.color}">{selectedProject.progress}%</div>
        <div class="progress-sub">{selectedProject.done_tasks}/{selectedProject.total_tasks} taches</div>
      </div>
    </div>
    <div class="progress-bar" style="margin-bottom:0.75rem"><div class="progress-fill" style="width:{selectedProject.progress}%;background:{selectedProject.color}"></div></div>

    {#if budgetPrevu > 0 || budgetDocs.length > 0 || budgetEngage > 0 || budgetFacture > 0}
      <div class="budget-compact">
        <div class="budget-compact-cards">
          {#if budgetPrevu > 0}
            <div class="budget-mini-card">
              <div class="budget-mini-icon" style="background:rgba(245,158,11,0.1)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
              </div>
              <div>
                <div class="budget-mini-val" style="color:#F59E0B">{budgetPrevu.toLocaleString('fr-FR')} EUR</div>
                <div class="budget-mini-label">Budget prevu</div>
              </div>
            </div>
          {:else}
            <div class="budget-mini-card">
              <div class="budget-mini-icon" style="background:rgba(148,163,184,0.12)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              </div>
              <div>
                <div class="budget-mini-val" style="color:#64748B">Sans budget prevu</div>
                <div class="budget-mini-label">Suivi des depenses uniquement</div>
              </div>
            </div>
          {/if}
          <div class="budget-mini-card">
            <div class="budget-mini-icon" style="background:rgba(139,92,246,0.1)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
            </div>
            <div>
              <div class="budget-mini-val" style="color:#8B5CF6">{budgetEngage.toLocaleString('fr-FR')} EUR</div>
              <div class="budget-mini-label">Engage (devis accepte)</div>
            </div>
          </div>
          <div class="budget-mini-card">
            <div class="budget-mini-icon" style="background:rgba(34,197,94,0.1)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>
            </div>
            <div>
              <div class="budget-mini-val" style="color:#22C55E">{budgetFacture.toLocaleString('fr-FR')} EUR</div>
              <div class="budget-mini-label">Facture</div>
            </div>
          </div>
        </div>
        <button class="ya-btn ya-btn--ghost ya-btn--sm" on:click={() => showBudgetPanel = true}>Voir le detail</button>
      </div>
    {/if}

    <!-- Gantt -->
    {#if gd.months.length === 0 && gd.hiddenCount > 0}
      <div class="section-card">
        <p class="gantt-hidden-note" style="margin:0">
          {gd.hiddenCount} tâche{gd.hiddenCount > 1 ? 's' : ''} sans date — renseignez une date de début ou d'échéance pour les voir sur le Gantt.
        </p>
      </div>
    {/if}
    {#if gd.months.length > 0}
      <div class="section-card gantt-card" bind:this={ganttCardEl}>
        <div class="gantt-header">
          <h3 class="section-title" style="margin:0">Diagramme de Gantt</h3>
          <div class="gantt-zoom">
            {#each GANTT_ZOOMS as z}
              <button
                class="gantt-zoom-btn"
                class:gantt-zoom-btn--active={ganttZoom === z.value}
                on:click={() => ganttZoom = z.value}
              >{z.label}</button>
            {/each}
          </div>
          <div class="gantt-legend">
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:#22C55E"></span>Termine</span>
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:#3B82F6"></span>En cours</span>
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:#F59E0B"></span>Bientot du</span>
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:#EF4444"></span>En retard</span>
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:#94A3B8"></span>A faire</span>
          </div>
        </div>
        <div class="gantt">
          <!-- Month + day headers (offset by the task-name column so they align with bars below) -->
          <div class="gantt-months">
            {#each gd.months as m}
              <span style="left:calc(180px + (100% - 180px) * {m.pos} / 100)">{m.label}</span>
            {/each}
          </div>
          {#if gd.days && gd.days.length > 0}
            <div class="gantt-days">
              {#each gd.days as d}
                <span class="gantt-day-tick" style="left:calc(180px + (100% - 180px) * {d.pos} / 100)">{d.label}</span>
              {/each}
            </div>
          {/if}
          <div class="gantt-body" bind:clientWidth={ganttBodyWidth}>
            <!-- Week grid lines (inside the bar-area portion, offset 180px via calc) -->
            {#each gd.weeks || [] as w}
              <div class="gantt-week-line" style="left:calc(180px + (100% - 180px) * {w.pos} / 100)"></div>
            {/each}
            <!-- Today line — same offset so it lines up exactly with bars -->
            <div class="gantt-today-line" style="left:calc(180px + (100% - 180px) * {todayPos(gd.startMs, gd.totalMs)} / 100)">
              <span class="gantt-today-label">Aujourd'hui</span>
            </div>
            <!-- Task rows -->
            {#each gd.tasks as task, idx}
              <div class="gantt-row" class:gantt-row-alt={idx % 2 === 1}>
                <div class="gantt-task-name" class:done={task.done}>
                  <span class="gantt-task-num">{idx + 1}</span>
                  {task.title}
                </div>
                <div class="gantt-bar-area">
                  {#if task.start_date || task.due_date}
                    {@const status = taskStatus(task)}
                    {@const color = STATUS_COLORS[status]}
                    {@const pct = taskProgress(task)}
                    {@const blocked = task.blocked && !task.done}
                    {@const isDragging = dragState?.taskId === task.id}
                    {@const baseStyle = ganttBarStyle(task, gd.startMs, gd.totalMs)}
                    {#if task.is_milestone}
                      <!-- Milestone: diamond shape at the due_date (or start_date fallback) position -->
                      {@const mkMs = taskEndMs(task) ?? taskStartMs(task)}
                      {@const mkPct = mkMs !== null ? Math.max(0, Math.min(100, ((mkMs - gd.startMs) / gd.totalMs) * 100)) : 0}
                      {@const mkOffset = isDragging ? dragOffsetPct : 0}
                      <div class="gantt-milestone" class:gantt-milestone--done={task.done}
                           class:gantt-bar--dragging={isDragging}
                           style="left:calc({mkPct}% + {mkOffset}%);background:{color};border-color:{color}"
                           on:mousedown={(e) => onGanttBarDown(e, task)}
                           title="{task.title} — Jalon {ganttBarDates(task)}{blocked ? ' — Bloquee' : ''}"></div>
                    {:else}
                      {@const dragLeft = isDragging && dragState.mode === 'move' ? dragOffsetPct : 0}
                      {@const dragWidth = isDragging && dragState.mode === 'resize' ? dragOffsetPct : 0}
                      <div class="gantt-bar gantt-bar--{status}" class:gantt-bar--blocked={blocked}
                           class:gantt-bar--dragging={isDragging}
                           style="{baseStyle.replace(/left:([0-9.]+)%/, (m, v) => `left:calc(${v}% + ${dragLeft}%)`).replace(/width:([0-9.]+)%/, (m, v) => `width:calc(${v}% + ${dragWidth}%)`)};background:{color}22;border-color:{color}"
                           data-task-id={task.id}
                           on:mousedown={(e) => onGanttBarDown(e, task)}
                           title="{task.title} — {ganttBarDates(task)}{pct !== null ? ` — ${pct}%` : ''}{task.checklist_total > 0 ? ` (${task.checklist_done}/${task.checklist_total})` : ''}{blocked ? ' — Bloquee' : ''} — Glisser pour deplacer, bord droit pour redimensionner">
                        {#if pct !== null && pct > 0 && !task.done}
                          <div class="gantt-bar-fill" style="width:{pct}%;background:{color}"></div>
                        {/if}
                        {#if task.done}
                          <div class="gantt-bar-fill gantt-bar-fill--full" style="background:{color}"></div>
                        {/if}
                        <span class="gantt-bar-text" style="color:{task.done || (pct !== null && pct >= 50) ? '#fff' : color}">
                          {#if blocked}{'\u{1F512} '}{/if}{#if task.done}{'\u2713 '}{/if}
                          {#if isDragging && dragState.deltaDays !== 0}
                            {dragState.deltaDays > 0 ? '+' : ''}{dragState.deltaDays}j
                          {:else if pct !== null}{pct}%{:else}{ganttBarDates(task)}{/if}
                        </span>
                        <!-- Resize handle on the right edge (visual hint) -->
                        <div class="gantt-bar-resize-handle"></div>
                      </div>
                    {/if}
                  {/if}
                </div>
              </div>
            {/each}

            <!-- Dependency arrows (elbow lines between dependent tasks) -->
            {#if arrows.length > 0}
              <svg class="gantt-arrows" width={ganttBodyWidth} height={gd.tasks.length * GANTT_ROW_H}>
                <defs>
                  <marker id="gantt-arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M 0 0 L 6 3 L 0 6 z" fill="#94A3B8" />
                  </marker>
                  <marker id="gantt-arrowhead-done" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M 0 0 L 6 3 L 0 6 z" fill="#22C55E" />
                  </marker>
                </defs>
                {#each arrows as a}
                  <path d={a.d} stroke={a.resolved ? '#22C55E' : '#94A3B8'} stroke-width="1.5" fill="none"
                        stroke-dasharray={a.resolved ? 'none' : '4 3'}
                        marker-end="url(#{a.resolved ? 'gantt-arrowhead-done' : 'gantt-arrowhead'})" />
                {/each}
              </svg>
            {/if}
          </div>
        </div>
        {#if gd.hiddenCount > 0}
          <p class="gantt-hidden-note">{gd.hiddenCount} tache{gd.hiddenCount > 1 ? 's' : ''} sans date non affichée{gd.hiddenCount > 1 ? 's' : ''} sur le Gantt</p>
        {/if}
      </div>
    {/if}

    <!-- Tasks -->
    <div class="section-card">
      <div class="section-header">
        <h3 class="section-title">Taches ({selectedProject.tasks?.length || 0})</h3>
        <button class="ya-btn ya-btn--primary ya-btn--sm" on:click={openNewTaskDialog}>+ Ajouter</button>
      </div>
      {#if selectedProject.tasks?.length > 0}
        <div class="task-list">
          {#each selectedProject.tasks as task}
            <div class="task-item" id="task-item-{task.id}" class:task-item--blocked={task.blocked && !task.done}>
              <div class="task-check" class:done={task.done} on:click={() => toggleTask(task)}></div>
              <div class="task-main">
                <div class="task-title-row">
                  {#if task.is_milestone}<span class="task-milestone-badge" title="Jalon">{'\u25C6'}</span>{/if}
                  <span class="task-title" class:done={task.done}>{task.title}</span>
                  {#if task.blocked && !task.done}
                    <span class="task-blocked-badge">🔒 Bloquee</span>
                  {/if}
                </div>
                {#if (task.dependencies || []).length > 0}
                  <div class="task-deps-inline">
                    <span class="task-deps-inline__label">Depend de :</span>
                    {#each task.dependencies as d, i}
                      <button type="button" class="task-deps-inline__chip" class:task-deps-inline__chip--done={d.done}
                              on:click={() => jumpToTask(d.id)} title="Aller à cette tâche">
                        {d.done ? '\u2713 ' : ''}{d.title}
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
              <span class="task-priority p{task.priority}">{task.priority === 3 ? 'Haute' : task.priority === 1 ? 'Basse' : 'Normale'}</span>
              {#if task.start_date || task.due_date}
                <span class="task-dates">
                  {#if task.start_date}{formatDate(task.start_date)}{:else}…{/if}
                  <span class="task-dates__arrow">{'\u2192'}</span>
                  {#if task.due_date}{formatDate(task.due_date)}{:else}…{/if}
                </span>
              {/if}
              <button class="task-edit-btn" on:click={() => openEditTaskDialog(task)} title="Modifier">{'\u270F\uFE0F'}</button>
              <button class="task-deps-btn" on:click={() => openDepsDialog(task)} title="Gérer les dépendances">🔗</button>
              <button class="task-unlink" on:click={() => deleteTask(task.id)} title="Supprimer la tâche">✕</button>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty-text">Aucune tache dans ce projet</p>
      {/if}
    </div>

    <!-- Documents -->
    <div class="section-card">
      <div class="section-header">
        <h3 class="section-title">Documents et budget ({selectedProject.documents?.length || 0})</h3>
        <button class="ya-btn ya-btn--ghost ya-btn--sm" on:click={() => { fetchAllDocuments(); showLinkDocDialog = true; }}>+ Lier un document</button>
      </div>
      {#if selectedProject.documents?.length > 0}
        {#if budgetEngage > 0 || budgetFacture > 0}
          <div class="budget-summary">
            <div class="budget-stat">
              <span class="budget-stat-val" style="color:#8B5CF6">{budgetEngage.toLocaleString('fr-FR')} EUR</span>
              <span class="budget-stat-label">Engage</span>
            </div>
            <div class="budget-stat">
              <span class="budget-stat-val" style="color:#22C55E">{budgetFacture.toLocaleString('fr-FR')} EUR</span>
              <span class="budget-stat-label">Facture</span>
            </div>
            <div class="budget-stat">
              <span class="budget-stat-val" style="color:#F59E0B">{budgetResteAFacturer.toLocaleString('fr-FR')} EUR</span>
              <span class="budget-stat-label">Reste a facturer</span>
            </div>
          </div>
        {/if}
        <div class="doc-list">
          {#each selectedProject.documents as doc}
            <div class="doc-item-rich">
              <div class="doc-item-main">
                <span class="doc-type">{doc.doc_type}</span>
                <span class="doc-title">{doc.title}</span>
                {#if doc.status}
                  <span class="doc-status" class:doc-accepted={doc.status === 'accepte'} class:doc-refused={doc.status === 'refuse'}>{doc.status}</span>
                {/if}
              </div>
              <div class="doc-item-amounts">
                {#if doc.amount > 0}
                  <span class="doc-amount">{doc.amount.toLocaleString('fr-FR')} EUR</span>
                {/if}
                {#if doc.amount_accepted > 0}
                  <span class="doc-amount-ok">{doc.amount_accepted.toLocaleString('fr-FR')} EUR valide</span>
                {/if}
              </div>
              <button class="task-unlink" on:click={() => openEditDocLink(doc)} title="Modifier montant" style="color:var(--primary)">✏️</button>
              <button class="task-unlink" on:click={() => unlinkDocument(doc.id)}>✕</button>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty-text">Aucun document lie</p>
      {/if}
    </div>

    <!-- Suppliers -->
    <div class="section-card">
      <div class="section-header">
        <h3 class="section-title">Prestataires ({selectedProject.suppliers?.length || 0})</h3>
        <button class="ya-btn ya-btn--ghost ya-btn--sm" on:click={() => { fetchAllSuppliers(); showLinkSupDialog = true; }}>+ Lier un prestataire</button>
      </div>
      {#if selectedProject.suppliers?.length > 0}
        <div class="sup-list">
          {#each selectedProject.suppliers as sup}
            <div class="sup-item">
              <div class="sup-logo">
                {#if sup.logo_path && !supplierLogoErrors[sup.id]}
                  <img src="{API_BASE}/api/suppliers/{sup.id}/logo" alt=""
                       on:error={() => { supplierLogoErrors[sup.id] = true; supplierLogoErrors = supplierLogoErrors; }} />
                {:else}
                  <span class="sup-logo__initials">{supplierInitials(sup.name)}</span>
                {/if}
              </div>
              <strong>{sup.name}</strong>
              {#if sup.contact}<span>{sup.contact}</span>{/if}
              {#if sup.phone}<span>{sup.phone}</span>{/if}
              {#if sup.email}<span>{sup.email}</span>{/if}
              <button class="task-unlink" on:click={() => unlinkSupplier(sup.id)}>✕</button>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty-text">Aucun prestataire lie</p>
      {/if}
    </div>

    <!-- Notes -->
    <div class="section-card">
      <h3 class="section-title">Journal de bord</h3>
      <div class="note-input">
        <textarea bind:value={noteText} placeholder="Ajouter une note..." rows="2"></textarea>
        <button class="ya-btn ya-btn--primary ya-btn--sm" on:click={addNote} disabled={!noteText.trim()}>Ajouter</button>
      </div>
      {#if selectedProject.notes?.length > 0}
        <div class="notes-list">
          {#each selectedProject.notes as note}
            <div class="note-item">
              <span class="note-date">{formatDate(note.created_at)}</span>
              <p class="note-content">{note.content}</p>
              <button class="note-delete" on:click={() => deleteNote(note.id)}>✕</button>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
{/if}

<!-- ═══ DIALOGS ═══ -->

{#if showDialog}
<div class="ya-dialog-overlay" on:mousedown|self={() => showDialog = false}>
  <div class="ya-dialog" style="max-width:500px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">{editingProject ? 'Modifier le projet' : 'Nouveau projet'}</h2>
      <button class="ya-dialog__close" on:click={() => showDialog = false}>x</button>
    </div>
    <div class="ya-dialog__body">
      <label>Titre <input type="text" bind:value={form.title} placeholder="Migration serveurs..." /></label>
      <label>Description <textarea bind:value={form.description} rows="3" placeholder="Description du projet..."></textarea></label>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
        <label>Date debut <input type="date" bind:value={form.start_date} /></label>
        <label>Date fin <input type="date" bind:value={form.end_date} /></label>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
        <label>Budget prevu (EUR) <input type="number" bind:value={form.budget} min="0" step="0.01" /></label>
        <label>Depense (EUR) <input type="number" bind:value={form.budget_spent} min="0" step="0.01" /></label>
      </div>
      <label>Statut
        <select bind:value={form.status}>
          {#each STATUSES as s}<option value={s.value}>{s.label}</option>{/each}
        </select>
      </label>
      <label>Couleur
        <div class="color-row">
          {#each COLORS as c}
            <button class="color-dot" class:active={form.color === c} style="background:{c}" on:click={() => form.color = c}></button>
          {/each}
        </div>
      </label>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => showDialog = false}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={saveProject} disabled={saving || !form.title.trim()}>
        {saving ? 'En cours...' : editingProject ? 'Enregistrer' : 'Creer'}
      </button>
    </div>
  </div>
</div>
{/if}

{#if showTaskDialog}
<div class="ya-dialog-overlay" on:mousedown|self={() => showTaskDialog = false}>
  <div class="ya-dialog" style="max-width:450px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">{editingTaskId ? 'Modifier la tache' : 'Nouvelle tache'}</h2>
      <button class="ya-dialog__close" on:click={() => showTaskDialog = false}>x</button>
    </div>
    <div class="ya-dialog__body">
      <label>Titre <input type="text" bind:value={taskForm.title} placeholder="Titre de la tache..." /></label>
      <label>Priorite
        <select bind:value={taskForm.priority}>
          <option value={1}>Basse</option><option value={2}>Normale</option><option value={3}>Haute</option>
        </select>
      </label>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
        <label>Date debut <input type="date" bind:value={taskForm.start_date} /></label>
        <label>Echeance <input type="date" bind:value={taskForm.due_date} /></label>
      </div>
      <label class="checkbox-inline">
        <input type="checkbox" bind:checked={taskForm.is_milestone} />
        <span>Cette tache est un jalon ({'\u25C6'}) — affichage ponctuel sur le Gantt</span>
      </label>
      <label>Site
        <select bind:value={taskForm.site}>
          {#each SITES as s}<option value={s.value}>{s.label}</option>{/each}
        </select>
      </label>
      <label>Notes <textarea bind:value={taskForm.notes} rows="2" placeholder="Notes..."></textarea></label>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => showTaskDialog = false}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={saveTask} disabled={!taskForm.title.trim()}>
        {editingTaskId ? 'Enregistrer' : 'Ajouter'}
      </button>
    </div>
  </div>
</div>
{/if}

{#if showLinkDocDialog}
<div class="ya-dialog-overlay" on:mousedown|self={() => showLinkDocDialog = false}>
  <div class="ya-dialog" style="max-width:500px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Lier un document</h2>
      <button class="ya-dialog__close" on:click={() => showLinkDocDialog = false}>x</button>
    </div>
    <div class="ya-dialog__body" style="max-height:400px;overflow-y:auto">
      {#each allDocuments.filter(d => !(selectedProject.documents || []).some(pd => pd.id === d.id)) as doc}
        <div class="link-item" on:click={() => selectDocToLink(doc.id)}>
          <span class="link-type">{doc.doc_type}</span>
          <span>{doc.title}</span>
        </div>
      {/each}
      {#if allDocuments.length === 0}<p class="empty-text">Aucun document disponible</p>{/if}
    </div>
  </div>
</div>
{/if}

{#if showLinkSupDialog}
<div class="ya-dialog-overlay" on:mousedown|self={() => showLinkSupDialog = false}>
  <div class="ya-dialog" style="max-width:500px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Lier un prestataire</h2>
      <button class="ya-dialog__close" on:click={() => showLinkSupDialog = false}>x</button>
    </div>
    <div class="ya-dialog__body" style="max-height:400px;overflow-y:auto">
      {#each allSuppliers.filter(s => !(selectedProject.suppliers || []).some(ps => ps.id === s.id)) as sup}
        <div class="link-item" on:click={() => linkSupplier(sup.id)}>
          <strong>{sup.name}</strong>
          {#if sup.contact}<span style="color:var(--text-muted);margin-left:0.5rem">{sup.contact}</span>{/if}
        </div>
      {/each}
      {#if allSuppliers.length === 0}<p class="empty-text">Aucun prestataire disponible</p>{/if}
    </div>
  </div>
</div>
{/if}

{#if confirmDeleteId}
<div class="ya-dialog-overlay" on:mousedown|self={() => confirmDeleteId = null}>
  <div class="ya-dialog" style="max-width:400px">
    <div class="ya-dialog__header"><h2 class="ya-dialog__title">Supprimer le projet ?</h2></div>
    <div class="ya-dialog__body">
      <p>Les taches ne seront pas supprimees, seulement delinkees du projet.</p>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => confirmDeleteId = null}>Annuler</button>
      <button class="ya-btn ya-btn--danger" on:click={() => deleteProject(confirmDeleteId)}>Supprimer</button>
    </div>
  </div>
</div>
{/if}

{#if showBudgetPanel && selectedProject}
<div class="ya-dialog-overlay" on:mousedown|self={() => showBudgetPanel = false}>
  <div class="ya-dialog" style="max-width:650px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Budget — {selectedProject.title}</h2>
      <button class="ya-dialog__close" on:click={() => showBudgetPanel = false}>x</button>
    </div>
    <div class="ya-dialog__body">
      <!-- 3-level summary cards: Prévu / Engagé / Facturé -->
      <div class="budget-detail-cards">
        <div class="bd-card">
          <div class="bd-card-icon" style="background:rgba(245,158,11,0.1);color:#F59E0B">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
          </div>
          <div class="bd-card-info">
            <span class="bd-card-label">Budget prevu</span>
            <span class="bd-card-val" style="color:#F59E0B">{budgetPrevu.toLocaleString('fr-FR')} EUR</span>
          </div>
        </div>
        <div class="bd-card">
          <div class="bd-card-icon" style="background:rgba(139,92,246,0.1);color:#8B5CF6">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
          </div>
          <div class="bd-card-info">
            <span class="bd-card-label">Engage</span>
            <span class="bd-card-val" style="color:#8B5CF6">{budgetEngage.toLocaleString('fr-FR')} EUR</span>
          </div>
        </div>
        <div class="bd-card">
          <div class="bd-card-icon" style="background:rgba(34,197,94,0.1);color:#22C55E">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>
          </div>
          <div class="bd-card-info">
            <span class="bd-card-label">Facture</span>
            <span class="bd-card-val" style="color:#22C55E">{budgetFacture.toLocaleString('fr-FR')} EUR</span>
          </div>
        </div>
      </div>

      <!-- Secondary indicators -->
      <div class="budget-status-row">
        <span class="bs-chip bs-accepted" title="Ce qu'il reste a commander sur le budget prevu">Reste a engager : {budgetResteAEngager.toLocaleString('fr-FR')} EUR</span>
        <span class="bs-chip bs-pending" title="Devis acceptes non encore factures">Reste a facturer : {budgetResteAFacturer.toLocaleString('fr-FR')} EUR</span>
        {#if budgetAttente > 0}
          <span class="bs-chip" style="background:rgba(148,163,184,0.1);color:#94A3B8" title="Devis en attente de validation">{budgetAttenteDocs.length} devis en attente ({budgetAttente.toLocaleString('fr-FR')} EUR)</span>
        {/if}
        {#if budgetNbRefuse > 0}
          <span class="bs-chip bs-refused">{budgetNbRefuse} refuse{budgetNbRefuse > 1 ? 's' : ''}</span>
        {/if}
      </div>

      <!-- Alert: facture without matching quote -->
      {#if budgetFacture > budgetEngage && budgetEngage > 0}
        <div class="budget-alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span>Le montant facture depasse l'engagement : des factures n'ont pas de devis associe.</span>
        </div>
      {/if}

      <!-- Table of documents, grouped by type -->
      {#if budgetDocs.length > 0}
        <table class="budget-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Type</th>
              <th>Montant</th>
              <th>Valide</th>
              <th>Statut</th>
              <th>Compte en</th>
            </tr>
          </thead>
          <tbody>
            {#each budgetDocs as doc}
              <tr>
                <td class="bt-title">{doc.title}</td>
                <td><span class="doc-type">{doc.doc_type}</span></td>
                <td class="bt-amount">{(doc.amount || 0).toLocaleString('fr-FR')} EUR</td>
                <td class="bt-amount">{doc.amount_accepted > 0 ? doc.amount_accepted.toLocaleString('fr-FR') + ' EUR' : '—'}</td>
                <td>
                  {#if doc.status === 'accepte'}<span class="doc-status doc-accepted">Accepte</span>
                  {:else if doc.status === 'refuse'}<span class="doc-status doc-refused">Refuse</span>
                  {:else if doc.status === 'en attente'}<span class="doc-status">En attente</span>
                  {:else}<span class="doc-status">—</span>{/if}
                </td>
                <td>
                  {#if isFacture(doc)}<span class="doc-status" style="background:rgba(34,197,94,0.15);color:#22C55E">Facture</span>
                  {:else if isEngageable(doc) && doc.status === 'accepte'}<span class="doc-status" style="background:rgba(139,92,246,0.15);color:#8B5CF6">Engage</span>
                  {:else}<span class="doc-status">—</span>{/if}
                </td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            <tr>
              <td colspan="5" style="font-weight:700;text-align:right">Engage</td>
              <td class="bt-amount" style="font-weight:700;color:#8B5CF6">{budgetEngage.toLocaleString('fr-FR')} EUR</td>
            </tr>
            <tr>
              <td colspan="5" style="font-weight:700;text-align:right">Facture</td>
              <td class="bt-amount" style="font-weight:700;color:#22C55E">{budgetFacture.toLocaleString('fr-FR')} EUR</td>
            </tr>
          </tfoot>
        </table>
      {:else}
        <p class="empty-text">Aucun document avec montant</p>
      {/if}

      {#if budgetPrevu > 0}
        <div style="margin-top:1rem;padding-top:0.75rem;border-top:1px solid var(--border-subtle)">
          <div class="budget-info" style="margin-bottom:0.25rem">
            <span>Consommation du budget (max engage/facture)</span>
            <span class="budget-pct" class:budget-over={budgetConsomme > budgetPrevu}>{Math.round((budgetConsomme / budgetPrevu) * 100)}% ({budgetConsomme.toLocaleString('fr-FR')} / {budgetPrevu.toLocaleString('fr-FR')} EUR)</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:{Math.min(100, (budgetConsomme / budgetPrevu) * 100)}%;background:{budgetConsomme > budgetPrevu ? '#EF4444' : '#22C55E'}"></div></div>
        </div>
      {:else if budgetConsomme > 0}
        <div style="margin-top:1rem;padding-top:0.75rem;border-top:1px solid var(--border-subtle);font-size:0.75rem;color:var(--text-muted)">
          Pas de budget prevu pour ce projet — suivi des depenses uniquement.
          Total engage/facture : <strong style="color:var(--text-heading)">{budgetConsomme.toLocaleString('fr-FR')} EUR</strong>
        </div>
      {/if}
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => showBudgetPanel = false}>Fermer</button>
    </div>
  </div>
</div>
{/if}

{#if editingDocLink}
<div class="ya-dialog-overlay" on:mousedown|self={() => editingDocLink = null}>
  <div class="ya-dialog" style="max-width:420px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Modifier — {editingDocLink.title}</h2>
      <button class="ya-dialog__close" on:click={() => editingDocLink = null}>x</button>
    </div>
    <div class="ya-dialog__body">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
        <label>Montant initial (EUR) <input type="number" bind:value={editDocForm.amount} min="0" step="0.01" /></label>
        <label>Montant valide (EUR) <input type="number" bind:value={editDocForm.amount_accepted} min="0" step="0.01" /></label>
      </div>
      <label>Statut
        <select bind:value={editDocForm.status}>
          <option value="">Non defini</option>
          <option value="en attente">En attente</option>
          <option value="accepte">Accepte</option>
          <option value="refuse">Refuse</option>
        </select>
      </label>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => editingDocLink = null}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={saveEditDocLink}>Enregistrer</button>
    </div>
  </div>
</div>
{/if}

{#if depsTask}
<div class="ya-dialog-overlay" on:mousedown|self={() => depsTask = null}>
  <div class="ya-dialog" style="max-width:500px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Dependances — {depsTask.title}</h2>
      <button class="ya-dialog__close" on:click={() => depsTask = null}>x</button>
    </div>
    <div class="ya-dialog__body">
      <p style="font-size:0.8125rem;color:var(--text-muted);margin-bottom:0.75rem">
        Cette tache ne peut etre consideree comme logiquement faisable que si toutes ses dependances sont terminees.
      </p>

      <div style="margin-bottom:1rem">
        <h4 style="margin:0 0 0.5rem;font-size:0.75rem;text-transform:uppercase;color:var(--text-muted)">Depend de</h4>
        {#if (depsTask.dependencies || []).length === 0}
          <p class="empty-text" style="padding:0.25rem 0">Aucune dependance</p>
        {:else}
          <ul class="deps-list">
            {#each depsTask.dependencies as d}
              <li class="deps-item" class:deps-item--done={d.done}>
                <span class="deps-check">{d.done ? '\u2713' : '\u25CB'}</span>
                <span class="deps-title">{d.title}</span>
                <button class="task-unlink" on:click={() => removeDependency(d.id)} title="Retirer">{'\u2715'}</button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <h4 style="margin:0 0 0.5rem;font-size:0.75rem;text-transform:uppercase;color:var(--text-muted)">Ajouter une dependance</h4>
      <div style="display:flex;gap:0.5rem">
        <select bind:value={depsPickId} style="flex:1">
          <option value={null}>— Choisir une tache —</option>
          {#each (selectedProject.tasks || []).filter(t => t.id !== depsTask.id && !(depsTask.dependencies || []).some(d => d.id === t.id)) as t}
            <option value={t.id}>{t.done ? '\u2713 ' : ''}{t.title}</option>
          {/each}
        </select>
        <button class="ya-btn ya-btn--primary" on:click={addDependency} disabled={!depsPickId}>Ajouter</button>
      </div>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => depsTask = null}>Fermer</button>
    </div>
  </div>
</div>
{/if}

{#if showDocAmountDialog}
<div class="ya-dialog-overlay" on:mousedown|self={() => showDocAmountDialog = false}>
  <div class="ya-dialog" style="max-width:420px">
    <div class="ya-dialog__header">
      <h2 class="ya-dialog__title">Montant du document</h2>
      <button class="ya-dialog__close" on:click={() => showDocAmountDialog = false}>x</button>
    </div>
    <div class="ya-dialog__body">
      <p style="font-size:0.8125rem;color:var(--text-muted);margin-bottom:0.75rem">Renseignez les montants si ce document a une valeur financiere (devis, facture, BPA, proposition...).</p>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
        <label>Montant initial (EUR) <input type="number" bind:value={docLinkForm.amount} min="0" step="0.01" /></label>
        <label>Montant valide (EUR) <input type="number" bind:value={docLinkForm.amount_accepted} min="0" step="0.01" /></label>
      </div>
      <label>Statut
        <select bind:value={docLinkForm.status}>
          <option value="">Non defini</option>
          <option value="en attente">En attente</option>
          <option value="accepte">Accepte</option>
          <option value="refuse">Refuse</option>
        </select>
      </label>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => { showDocAmountDialog = false; }}>Passer</button>
      <button class="ya-btn ya-btn--primary" on:click={confirmLinkDocument}>Lier le document</button>
    </div>
  </div>
</div>
{/if}

<style>
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; }
  .page-header h1 { font-size: 1.375rem; font-weight: 700; color: var(--text-heading); margin: 0; }

  .loading { text-align: center; padding: 3rem; color: var(--text-muted); }
  .empty-state { text-align: center; padding: 3rem; }
  .empty-state h3 { margin: 0.5rem 0 0.25rem; color: var(--text-heading); }
  .empty-state p { color: var(--text-muted); font-size: 0.8125rem; margin-bottom: 1rem; }
  .empty-text { color: var(--text-muted); font-size: 0.8125rem; padding: 0.75rem 0; }

  /* Project cards grid */
  .projects-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
  .project-card {
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.75rem;
    padding: 1.25rem; cursor: pointer; transition: all 0.2s; border-left: 4px solid;
  }
  .project-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.08); transform: translateY(-2px); }
  .project-card__header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.25rem; }
  .project-card__header h3 { font-size: 1rem; font-weight: 700; color: var(--text-heading); margin: 0; }
  .project-card__desc { font-size: 0.8125rem; color: var(--text-muted); margin: 0 0 0.75rem; }
  .project-card__meta { display: flex; gap: 1rem; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.75rem; }
  .project-card__footer { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); }

  .card-budget { margin-top: 0.625rem; padding-top: 0.625rem; border-top: 1px dashed var(--border-subtle); }
  .card-budget__label { display: flex; justify-content: space-between; font-size: 0.6875rem; color: var(--text-muted); margin-bottom: 0.25rem; }
  .card-budget__val { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--text-heading); }
  .card-budget__bar { background: var(--bg-base); height: 4px; border-radius: 2px; overflow: hidden; }
  .card-budget__fill { height: 100%; transition: width 0.3s; }
  .card-budget--over .card-budget__val { color: #EF4444; }
  .card-budget__split {
    display: flex; justify-content: space-between; font-size: 0.625rem;
    color: var(--text-muted); font-family: 'JetBrains Mono', monospace;
  }

  .status-badge { display: inline-block; padding: 0.2rem 0.625rem; border-radius: 1rem; font-size: 0.6875rem; font-weight: 600; white-space: nowrap; }

  .progress-bar { background: var(--bg-base); height: 6px; border-radius: 3px; overflow: hidden; margin-bottom: 0.375rem; }
  .progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }

  /* Detail */
  .detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
  .project-header-card {
    background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.75rem;
    padding: 1.25rem; border-left: 4px solid; display: flex; justify-content: space-between;
    align-items: center; margin-bottom: 0.75rem;
  }
  .project-header-card__info h2 { font-size: 1.25rem; font-weight: 700; color: var(--text-heading); margin: 0 0 0.25rem; }
  .project-header-card__info p { color: var(--text-muted); font-size: 0.8125rem; margin: 0 0 0.5rem; }
  .project-header-card__meta { display: flex; gap: 0.75rem; align-items: center; font-size: 0.75rem; color: var(--text-muted); }
  .progress-big-num { font-size: 2rem; font-weight: 700; }
  .progress-sub { font-size: 0.6875rem; color: var(--text-muted); text-align: center; }

  /* Sections */
  .section-card { background: var(--bg-card); border: 1px solid var(--border-card); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1rem; }
  .section-header { display: flex; justify-content: space-between; align-items: center; }
  .section-title { font-size: 0.9375rem; font-weight: 700; color: var(--text-heading); margin: 0 0 0.75rem; }

  /* Budget compact */
  .budget-compact { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.25rem; gap: 1rem; flex-wrap: wrap; }
  .budget-compact-cards { display: flex; gap: 1rem; }
  .budget-mini-card { display: flex; align-items: center; gap: 0.5rem; }
  .budget-mini-icon { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .budget-mini-val { font-size: 0.875rem; font-weight: 700; color: var(--text-heading); }
  .budget-mini-label { font-size: 0.625rem; color: var(--text-muted); text-transform: uppercase; }

  /* Budget detail panel */
  .budget-detail-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 1rem; }
  .bd-card { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: var(--bg-base); border-radius: 0.625rem; }
  .bd-card-icon { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .bd-card-info { display: flex; flex-direction: column; }
  .bd-card-label { font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; }
  .bd-card-val { font-size: 1.125rem; font-weight: 700; color: var(--text-heading); }

  .budget-status-row { display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }
  .bs-chip { padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.6875rem; font-weight: 600; cursor: default; }
  .bs-accepted { background: rgba(34,197,94,0.1); color: #22C55E; }
  .bs-pending { background: rgba(245,158,11,0.1); color: #F59E0B; }
  .bs-refused { background: rgba(239,68,68,0.1); color: #EF4444; }

  .budget-alert {
    display: flex; align-items: center; gap: 0.5rem;
    background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.25);
    color: #EF4444; padding: 0.5rem 0.75rem; border-radius: 0.5rem;
    font-size: 0.75rem; margin-bottom: 1rem;
  }

  .budget-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
  .budget-table th { padding: 0.5rem 0.75rem; text-align: left; font-size: 0.6875rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; border-bottom: 2px solid var(--border-subtle); }
  .budget-table td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border-subtle); }
  .budget-table tfoot td { border-bottom: none; border-top: 2px solid var(--border-subtle); }
  .bt-title { font-weight: 500; color: var(--text-heading); max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bt-amount { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }

  .budget-info { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); }
  .budget-pct { font-weight: 700; color: #F59E0B; }
  .budget-over { color: #EF4444 !important; }

  /* Gantt */
  .gantt-card { padding: 1.25rem 1.25rem 0.75rem; }
  .gantt-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; gap: 0.75rem; flex-wrap: wrap; }
  .gantt-zoom { display: inline-flex; background: var(--bg-base); border-radius: 0.5rem; padding: 2px; gap: 2px; }
  .gantt-zoom-btn {
    background: transparent; border: 0; color: var(--text-muted); padding: 0.25rem 0.625rem;
    border-radius: 0.375rem; font-size: 0.6875rem; font-weight: 600; cursor: pointer;
  }
  .gantt-zoom-btn:hover { color: var(--text-heading); }
  .gantt-zoom-btn--active {
    background: var(--bg-card); color: var(--text-heading);
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
  }
  .gantt-legend { display: flex; gap: 1rem; }
  .gantt-legend-item { display: flex; align-items: center; gap: 0.25rem; font-size: 0.6875rem; color: var(--text-muted); }
  .gantt-legend-dot { width: 10px; height: 10px; border-radius: 2px; }

  .gantt { overflow-x: auto; padding-bottom: 0.5rem; }
  .gantt-months {
    display: block; position: relative; height: 20px;
  }
  .gantt-months span {
    position: absolute; font-size: 0.6875rem; color: var(--text-muted);
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
  }
  .gantt-days {
    display: block; position: relative; height: 18px;
    border-bottom: 2px solid var(--border-subtle); margin-bottom: 0.25rem;
  }
  .gantt-day-tick {
    position: absolute; font-size: 0.5625rem; color: var(--text-muted);
    transform: translateX(-50%);
  }
  .gantt-body { position: relative; min-height: 80px; }
  .gantt-arrows {
    position: absolute; top: 0; left: 0; pointer-events: none; overflow: visible;
    z-index: 3;
  }
  .gantt-hidden-note {
    font-size: 0.75rem; color: var(--text-muted); font-style: italic;
    padding: 0.5rem 0 0; margin: 0;
  }
  .gantt-today-line {
    position: absolute; top: 0; bottom: 0; width: 2px; background: #EF4444; z-index: 2;
  }
  .gantt-today-label {
    position: absolute; top: -18px; left: 50%; transform: translateX(-50%);
    font-size: 0.5625rem; color: #EF4444; font-weight: 700; white-space: nowrap;
    background: rgba(239,68,68,0.1); padding: 1px 4px; border-radius: 2px;
  }
  .gantt-row {
    display: flex; align-items: center; padding: 0.25rem 0;
    border-bottom: 1px solid rgba(128,128,128,0.06);
  }
  .gantt-row-alt { background: rgba(128,128,128,0.03); }
  .gantt-task-name {
    width: 180px; font-size: 0.75rem; color: var(--text-secondary); flex-shrink: 0;
    padding-right: 0.75rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    display: flex; align-items: center; gap: 0.375rem;
  }
  .gantt-task-name.done { text-decoration: line-through; color: var(--text-muted); }
  .gantt-task-num {
    width: 18px; height: 18px; border-radius: 50%; background: var(--bg-base);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.5625rem; font-weight: 700; color: var(--text-muted); flex-shrink: 0;
  }
  .gantt-bar-area {
    flex: 1; height: 22px; position: relative; background: var(--bg-base);
    border-radius: 4px; overflow: hidden;
  }
  .gantt-week-line {
    position: absolute; top: 0; bottom: 0; width: 1px;
    background: var(--border-subtle); opacity: 0.3;
  }
  .gantt-bar {
    position: absolute; height: 16px; top: 3px; border-radius: 4px;
    transition: width 0.3s ease; display: flex; align-items: center; padding: 0 4px;
    overflow: hidden; cursor: grab; border: 1.5px solid;
    user-select: none;
  }
  .gantt-bar:active { cursor: grabbing; }
  .gantt-bar--dragging {
    transition: none !important; opacity: 0.85;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    z-index: 4;
  }
  .gantt-bar-resize-handle {
    position: absolute; right: 0; top: 0; bottom: 0; width: 8px;
    cursor: ew-resize;
  }
  .gantt-bar-resize-handle:hover {
    background: rgba(255,255,255,0.25);
  }
  .gantt-milestone { cursor: grab; }
  .gantt-milestone:active { cursor: grabbing; }
  .gantt-bar--late { box-shadow: 0 0 0 1px rgba(239,68,68,0.35); }
  .gantt-bar--blocked { border-style: dashed !important; opacity: 0.85; }

  /* Milestone diamond — drawn via a rotated square centered on the milestone date */
  .gantt-milestone {
    position: absolute; top: 4px; width: 14px; height: 14px;
    transform: translateX(-50%) rotate(45deg);
    border-radius: 2px; border: 1.5px solid;
    z-index: 1;
  }
  .gantt-milestone--done { opacity: 0.7; }
  .gantt-bar-fill {
    position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px 0 0 3px;
    opacity: 0.9; transition: width 0.3s ease; z-index: 0;
  }
  .gantt-bar-fill--full { width: 100%; border-radius: 3px; }
  .gantt-bar-text {
    font-size: 0.5rem; font-weight: 600; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; position: relative; z-index: 1;
  }

  /* Tasks */
  .task-list { display: flex; flex-direction: column; }
  .task-item { display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle); }
  .task-item:last-child { border-bottom: none; }
  .task-check { width: 18px; height: 18px; border-radius: 4px; border: 2px solid var(--border-subtle); cursor: pointer; flex-shrink: 0; margin-top: 0.125rem; }
  .task-check.done { background: #22C55E; border-color: #22C55E; }
  .task-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.25rem; }
  .task-title-row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .task-title { font-size: 0.8125rem; color: var(--text-heading); }
  .task-title.done { text-decoration: line-through; color: var(--text-muted); }
  .task-priority { padding: 0.125rem 0.5rem; border-radius: 0.25rem; font-size: 0.625rem; font-weight: 600; align-self: center; }
  .p3 { background: rgba(239,68,68,0.1); color: #EF4444; }
  .p2 { background: rgba(59,130,246,0.1); color: #3B82F6; }
  .p1 { background: rgba(34,197,94,0.1); color: #22C55E; }
  .task-date { font-size: 0.6875rem; color: var(--text-muted); }
  .task-dates {
    display: inline-flex; align-items: center; gap: 0.25rem;
    font-size: 0.6875rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;
    align-self: center; white-space: nowrap;
  }
  .task-dates__arrow { opacity: 0.5; }

  .task-deps-inline {
    display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem;
    font-size: 0.6875rem;
  }
  .task-deps-inline__label { color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.03em; font-weight: 600; font-size: 0.625rem; }
  .task-deps-inline__chip {
    padding: 0.0625rem 0.375rem; border-radius: 0.25rem;
    background: rgba(148,163,184,0.12); color: var(--text-secondary);
    border: 1px solid var(--border-subtle); font-size: 0.625rem;
    cursor: pointer; font-family: inherit;
  }
  .task-deps-inline__chip:hover {
    background: rgba(136,105,225,0.15); border-color: var(--primary); color: var(--primary);
  }
  .task-item--flash {
    animation: task-flash 1.5s ease-out;
  }
  @keyframes task-flash {
    0%   { background: rgba(136,105,225,0.25); }
    100% { background: transparent; }
  }
  .task-deps-inline__chip--done { background: rgba(34,197,94,0.1); color: #22C55E; border-color: rgba(34,197,94,0.25); }

  .task-unlink { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.875rem; padding: 0.25rem; align-self: center; }
  .task-unlink:hover { color: #EF4444; }

  .task-item--blocked { background: rgba(148,163,184,0.06); }
  .task-blocked-badge {
    background: rgba(148,163,184,0.15); color: #64748B;
    padding: 0.125rem 0.5rem; border-radius: 0.75rem; font-size: 0.625rem; font-weight: 600;
    display: inline-flex; align-items: center; gap: 0.25rem; white-space: nowrap;
  }
  .task-deps-btn, .task-edit-btn {
    background: none; border: none; color: var(--text-muted); cursor: pointer;
    font-size: 0.875rem; padding: 0.25rem; align-self: center;
  }
  .task-deps-btn:hover { color: var(--primary); }
  .task-edit-btn:hover { color: var(--primary); }

  .task-milestone-badge {
    color: #F59E0B; font-size: 0.75rem; font-weight: 700;
  }

  .checkbox-inline {
    display: flex !important; align-items: center; gap: 0.5rem;
    flex-direction: row !important; font-size: 0.8125rem; color: var(--text-secondary);
    cursor: pointer;
  }
  .checkbox-inline input { width: auto !important; margin: 0; }

  .deps-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.25rem; }
  .deps-item {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.375rem 0.5rem; background: var(--bg-base); border-radius: 0.375rem;
    font-size: 0.8125rem;
  }
  .deps-item--done .deps-title { text-decoration: line-through; color: var(--text-muted); }
  .deps-check { width: 16px; height: 16px; text-align: center; color: var(--text-muted); }
  .deps-item--done .deps-check { color: #22C55E; font-weight: 700; }
  .deps-title { flex: 1; }

  /* Budget summary */
  .budget-summary { display: flex; gap: 1.5rem; padding: 0.75rem 0; border-bottom: 1px solid var(--border-subtle); margin-bottom: 0.5rem; }
  .budget-stat { text-align: center; }
  .budget-stat-val { display: block; font-size: 1rem; font-weight: 700; color: var(--text-heading); }
  .budget-stat-label { font-size: 0.625rem; color: var(--text-muted); text-transform: uppercase; }

  /* Documents */
  .doc-list { display: flex; flex-direction: column; gap: 0.375rem; }
  .doc-item-rich { display: flex; align-items: center; gap: 0.75rem; padding: 0.625rem 0; border-bottom: 1px solid var(--border-subtle); }
  .doc-item-main { display: flex; align-items: center; gap: 0.5rem; flex: 1; min-width: 0; }
  .doc-type { padding: 0.125rem 0.5rem; border-radius: 0.25rem; font-size: 0.625rem; font-weight: 600; background: rgba(139,92,246,0.1); color: #8B5CF6; flex-shrink: 0; }
  .doc-title { font-size: 0.8125rem; color: var(--text-heading); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .doc-status { padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-size: 0.5625rem; font-weight: 600; background: rgba(148,163,184,0.1); color: #94A3B8; }
  .doc-accepted { background: rgba(34,197,94,0.1) !important; color: #22C55E !important; }
  .doc-refused { background: rgba(239,68,68,0.1) !important; color: #EF4444 !important; }
  .doc-item-amounts { display: flex; gap: 0.75rem; flex-shrink: 0; }
  .doc-amount { font-size: 0.6875rem; color: var(--text-muted); }
  .doc-amount-ok { font-size: 0.6875rem; color: #22C55E; font-weight: 600; }
  .doc-date { font-size: 0.6875rem; color: var(--text-muted); }

  /* Suppliers */
  .sup-list { display: flex; flex-direction: column; gap: 0.375rem; }
  .sup-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle); font-size: 0.8125rem; }
  .sup-item strong { color: var(--text-heading); }
  .sup-item span { color: var(--text-muted); font-size: 0.75rem; }
  .sup-logo {
    width: 32px; height: 32px; border-radius: 6px; overflow: hidden; flex-shrink: 0;
    background: var(--bg-base); display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--border-subtle);
  }
  .sup-logo img { width: 100%; height: 100%; object-fit: contain; }
  .sup-logo__initials { font-size: 0.75rem; font-weight: 700; color: var(--text-muted); }

  /* Notes */
  .note-input { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
  .note-input textarea { flex: 1; padding: 0.5rem; border: 1px solid var(--border-subtle); border-radius: 0.375rem; background: var(--bg-base); color: var(--text-heading); font-family: inherit; font-size: 0.8125rem; resize: none; }
  .notes-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .note-item { padding: 0.75rem; background: var(--bg-base); border-radius: 0.5rem; position: relative; }
  .note-date { font-size: 0.625rem; color: var(--text-muted); }
  .note-content { font-size: 0.8125rem; color: var(--text-heading); margin: 0.25rem 0 0; }
  .note-delete { position: absolute; top: 0.5rem; right: 0.5rem; background: none; border: none; color: var(--text-muted); cursor: pointer; }
  .note-delete:hover { color: #EF4444; }

  /* Link dialog items */
  .link-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.625rem 0.75rem; cursor: pointer; border-radius: 0.375rem; font-size: 0.8125rem; }
  .link-item:hover { background: var(--bg-hover); }
  .link-type { padding: 0.125rem 0.5rem; border-radius: 0.25rem; font-size: 0.625rem; font-weight: 600; background: rgba(59,130,246,0.1); color: #3B82F6; }

  /* Color picker */
  .color-row { display: flex; gap: 0.5rem; margin-top: 0.25rem; }
  .color-dot { width: 1.75rem; height: 1.75rem; border-radius: 50%; border: 2px solid transparent; cursor: pointer; }
  .color-dot.active { border-color: var(--text-heading); transform: scale(1.15); }

  /* Dialog form */
  label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8125rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 0.75rem; }
  input, select, textarea { padding: 0.5rem 0.75rem; border: 1px solid var(--border-subtle); border-radius: 0.375rem; background: var(--bg-base); color: var(--text-heading); font-family: inherit; font-size: 0.8125rem; }
  input:focus, select:focus, textarea:focus { outline: none; border-color: var(--primary); }
</style>
