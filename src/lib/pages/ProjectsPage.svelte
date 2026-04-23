<script>
  import { onMount } from 'svelte';
  import { api, API_BASE } from '../api/client.js';
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

  // Task dialog
  let showTaskDialog = false;
  let taskForm = { title: '', priority: 2, due_date: '', notes: '', site: '' };

  // Note
  let noteText = '';

  // Budget panel
  let showBudgetPanel = false;

  // Budget computed values
  $: budgetDocs = (selectedProject?.documents || []).filter(d => d.amount > 0 || d.amount_accepted > 0);
  $: budgetTotalInit = budgetDocs.reduce((s, d) => s + (d.amount || 0), 0);
  $: budgetTotalVal = budgetDocs.reduce((s, d) => s + (d.amount_accepted || 0), 0);
  $: budgetNbAccepte = budgetDocs.filter(d => d.status === 'accepte').length;
  $: budgetNbRefuse = budgetDocs.filter(d => d.status === 'refuse').length;
  $: budgetNbAttente = budgetDocs.filter(d => d.status === 'en attente' || !d.status).length;

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

  // ── Tasks ──
  async function addTask() {
    if (!taskForm.title.trim()) return;
    try {
      await api.post(`/api/projects/${selectedProject.id}/tasks`, taskForm);
      showTaskDialog = false;
      taskForm = { title: '', priority: 2, due_date: '', notes: '', site: '' };
      await openProject(selectedProject);
    } catch (e) { toastError('Erreur: ' + e.message); }
  }

  async function toggleTask(task) {
    try {
      await api.patch(`/api/tasks/${task.id}/done`);
      await openProject(selectedProject);
    } catch (e) { console.error('Toggle task failed:', e); }
  }

  async function unlinkTask(taskId) {
    try {
      await api.delete(`/api/projects/${selectedProject.id}/tasks/${taskId}`);
      await openProject(selectedProject);
    } catch {}
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
    } catch {}
  }

  async function unlinkDocument(docId) {
    try {
      await api.delete(`/api/projects/${selectedProject.id}/documents/${docId}`);
      await openProject(selectedProject);
    } catch {}
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
    } catch {}
  }

  // ── Notes ──
  async function addNote() {
    if (!noteText.trim()) return;
    try {
      await api.post(`/api/projects/${selectedProject.id}/notes`, { content: noteText });
      noteText = '';
      await openProject(selectedProject);
    } catch {}
  }

  async function deleteNote(noteId) {
    try {
      await api.delete(`/api/projects/${selectedProject.id}/notes/${noteId}`);
      await openProject(selectedProject);
    } catch {}
  }

  // ── Gantt helpers ──
  function ganttData(project) {
    if (!project?.tasks?.length) return { tasks: [], months: [], startMs: 0, totalMs: 1 };
    const tasks = project.tasks.filter(t => t.due_date);
    if (!tasks.length) return { tasks: project.tasks, months: [], startMs: 0, totalMs: 1 };

    const pStart = project.start_date ? new Date(project.start_date) : new Date(Math.min(...tasks.map(t => new Date(t.due_date))));
    const pEnd = project.end_date ? new Date(project.end_date) : new Date(Math.max(...tasks.map(t => new Date(t.due_date))));
    // Add padding
    pStart.setDate(pStart.getDate() - 7);
    pEnd.setDate(pEnd.getDate() + 14);
    const startMs = pStart.getTime();
    const totalMs = pEnd.getTime() - startMs;

    // Generate month labels
    const months = [];
    const cur = new Date(pStart);
    cur.setDate(1);
    while (cur <= pEnd) {
      const pos = ((cur.getTime() - startMs) / totalMs) * 100;
      months.push({ label: cur.toLocaleDateString('fr-FR', { month: 'short' }), pos: Math.max(0, pos) });
      cur.setMonth(cur.getMonth() + 1);
    }

    return { tasks: project.tasks, months, startMs, totalMs };
  }

  function ganttBarStyle(task, startMs, totalMs) {
    if (!task.due_date) return '';
    const dueMs = new Date(task.due_date).getTime();
    // Estimate start as 14 days before due
    const taskStartMs = dueMs - 14 * 86400000;
    const left = Math.max(0, ((taskStartMs - startMs) / totalMs) * 100);
    const width = Math.min(100 - left, (14 * 86400000 / totalMs) * 100);
    return `left:${left}%;width:${Math.max(3, width)}%`;
  }

  function todayPos(startMs, totalMs) {
    const now = Date.now();
    return Math.max(0, Math.min(100, ((now - startMs) / totalMs) * 100));
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
        </div>
      {/each}
    </div>
  {/if}

{:else}
  <!-- ═══ DETAIL VIEW ═══ -->
  <div class="detail-header">
    <button class="ya-btn ya-btn--ghost" on:click={backToList}>← Retour</button>
    <div style="display:flex;gap:0.5rem">
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

    {#if selectedProject.budget > 0 || selectedProject.documents?.some(d => d.amount > 0)}
      <div class="budget-compact">
        <div class="budget-compact-cards">
          <div class="budget-mini-card">
            <div class="budget-mini-icon" style="background:rgba(139,92,246,0.1)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
            </div>
            <div>
              <div class="budget-mini-val">{budgetTotalInit.toLocaleString('fr-FR')} EUR</div>
              <div class="budget-mini-label">Montant initial</div>
            </div>
          </div>
          <div class="budget-mini-card">
            <div class="budget-mini-icon" style="background:rgba(34,197,94,0.1)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <div>
              <div class="budget-mini-val" style="color:#22C55E">{budgetTotalVal.toLocaleString('fr-FR')} EUR</div>
              <div class="budget-mini-label">Valide</div>
            </div>
          </div>
          {#if selectedProject.budget > 0}
            <div class="budget-mini-card">
              <div class="budget-mini-icon" style="background:rgba(245,158,11,0.1)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
              </div>
              <div>
                <div class="budget-mini-val" style="color:#F59E0B">{selectedProject.budget.toLocaleString('fr-FR')} EUR</div>
                <div class="budget-mini-label">Budget prevu</div>
              </div>
            </div>
          {/if}
        </div>
        <button class="ya-btn ya-btn--ghost ya-btn--sm" on:click={() => showBudgetPanel = true}>Voir le detail</button>
      </div>
    {/if}

    <!-- Gantt -->
    {@const gd = ganttData(selectedProject)}
    {#if gd.months.length > 0}
      <div class="section-card gantt-card">
        <div class="gantt-header">
          <h3 class="section-title" style="margin:0">Diagramme de Gantt</h3>
          <div class="gantt-legend">
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:#22C55E"></span>Termine</span>
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:{selectedProject.color}"></span>En cours</span>
            <span class="gantt-legend-item"><span class="gantt-legend-dot" style="background:#94A3B8"></span>A faire</span>
          </div>
        </div>
        <div class="gantt">
          <div class="gantt-months">
            {#each gd.months as m}
              <span style="left:{m.pos}%">{m.label}</span>
            {/each}
          </div>
          <div class="gantt-body">
            <div class="gantt-today-line" style="left:{todayPos(gd.startMs, gd.totalMs)}%">
              <span class="gantt-today-label">Aujourd'hui</span>
            </div>
            {#each gd.tasks as task, idx}
              <div class="gantt-row" class:gantt-row-alt={idx % 2 === 1}>
                <div class="gantt-task-name" class:done={task.done}>
                  <span class="gantt-task-num">{idx + 1}</span>
                  {task.title}
                </div>
                <div class="gantt-bar-area">
                  {#if task.due_date}
                    {@const barColor = task.done ? '#22C55E' : '#94A3B8'}
                    <div class="gantt-bar" style="{ganttBarStyle(task, gd.startMs, gd.totalMs)};background:{barColor}" title="{task.title} — {task.due_date}">
                      {#if task.done}<span class="gantt-bar-check">✓</span>{/if}
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      </div>
    {/if}

    <!-- Tasks -->
    <div class="section-card">
      <div class="section-header">
        <h3 class="section-title">Taches ({selectedProject.tasks?.length || 0})</h3>
        <button class="ya-btn ya-btn--primary ya-btn--sm" on:click={() => { showTaskDialog = true; }}>+ Ajouter</button>
      </div>
      {#if selectedProject.tasks?.length > 0}
        <div class="task-list">
          {#each selectedProject.tasks as task}
            <div class="task-item">
              <div class="task-check" class:done={task.done} on:click={() => toggleTask(task)}></div>
              <span class="task-title" class:done={task.done}>{task.title}</span>
              <span class="task-priority p{task.priority}">{task.priority === 3 ? 'Haute' : task.priority === 1 ? 'Basse' : 'Normale'}</span>
              {#if task.due_date}<span class="task-date">{formatDate(task.due_date)}</span>{/if}
              <button class="task-unlink" on:click={() => unlinkTask(task.id)} title="Retirer du projet">✕</button>
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
        {#if budgetTotalInit > 0 || budgetTotalVal > 0}
          <div class="budget-summary">
            <div class="budget-stat">
              <span class="budget-stat-val">{budgetTotalInit.toLocaleString('fr-FR')} EUR</span>
              <span class="budget-stat-label">Montant initial</span>
            </div>
            <div class="budget-stat">
              <span class="budget-stat-val" style="color:#22C55E">{budgetTotalVal.toLocaleString('fr-FR')} EUR</span>
              <span class="budget-stat-label">Valide</span>
            </div>
            <div class="budget-stat">
              <span class="budget-stat-val" style="color:{budgetTotalInit - budgetTotalVal > 0 ? '#F59E0B' : '#22C55E'}">{(budgetTotalInit - budgetTotalVal).toLocaleString('fr-FR')} EUR</span>
              <span class="budget-stat-label">Ecart</span>
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
      <h2 class="ya-dialog__title">Nouvelle tache</h2>
      <button class="ya-dialog__close" on:click={() => showTaskDialog = false}>x</button>
    </div>
    <div class="ya-dialog__body">
      <label>Titre <input type="text" bind:value={taskForm.title} placeholder="Titre de la tache..." /></label>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem">
        <label>Priorite
          <select bind:value={taskForm.priority}>
            <option value={1}>Basse</option><option value={2}>Normale</option><option value={3}>Haute</option>
          </select>
        </label>
        <label>Echeance <input type="date" bind:value={taskForm.due_date} /></label>
      </div>
      <label>Site <input type="text" bind:value={taskForm.site} placeholder="Ex: NDK, SU, NDE..." /></label>
      <label>Notes <textarea bind:value={taskForm.notes} rows="2" placeholder="Notes..."></textarea></label>
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => showTaskDialog = false}>Annuler</button>
      <button class="ya-btn ya-btn--primary" on:click={addTask} disabled={!taskForm.title.trim()}>Ajouter</button>
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
      <!-- Summary cards -->
      <div class="budget-detail-cards">
        <div class="bd-card">
          <div class="bd-card-icon" style="background:rgba(139,92,246,0.1);color:#8B5CF6">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
          </div>
          <div class="bd-card-info">
            <span class="bd-card-label">Montant total</span>
            <span class="bd-card-val">{budgetTotalInit.toLocaleString('fr-FR')} EUR</span>
          </div>
        </div>
        <div class="bd-card">
          <div class="bd-card-icon" style="background:rgba(34,197,94,0.1);color:#22C55E">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <div class="bd-card-info">
            <span class="bd-card-label">Valide</span>
            <span class="bd-card-val" style="color:#22C55E">{budgetTotalVal.toLocaleString('fr-FR')} EUR</span>
          </div>
        </div>
        <div class="bd-card">
          <div class="bd-card-icon" style="background:rgba(245,158,11,0.1);color:#F59E0B">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <div class="bd-card-info">
            <span class="bd-card-label">Ecart</span>
            <span class="bd-card-val" style="color:#F59E0B">{(budgetTotalInit - budgetTotalVal).toLocaleString('fr-FR')} EUR</span>
          </div>
        </div>
      </div>

      <!-- Status summary -->
      <div class="budget-status-row">
        <span class="bs-chip bs-accepted">{budgetNbAccepte} accepte{budgetNbAccepte > 1 ? 's' : ''}</span>
        <span class="bs-chip bs-pending">{budgetNbAttente} en attente</span>
        <span class="bs-chip bs-refused">{budgetNbRefuse} refuse{budgetNbRefuse > 1 ? 's' : ''}</span>
      </div>

      <!-- Table of documents -->
      {#if budgetDocs.length > 0}
        <table class="budget-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Type</th>
              <th>Montant</th>
              <th>Valide</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {#each budgetDocs as doc}
              <tr>
                <td class="bt-title">{doc.title}</td>
                <td><span class="doc-type">{doc.doc_type}</span></td>
                <td class="bt-amount">{doc.amount.toLocaleString('fr-FR')} EUR</td>
                <td class="bt-amount" style="color:#22C55E">{doc.amount_accepted > 0 ? doc.amount_accepted.toLocaleString('fr-FR') + ' EUR' : '—'}</td>
                <td>
                  {#if doc.status === 'accepte'}<span class="doc-status doc-accepted">Accepte</span>
                  {:else if doc.status === 'refuse'}<span class="doc-status doc-refused">Refuse</span>
                  {:else if doc.status === 'en attente'}<span class="doc-status">En attente</span>
                  {:else}<span class="doc-status">—</span>{/if}
                </td>
              </tr>
            {/each}
          </tbody>
          <tfoot>
            <tr>
              <td colspan="2" style="font-weight:700">Total</td>
              <td class="bt-amount" style="font-weight:700">{budgetTotalInit.toLocaleString('fr-FR')} EUR</td>
              <td class="bt-amount" style="font-weight:700;color:#22C55E">{budgetTotalVal.toLocaleString('fr-FR')} EUR</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      {:else}
        <p class="empty-text">Aucun document avec montant</p>
      {/if}

      {#if selectedProject.budget > 0}
        <div style="margin-top:1rem;padding-top:0.75rem;border-top:1px solid var(--border-subtle)">
          <div class="budget-info" style="margin-bottom:0.25rem">
            <span>Budget prevu: {selectedProject.budget.toLocaleString('fr-FR')} EUR</span>
            <span class="budget-pct" class:budget-over={budgetTotalVal > selectedProject.budget}>{selectedProject.budget > 0 ? Math.round((budgetTotalVal / selectedProject.budget) * 100) : 0}% utilise</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:{Math.min(100, selectedProject.budget > 0 ? (budgetTotalVal / selectedProject.budget) * 100 : 0)}%;background:{budgetTotalVal > selectedProject.budget ? '#EF4444' : '#22C55E'}"></div></div>
        </div>
      {/if}
    </div>
    <div class="ya-dialog__footer">
      <button class="ya-btn ya-btn--ghost" on:click={() => showBudgetPanel = false}>Fermer</button>
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

  .budget-status-row { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .bs-chip { padding: 0.25rem 0.75rem; border-radius: 1rem; font-size: 0.6875rem; font-weight: 600; }
  .bs-accepted { background: rgba(34,197,94,0.1); color: #22C55E; }
  .bs-pending { background: rgba(245,158,11,0.1); color: #F59E0B; }
  .bs-refused { background: rgba(239,68,68,0.1); color: #EF4444; }

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
  .gantt-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
  .gantt-legend { display: flex; gap: 1rem; }
  .gantt-legend-item { display: flex; align-items: center; gap: 0.25rem; font-size: 0.6875rem; color: var(--text-muted); }
  .gantt-legend-dot { width: 10px; height: 10px; border-radius: 2px; }

  .gantt { overflow-x: auto; padding-bottom: 0.5rem; }
  .gantt-months {
    display: flex; position: relative; height: 24px;
    border-bottom: 2px solid var(--border-subtle); margin-bottom: 0.25rem;
  }
  .gantt-months span {
    position: absolute; font-size: 0.6875rem; color: var(--text-muted);
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
  }
  .gantt-body { position: relative; min-height: 80px; }
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
  .gantt-bar {
    position: absolute; height: 16px; top: 3px; border-radius: 4px;
    transition: width 0.3s ease; display: flex; align-items: center; padding-left: 4px;
  }
  .gantt-bar-check { font-size: 0.5625rem; color: #fff; font-weight: 700; }

  /* Tasks */
  .task-list { display: flex; flex-direction: column; }
  .task-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle); }
  .task-item:last-child { border-bottom: none; }
  .task-check { width: 18px; height: 18px; border-radius: 4px; border: 2px solid var(--border-subtle); cursor: pointer; flex-shrink: 0; }
  .task-check.done { background: #22C55E; border-color: #22C55E; }
  .task-title { flex: 1; font-size: 0.8125rem; color: var(--text-heading); }
  .task-title.done { text-decoration: line-through; color: var(--text-muted); }
  .task-priority { padding: 0.125rem 0.5rem; border-radius: 0.25rem; font-size: 0.625rem; font-weight: 600; }
  .p3 { background: rgba(239,68,68,0.1); color: #EF4444; }
  .p2 { background: rgba(59,130,246,0.1); color: #3B82F6; }
  .p1 { background: rgba(34,197,94,0.1); color: #22C55E; }
  .task-date { font-size: 0.6875rem; color: var(--text-muted); }
  .task-unlink { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.875rem; padding: 0.25rem; }
  .task-unlink:hover { color: #EF4444; }

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
